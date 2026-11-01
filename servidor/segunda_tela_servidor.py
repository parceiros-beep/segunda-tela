"""
Segunda Tela - Servidor para Windows (v3)
Transforma o tablet/celular Android num monitor de verdade para o PC.

Recursos:
  - Tela estendida real: cria um monitor virtual do tamanho do tablet
    (driver instalado sozinho na 1ª vez) ou espelha a tela principal.
  - Vídeo H.264 com encoder da placa de vídeo (NVIDIA/AMD/Intel) até 60 fps;
    modo compatível em MJPEG.
  - Toque multitoque nativo do Windows, caneta (S Pen) com pressão e
    inclinação, mouse, teclado físico do tablet e atalhos.
  - Wi-Fi (descoberta automática) ou cabo USB (adb reverse automático).

Protocolo:
  GET  /status                      -> JSON com informações do servidor
  GET  /video?w=&h=&fps=&kbps=&escala=200&modo=estender|espelhar
             &lado=direita|esquerda|acima
       resposta binária: pacotes [tipo:1][tamanho:4 BE][dados]
         tipo 0 = JSON {"w","h","encoder"} ; tipo 1 = quadro H.264 (Annex-B)
  GET  /stream?fps=&quality=&w=&h=&modo=...   (MJPEG, compatibilidade)
  GET  /audio                       som do PC: PCM 16 bits, 48 kHz, estéreo
  GET  /direto?banda=5|2.4|auto|off liga/desliga a rede direta (hotspot do PC)
  POST /input                       canal de eventos, uma linha por evento
       o servidor responde "pong t"; com "clipon" envia "clip <base64>"
       quando a área de transferência do PC muda; com "appon" envia
       "app <programa.exe>" quando muda o programa em primeiro plano
  &pin=1234 quando o servidor foi iniciado com PIN.
"""

import argparse
import base64
import io
import json
import os
import select
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import audio
import config
import hotspot
import janela
import win_clip
import win_display
import win_input
import tela_virtual
import video

try:
    from zeroconf import ServiceInfo, Zeroconf
except ImportError:  # descoberta automática é opcional
    Zeroconf = None

BOUNDARY = "segundatela"
VERSAO = "3.8"
try:  # o CI grava este arquivo com o número da compilação e o commit
    from versao_build import BUILD
except ImportError:
    BUILD = "desenvolvimento"
_WIN = sys.platform == "win32"


class Servidor(ThreadingHTTPServer):
    # No Windows, SO_REUSEADDR deixa DOIS servidores abrirem a mesma porta sem
    # erro (brigando por monitor virtual e ffmpeg). Desligado, a 2ª instância
    # avisa que a porta está em uso.
    allow_reuse_address = not _WIN
    daemon_threads = True


def manter_vivo(sock):
    """Detecta tablet que sumiu sem avisar (Wi-Fi caiu) em ~10 s, sem timeout
    de envio: um timeout no socket derrubava o vídeo quando o Wi-Fi engasgava."""
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if _WIN:
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
    except (OSError, AttributeError, ValueError):
        pass


def ip_principal():
    """IP da placa de rede que tem a rota padrão (o Wi-Fi/cabo de verdade)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def ips_locais():
    ips = set()
    principal = ip_principal()
    if principal:
        ips.add(principal)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def numero(qs, nome, padrao, tipo=float, minimo=None, maximo=None):
    try:
        v = tipo(qs.get(nome, [padrao])[0])
    except (TypeError, ValueError):
        v = padrao
    if minimo is not None:
        v = max(minimo, v)
    if maximo is not None:
        v = min(maximo, v)
    return v


# ------------------------------------------------------------------ sessões
class Controle:
    """Uma tela por vez (como o Duet): nova conexão substitui a anterior."""
    lock = threading.Lock()
    geracao = 0
    geracao_som = 0
    sessao = None
    area = None          # (left, top, w, h) da tela mostrada no tablet
    extendido = False

    @classmethod
    def nova(cls):
        with cls.lock:
            cls.geracao += 1
            if cls.sessao:
                cls.sessao.parar()
                cls.sessao = None
            return cls.geracao

    @classmethod
    def terminou(cls, geracao):
        """Desliga o monitor virtual se ninguém reconectar em alguns segundos."""
        def depois():
            time.sleep(6)
            with cls.lock:
                desligar = cls.geracao == geracao and cls.extendido
                if desligar:
                    cls.extendido = False
            if desligar:  # fora do lock: o Windows avisa todas as janelas da mudança
                win_input.touch_reset()
                tela_virtual.desativar()
        threading.Thread(target=depois, daemon=True).start()


def preparar_tela(qs):
    """Liga o monitor virtual (ou escolhe o principal). Devolve o alvo."""
    modo = qs.get("modo", ["estender"])[0]
    if qs.get("extend", ["0"])[0] == "1":
        modo = "estender"
    w = numero(qs, "w", 1920, int, 320, 7680) // 2 * 2
    h = numero(qs, "h", 1080, int, 240, 4320) // 2 * 2
    lado = qs.get("lado", ["direita"])[0]
    mon = None
    if modo != "estender" and Controle.extendido:
        Controle.extendido = False
        tela_virtual.desativar()
    if modo == "estender":
        mon = tela_virtual.ativar(w, h, 60, lado)
        if mon is None:
            print("[tela estendida] Indisponível agora; espelhando a tela principal.")
        else:
            Controle.extendido = True
            escala = numero(qs, "escala", 0, int, 0, 500)
            if escala and win_display.definir_escala(mon["nome"], escala):
                print("[tela estendida] Escala do Windows: %d%%" % escala)
    if mon is None:
        mon = win_display.primario()
    if mon is None or "w" not in mon:
        pw, ph = win_display.tamanho_primario()
        mon = {"nome": "", "x": 0, "y": 0, "w": pw, "h": ph}
    alvo = {"nome": mon.get("nome", ""), "x": mon["x"], "y": mon["y"],
            "w": mon["w"] // 2 * 2, "h": mon["h"] // 2 * 2}
    alvo["dxgi"] = win_display.indice_dxgi(alvo["nome"]) if alvo["nome"] else None
    Controle.area = (alvo["x"], alvo["y"], alvo["w"], alvo["h"])
    return alvo


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SegundaTela/" + VERSAO
    pin = ""

    def log_message(self, fmt, *args):  # log enxuto no console
        pass

    def _pin_ok(self, qs):
        if self.pin and qs.get("pin", [""])[0] != self.pin:
            self.send_error(403, "PIN incorreto")
            return False
        return True

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path in ("/", "/status"):
            info = {"app": "segundatela", "versao": VERSAO, "build": BUILD,
                    "nome": socket.gethostname(), "pin": bool(self.pin),
                    "driver": tela_virtual.instalado(),
                    "h264": bool(video.caminho_ffmpeg()),
                    "som": audio.disponivel(), "direto": _WIN}
            corpo = json.dumps(info).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if url.path == "/video":
            if self._pin_ok(qs):
                self.transmitir_h264(qs)
            return
        if url.path == "/stream":
            if self._pin_ok(qs):
                self.transmitir_mjpeg(qs)
            return
        if url.path == "/audio":
            if self._pin_ok(qs):
                self.transmitir_audio()
            return
        if url.path == "/direto":
            if self._pin_ok(qs):
                self.conexao_direta(qs.get("banda", ["5"])[0])
            return
        self.send_error(404, "Nao encontrado")

    def _json(self, dados):
        corpo = json.dumps(dados).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    # ---------------------------------------------------------- rede direta
    def conexao_direta(self, banda):
        if banda == "off":
            self._json(hotspot.desligar())
        else:
            self._json(hotspot.ligar(banda if banda in ("5", "2.4") else "auto"))

    # ---------------------------------------------------------- som
    def transmitir_audio(self):
        if not audio.disponivel():
            self.send_error(503, "Som do PC indisponivel neste servidor")
            return
        with Controle.lock:
            Controle.geracao_som += 1
            minha = Controle.geracao_som
        cliente = self.client_address[0]
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        manter_vivo(self.connection)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        print("[som] %s conectou" % cliente)
        try:
            audio.transmitir(self.connection, lambda: Controle.geracao_som == minha)
        except OSError:
            pass
        except Exception as e:  # erro do Windows/soundcard: avisa e encerra
            print("[som] Não consegui capturar o som: %s" % e)
        print("[som] %s desconectou" % cliente)

    # ---------------------------------------------------------- H.264
    def transmitir_h264(self, qs):
        geracao = Controle.nova()
        txt = lambda nome, padrao: qs.get(nome, [padrao])[0]
        opcoes = video.Opcoes(
            fps=numero(qs, "fps", 60, int, 10, 60),
            kbps=numero(qs, "kbps", 20000, int, 500, 150000),
            codec=txt("codec", "h264"), taxa=txt("taxa", "cbr"),
            cq=numero(qs, "cq", 23, int, 10, 51), vel=txt("vel", "rapida"),
            gop=numero(qs, "gop", 2.0, float, 0.5, 30.0),
            intra=txt("intra", "0") == "1", cursor=txt("cursor", "1") == "1")
        cliente = self.client_address[0]
        print("[+] %s conectou (%s)" % (cliente, opcoes.resumo()))
        alvo = preparar_tela(qs)

        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        manter_vivo(self.connection)
        try:
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
        except OSError:
            pass
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        fim = threading.Event()
        sock = self.connection
        trava = threading.Lock()

        def pacote(tipo, dados):
            with trava:
                sock.sendall(struct.pack(">BI", tipo, len(dados)) + dados)

        enviou_config = []

        def ao_quadro(q):
            if q is None:
                fim.set()
                return
            try:
                if not enviou_config:
                    enviou_config.append(1)
                    pacote(0, json.dumps({
                        "w": alvo["w"], "h": alvo["h"], "codec": sessao.codec,
                        "encoder": sessao.descricao, "fps": opcoes.fps,
                        "kbps": opcoes.kbps, "extendido": Controle.extendido}).encode())
                pacote(1, q)
            except OSError:
                fim.set()
                sessao.parar()

        sessao = video.Sessao(alvo, opcoes, ao_quadro)
        with Controle.lock:
            if Controle.geracao != geracao:
                return
            Controle.sessao = sessao
        try:
            if not sessao.iniciar():
                pacote(2, "Nenhum encoder de vídeo funcionou neste PC. "
                          "Use o modo Compatível.".encode())
                return
            # Espera o fim (desconexão ou ffmpeg encerrado). O socket fica sem
            # timeout: ele também valia para o envio dos quadros e derrubava a
            # transmissão quando o Wi-Fi engasgava por mais de 1 s.
            while not fim.is_set():
                pronto, _, _ = select.select([sock], [], [], 1.0)
                if pronto:
                    try:
                        if sock.recv(1) == b"":
                            break
                    except OSError:
                        break
        except OSError:
            pass
        finally:
            with Controle.lock:
                if Controle.sessao is sessao:
                    Controle.sessao = None   # a bandeja volta a "Aguardando"
            sessao.parar()
            print("[-] %s desconectou" % cliente)
            Controle.terminou(geracao)

    # ---------------------------------------------------------- MJPEG
    def transmitir_mjpeg(self, qs):
        import mss
        from PIL import Image
        geracao = Controle.nova()
        fps = numero(qs, "fps", 20, int, 1, 60)
        qualidade = numero(qs, "quality", 70, int, 10, 95)
        escala = numero(qs, "scale", 1.0, float, 0.2, 1.0)
        cliente = self.client_address[0]
        print("[+] %s conectou (compatível MJPEG, %d fps)" % (cliente, fps))
        alvo = preparar_tela(qs)
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.send_response(200)
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=" + BOUNDARY)
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        intervalo = 1.0 / fps
        buf = io.BytesIO()
        area = {"left": alvo["x"], "top": alvo["y"],
                "width": alvo["w"], "height": alvo["h"]}
        try:
            with mss.mss() as sct:
                while Controle.geracao == geracao:
                    inicio = time.perf_counter()
                    shot = sct.grab(area)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    if escala < 0.999:
                        img = img.resize((max(1, int(img.width * escala)),
                                          max(1, int(img.height * escala))),
                                         Image.BILINEAR)
                    buf.seek(0)
                    buf.truncate()
                    img.save(buf, "JPEG", quality=qualidade)
                    jpeg = buf.getvalue()
                    self.wfile.write(
                        ("--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
                         % (BOUNDARY, len(jpeg))).encode("ascii"))
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                    resto = intervalo - (time.perf_counter() - inicio)
                    if resto > 0:
                        time.sleep(resto)
        except OSError:
            pass
        print("[-] %s desconectou" % cliente)
        Controle.terminou(geracao)

    # ---------------------------------------------------------- entrada
    def do_POST(self):
        if urlparse(self.path).path != "/input":
            self.send_error(404, "Nao encontrado")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Connection", "keep-alive")
        self.send_header("Content-Length", "2")
        self.end_headers()
        try:
            self.wfile.write(b"ok")
            self.wfile.flush()
        except OSError:
            return
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print("[controle] %s conectou (toque/caneta/teclado)" % self.client_address[0])
        self._trava = threading.Lock()
        self._vivo = True
        self._clip = {"ultimo": None, "ver": None, "ligado": False}
        manter_vivo(self.connection)
        try:
            self.loop_input()
        except (OSError, ValueError):
            pass
        finally:
            self._vivo = False   # para os vigias de clipboard e de programa
            win_input.touch_reset()
        print("[controle] %s desconectou" % self.client_address[0])

    def loop_input(self):
        rfile = self.rfile
        while True:
            raw = rfile.readline()
            if not raw:
                break
            linha = raw.decode("utf-8", "replace").strip()
            if not linha:
                continue
            if self.pin:
                if "|" not in linha or linha.rsplit("|", 1)[1] != self.pin:
                    continue
                linha = linha.rsplit("|", 1)[0]
            if linha.startswith("png "):  # medição de atraso pelo app
                self._enviar("pong %s\n" % linha[4:])
                continue
            if linha == "clipon":  # o app quer a área de transferência compartilhada
                if not self._clip["ligado"]:
                    self._clip["ligado"] = True
                    threading.Thread(target=self._vigiar_clip, daemon=True).start()
                continue
            if linha == "appon":  # o app troca a barra conforme o programa aberto
                threading.Thread(target=self._vigiar_programa, daemon=True).start()
                continue
            if linha.startswith("clip "):  # copiado no tablet -> PC
                try:
                    texto = base64.b64decode(linha[5:]).decode("utf-8")
                except ValueError:
                    continue
                self._clip["ultimo"] = texto
                win_clip.escrever(texto)
                self._clip["ver"] = win_clip.versao()
                continue
            try:
                aplicar_evento(linha)
            except Exception as e:  # um evento ruim não pode derrubar o canal
                self._erros_evento = getattr(self, "_erros_evento", 0) + 1
                if self._erros_evento <= 5:
                    print("[entrada] evento ignorado (%s: %s)" % (type(e).__name__, e))

    def _enviar(self, texto):
        with self._trava:
            self.wfile.write(texto.encode("utf-8"))
            self.wfile.flush()

    def _vigiar_programa(self):
        """Avisa o tablet quando muda o programa em primeiro plano no PC."""
        ultimo = None
        while self._vivo:
            nome = janela.programa_atual()
            if nome and nome != ultimo:
                ultimo = nome
                try:
                    self._enviar("app %s\n" % nome)
                except OSError:
                    break
            time.sleep(1.0)

    def _vigiar_clip(self):
        """Copiou algo no PC: manda para o tablet (texto até ~500 KB)."""
        c = self._clip
        c["ver"] = win_clip.versao()
        while self._vivo:
            time.sleep(0.7)
            v = win_clip.versao()
            if v == c["ver"]:
                continue
            c["ver"] = v
            texto = win_clip.ler()
            if not texto or texto == c["ultimo"] or len(texto) > 500000:
                continue
            c["ultimo"] = texto
            try:
                self._enviar("clip %s\n" % base64.b64encode(texto.encode("utf-8")).decode())
            except OSError:
                break


def aplicar_evento(linha):
    """Converte uma linha do app em entrada no Windows.

    Coordenadas chegam normalizadas (0..1) na tela mostrada no tablet.
      m/d/u/r x y          mouse: mover, apertar, soltar, botão direito
      s x y n              rolagem (n = cliques da roda)
      k CTRL+C             atalho; t texto  -> digita texto
      kd vk / ku vk        tecla física (código virtual do Windows)
      T d|m|u id x y       toque nativo; TM id x y id x y ... (vários dedos)
      TR                   solta todos os toques
      P est x y pressão tiltX tiltY botões    caneta
      rm dx dy             touchpad: move a partir da posição atual
      cl / cr              clique esquerdo / direito no cursor atual
      sw n                 rolagem no cursor atual
    """
    p = linha.split(" ")
    cmd = p[0]
    area = Controle.area
    if area is None:
        return
    left, top, w, h = area

    def px(v):
        return int(left + min(max(float(v), 0.0), 1.0) * (w - 1))

    def py(v):
        return int(top + min(max(float(v), 0.0), 1.0) * (h - 1))

    try:
        if cmd == "m":
            win_input.move(px(p[1]), py(p[2]))
        elif cmd == "d":
            win_input.left_down(px(p[1]), py(p[2]))
        elif cmd == "u":
            win_input.left_up(px(p[1]), py(p[2]))
        elif cmd == "r":
            win_input.right_click(px(p[1]), py(p[2]))
        elif cmd == "s":
            win_input.wheel(px(p[1]), py(p[2]), int(p[3]))
        elif cmd == "k":
            win_input.key(p[1])
        elif cmd == "t":
            win_input.text(linha[2:].replace("\\n", "\n"))
        elif cmd == "kd":
            win_input.key_down(int(p[1]))
        elif cmd == "ku":
            win_input.key_up(int(p[1]))
        elif cmd == "T":
            win_input.touch(p[1], int(p[2]), px(p[3]), py(p[4]))
        elif cmd == "TM":
            pts = []
            for i in range(1, len(p) - 2, 3):
                pts.append((int(p[i]), px(p[i + 1]), py(p[i + 2])))
            win_input.touch_move_varios(pts)
        elif cmd == "TR":
            win_input.touch_reset()
        elif cmd == "rm":  # touchpad: deslocamento normalizado da tela do tablet
            win_input.move_rel(float(p[1]) * w, float(p[2]) * h)
        elif cmd == "cl":
            win_input.clique_aqui(False)
        elif cmd == "cr":
            win_input.clique_aqui(True)
        elif cmd == "sw":
            win_input.wheel_aqui(int(p[1]))
        elif cmd == "P":
            win_input.pen(p[1], px(p[2]), py(p[3]), float(p[4]),
                          float(p[5]), float(p[6]), int(p[7]))
    except (IndexError, ValueError):
        pass


# ------------------------------------------------------------------ USB
def caminho_adb():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for c in (os.path.join(base, "adb", "adb.exe"), os.path.join(base, "adb.exe")):
        if os.path.isfile(c):
            return c
    return shutil.which("adb")


def vigiar_usb(porta):
    """Com o tablet no cabo (depuração USB ligada), faz o adb reverse sozinho."""
    adb = caminho_adb()
    if not adb:
        return
    flags = 0x08000000 if _WIN else 0
    # O servidor do adb (daemon) herdaria os pipes de captura e travaria esta
    # thread no Windows; sobe antes, sem pipes.
    try:
        subprocess.run([adb, "start-server"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=20, creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        pass
    feitos = set()
    while True:
        try:
            r = subprocess.run([adb, "devices"], capture_output=True, text=True,
                               timeout=10, creationflags=flags)
            atuais = set()
            for linha in r.stdout.splitlines()[1:]:
                partes = linha.split()
                if len(partes) >= 2 and partes[1] == "device":
                    atuais.add(partes[0])
            for serial in atuais - feitos:
                rr = subprocess.run([adb, "-s", serial, "reverse",
                                     "tcp:%d" % porta, "tcp:%d" % porta],
                                    capture_output=True, timeout=10, creationflags=flags)
                if rr.returncode == 0:
                    print("[usb] Tablet %s no cabo: no app toque em USB." % serial)
            feitos = atuais
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(3)


def encerrar_adb():
    """Fecha o adb que abrimos (senão ele fica segurando arquivos)."""
    adb = caminho_adb()
    if adb:
        try:
            subprocess.run([adb, "kill-server"], capture_output=True, timeout=5,
                           creationflags=0x08000000 if _WIN else 0)
        except (OSError, subprocess.SubprocessError):
            pass


# ------------------------------------------------------------------ mDNS
def anunciar_mdns(porta):
    if Zeroconf is None:
        return None, None
    try:
        # Só o IP principal: adaptadores virtuais (VPN, WSL, VirtualBox)
        # fariam o tablet tentar um endereço que ele não alcança.
        principal = ip_principal()
        ips = [principal] if principal else ips_locais()
        if not ips:
            return None, None
        nome = socket.gethostname()
        info = ServiceInfo(
            "_segundatela._tcp.local.",
            "%s._segundatela._tcp.local." % nome,
            addresses=[socket.inet_aton(ip) for ip in ips],
            port=porta,
            properties={"versao": VERSAO},
            server="%s.local." % nome,
        )
        zc = Zeroconf()
        zc.register_service(info)
        return zc, info
    except Exception as e:  # sem mDNS o IP manual continua funcionando
        print("Aviso: descoberta automática indisponível (%s)" % e)
        return None, None


def rodar_bandeja(ao_sair):
    """Ícone na bandeja: status, desligar a tela estendida e sair.
    Devolve False se a bandeja não estiver disponível (aí o console continua)."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        return False
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 10, 60, 46), radius=8, fill=(3, 129, 254, 255))
    d.rectangle((26, 46, 38, 54), fill=(3, 129, 254, 255))
    d.rectangle((18, 54, 46, 58), fill=(3, 129, 254, 255))

    def estado(_item):  # texto dinâmico: o pystray passa só o item
        # Sem lock: esta função roda na thread da bandeja, que não pode esperar.
        return "Tablet conectado" if Controle.sessao is not None else "Aguardando o tablet"

    def desligar(_icon, _item):
        tela_virtual.desativar()

    def direto(banda):
        def acao(icon, _item):
            def rodar():
                r = hotspot.ligar(banda)
                if r.get("ok") and r.get("ativo"):
                    msg = "Rede %s ligada (%s). Senha: %s" % (r["ssid"], r.get("banda_nome") or "?", r["senha"])
                else:
                    msg = "Não consegui ligar a rede direta: %s" % r.get("msg", "")
                try:
                    icon.notify(msg, "Conexão direta")
                except Exception:
                    pass
            threading.Thread(target=rodar, daemon=True).start()
        return acao

    def desligar_direto(_icon, _item):
        threading.Thread(target=hotspot.desligar, daemon=True).start()

    def qr(_icon, _item):
        threading.Thread(target=hotspot.mostrar_qr, daemon=True).start()

    def ao_abrir(banda):
        def acao(_icon, _item):
            config.gravar("direto_ao_abrir", banda)
        return acao

    def marcado(banda):
        return lambda _item: config.ler("direto_ao_abrir") == banda

    def sair(icon, _item):
        ao_sair()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Segunda Tela " + VERSAO, None, enabled=False),
        pystray.MenuItem(estado, None, enabled=False),
        pystray.MenuItem("Desligar tela estendida", desligar),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Conexão direta 5 GHz", direto("5")),
        pystray.MenuItem("Conexão direta 2,4 GHz", direto("2.4")),
        pystray.MenuItem("Desligar conexão direta", desligar_direto),
        pystray.MenuItem("Mostrar QR code da rede direta", qr),
        pystray.MenuItem("Ligar a conexão direta ao abrir", pystray.Menu(
            pystray.MenuItem("Não", ao_abrir(None), checked=marcado(None), radio=True),
            pystray.MenuItem("5 GHz", ao_abrir("5"), checked=marcado("5"), radio=True),
            pystray.MenuItem("2,4 GHz", ao_abrir("2.4"), checked=marcado("2.4"), radio=True))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", sair))
    pystray.Icon("segundatela", img, "Segunda Tela", menu).run()
    return True


def iniciar_com_windows(ligar):
    if not _WIN:
        return
    import winreg
    chave = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave, 0, winreg.KEY_SET_VALUE) as k:
        if ligar:
            winreg.SetValueEx(k, "SegundaTela", 0, winreg.REG_SZ,
                              '"%s"' % os.path.abspath(sys.executable))
        else:
            try:
                winreg.DeleteValue(k, "SegundaTela")
            except FileNotFoundError:
                pass


def desligar_quickedit():
    """Clicar na janela do console seleciona texto e CONGELA o próximo print()
    (e com ele as conexões) até apertar Enter. Desliga esse modo."""
    if not _WIN:
        return
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.GetStdHandle.restype = wintypes.HANDLE
        k.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        h = k.GetStdHandle(-10)  # STD_INPUT_HANDLE
        modo = wintypes.DWORD()
        if k.GetConsoleMode(h, ctypes.byref(modo)):
            # 0x80 = ENABLE_EXTENDED_FLAGS, 0x40 = ENABLE_QUICK_EDIT_MODE
            k.SetConsoleMode(h, (modo.value | 0x80) & ~0x40)
    except Exception:
        pass


def autoteste():
    """--selftest: confere se tudo que o servidor usa veio dentro do .exe."""
    import importlib
    ok = True

    def modulo(nome, critico=True):
        nonlocal ok
        try:
            importlib.import_module(nome)
            print("  ok     %s" % nome)
        except Exception as e:
            print("  FALTA  %s (%s: %s)%s" % (nome, type(e).__name__, e,
                                              "" if critico else "  [opcional]"))
            if critico:
                ok = False

    print("Autoteste do Segunda Tela %s (build %s)" % (VERSAO, BUILD))
    for nome in ("PIL.Image", "PIL.ImageDraw", "mss", "numpy", "qrcode", "zeroconf"):
        modulo(nome)
    if _WIN:
        modulo("pystray")
        modulo("winreg")
    modulo("soundcard", critico=False)  # som é opcional (pode não haver áudio no CI)
    if getattr(sys, "frozen", False):
        itens = {"ffmpeg": video.caminho_ffmpeg(), "adb": caminho_adb(),
                 "driver": os.path.join(getattr(sys, "_MEIPASS", ""), "drivers", "MttVDD.inf")}
        for nome, caminho in itens.items():
            existe = bool(caminho) and os.path.exists(caminho)
            print("  %s  %s" % ("ok    " if existe else "FALTA ", nome))
            ok = ok and existe
    print("RESULTADO:", "tudo certo" if ok else "FALHOU")
    return ok


def main():
    """Executa o servidor; qualquer erro vira arquivo de log e a janela espera
    você ler, em vez de fechar sem deixar rastro."""
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass
    log = None
    try:
        import faulthandler
        log = open(os.path.join(config.pasta(), "erro.log"), "a", encoding="utf-8")
        log.write("\n=== %s (versão %s, build %s) ===\n"
                  % (time.strftime("%Y-%m-%d %H:%M:%S"), VERSAO, BUILD))
        log.flush()
        faulthandler.enable(file=log)   # também registra quedas nativas (ctypes)
    except Exception:
        pass
    try:
        _main()
    except (SystemExit, KeyboardInterrupt):
        raise
    except BaseException:
        import traceback
        texto = traceback.format_exc()
        print("\n" + texto)
        try:
            if log:
                log.write(texto)
                log.flush()
        except OSError:
            pass
        print("O servidor encontrou um erro e parou. O texto acima também foi salvo em:")
        print("  " + os.path.join(config.pasta(), "erro.log"))
        try:
            input("Pressione Enter para fechar...")
        except (EOFError, OSError):
            pass
        sys.exit(1)


def _main():
    p = argparse.ArgumentParser(description="Servidor Segunda Tela")
    p.add_argument("--porta", type=int, default=8080)
    p.add_argument("--pin", default="")
    p.add_argument("--instalar-driver", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--desinstalar-driver", action="store_true",
                   help="remove o monitor virtual (pede administrador)")
    p.add_argument("--iniciar-com-windows", choices=["sim", "nao"],
                   help="abrir o servidor junto com o Windows")
    p.add_argument("--direto", choices=["5", "2.4", "auto"],
                   help="ligar a rede direta (hotspot do PC) ao abrir")
    p.add_argument("--sem-bandeja", action="store_true",
                   help="não criar o ícone da bandeja (só o console)")
    p.add_argument("--selftest", action="store_true",
                   help="verifica se tudo veio dentro do executável e sai")
    a = p.parse_args()

    if a.selftest:
        sys.exit(0 if autoteste() else 1)

    if a.instalar_driver:  # processo elevado (UAC)
        ok = tela_virtual.instalar_driver_admin()
        if _WIN and getattr(sys, "frozen", False):
            subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule",
                            "name=Segunda Tela", "dir=in", "action=allow",
                            "program=%s" % sys.executable, "enable=yes"],
                           capture_output=True)
        sys.exit(0 if ok else 1)
    if a.desinstalar_driver:
        tela_virtual.desinstalar_driver_admin()
        return
    if a.iniciar_com_windows:
        iniciar_com_windows(a.iniciar_com_windows == "sim")
        print("Iniciar com o Windows:", a.iniciar_com_windows)
        return

    win_display.ativar_dpi()
    desligar_quickedit()
    if _WIN:
        os.system("title Segunda Tela - servidor %s (build %s)" % (VERSAO, BUILD))

    Handler.pin = a.pin.strip()
    try:
        srv = Servidor(("0.0.0.0", a.porta), Handler)
    except OSError as e:
        print("Não foi possível abrir a porta %d: %s" % (a.porta, e))
        input("Enter para sair...")
        sys.exit(1)

    print("=" * 56)
    print(" Segunda Tela - servidor %s   (build %s)" % (VERSAO, BUILD))
    print("=" * 56)
    # Tela estendida: instala o monitor virtual já na abertura (1ª vez).
    if _WIN:
        tela_virtual.instalar_se_preciso()
        tela_virtual.recolher()
    print(" Tela estendida: %s" % ("pronta" if tela_virtual.instalado()
                                   else "indisponível (espelhamento)"))
    print(" Vídeo H.264: %s" % ("pronto" if video.caminho_ffmpeg()
                                else "ffmpeg ausente (modo compatível)"))
    print(" Porta: %d   PIN: %s" % (a.porta, Handler.pin or "(sem PIN)"))
    principal = ip_principal()
    if principal:
        print(" No app, toque no PC encontrado ou digite: %s" % principal)
    outros = [ip for ip in ips_locais() if ip != principal]
    if outros:
        print(" Outros IPs deste PC: %s" % ", ".join(outros))
    print(" USB: ligue a 'Depuração USB' no tablet e plugue o cabo.")
    print(" Feche esta janela (ou Ctrl+C) para encerrar.")
    print("=" * 56)

    print(" Som do PC no tablet: %s" % ("pronto" if audio.disponivel() else "indisponível"))
    print(" Conexão direta: pelo ícone da bandeja ou pelo app (5 GHz ou 2,4 GHz).")
    # Conexão direta ao abrir: pelo parâmetro ou pela opção salva na bandeja.
    banda_inicial = a.direto or config.ler("direto_ao_abrir")
    if banda_inicial:
        threading.Thread(target=hotspot.ligar, args=(banda_inicial,), daemon=True).start()

    zc, info = anunciar_mdns(a.porta)

    def limpar():
        with Controle.lock:
            if Controle.sessao:
                Controle.sessao.parar()
            Controle.geracao_som += 1
        tela_virtual.desativar()
        encerrar_adb()
        hotspot.desligar_se_nosso()

    if _WIN:
        # Fechar a janela pelo X: desliga o monitor virtual e o adb antes de sair.
        import ctypes
        _HANDLER = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)

        def ao_fechar(evento):
            if evento in (2, 5, 6):  # CLOSE, LOGOFF, SHUTDOWN
                limpar()
            return 0

        _main._handler = _HANDLER(ao_fechar)  # manter referência viva
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_main._handler, True)

    threading.Thread(target=vigiar_usb, args=(a.porta,), daemon=True).start()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        # Ícone na bandeja do Windows (bloqueia até "Sair"). Sem pystray, ou se a
        # bandeja falhar por qualquer motivo, o servidor continua pelo console.
        usou_bandeja = False
        if _WIN and not a.sem_bandeja:
            try:
                usou_bandeja = rodar_bandeja(limpar)
            except Exception as e:
                print("[bandeja] Não consegui criar o ícone (%s: %s). "
                      "Seguindo só com o console." % (type(e).__name__, e))
        if not usou_bandeja:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        # Cada passo protegido: um erro em um não pode pular os outros.
        for passo in (limpar,
                      lambda: zc and zc.unregister_service(info),
                      lambda: zc and zc.close(),
                      srv.shutdown):
            try:
                passo()
            except Exception as e:
                print("[encerrar] %s: %s" % (type(e).__name__, e))


if __name__ == "__main__":
    main()
