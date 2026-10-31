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
  POST /input                       canal de eventos, uma linha por evento
  &pin=1234 quando o servidor foi iniciado com PIN.
"""

import argparse
import io
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import win_display
import win_input
import tela_virtual
import video

try:
    from zeroconf import ServiceInfo, Zeroconf
except ImportError:  # descoberta automática é opcional
    Zeroconf = None

BOUNDARY = "segundatela"
VERSAO = "3.0"
_WIN = sys.platform == "win32"


def ips_locais():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
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
                if cls.geracao == geracao and cls.extendido:
                    cls.extendido = False
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
    fps = numero(qs, "fps", 60, int, 10, 120)
    lado = qs.get("lado", ["direita"])[0]
    mon = None
    if modo == "estender":
        mon = tela_virtual.ativar(w, h, 60 if fps <= 60 else fps, lado)
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
            info = {"app": "segundatela", "versao": VERSAO,
                    "nome": socket.gethostname(), "pin": bool(self.pin),
                    "driver": tela_virtual.instalado(),
                    "h264": bool(video.caminho_ffmpeg())}
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
        self.send_error(404, "Nao encontrado")

    # ---------------------------------------------------------- H.264
    def transmitir_h264(self, qs):
        geracao = Controle.nova()
        fps = numero(qs, "fps", 60, int, 10, 120)
        kbps = numero(qs, "kbps", 20000, int, 1000, 150000)
        cliente = self.client_address[0]
        print("[+] %s conectou (H.264, %d fps, %d Mbps)" % (cliente, fps, kbps // 1000))
        alvo = preparar_tela(qs)

        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
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

        def ao_quadro(q):
            if q is None:
                fim.set()
                return
            try:
                pacote(1, q)
            except OSError:
                fim.set()
                sessao.parar()

        sessao = video.Sessao(alvo, fps, kbps, ao_quadro)
        with Controle.lock:
            if Controle.geracao != geracao:
                return
            Controle.sessao = sessao
        try:
            pacote(0, json.dumps({"w": alvo["w"], "h": alvo["h"],
                                  "extendido": Controle.extendido}).encode())
            if not sessao.iniciar():
                pacote(2, "Nenhum encoder de vídeo funcionou neste PC. "
                          "Use o modo Compatível.".encode())
                return
            pacote(0, json.dumps({"w": alvo["w"], "h": alvo["h"],
                                  "encoder": sessao.descricao,
                                  "extendido": Controle.extendido}).encode())
            # Espera o fim (desconexão ou ffmpeg encerrado); detecta queda
            # do cliente lendo o socket.
            sock.settimeout(1.0)
            while not fim.is_set():
                try:
                    if sock.recv(1) == b"":
                        break
                except socket.timeout:
                    continue
                except OSError:
                    break
        except OSError:
            pass
        finally:
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
        try:
            self.loop_input()
        except (OSError, ValueError):
            pass
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
            aplicar_evento(linha)


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


# ------------------------------------------------------------------ mDNS
def anunciar_mdns(porta):
    if Zeroconf is None:
        return None, None
    try:
        ips = ips_locais()
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


def main():
    p = argparse.ArgumentParser(description="Servidor Segunda Tela")
    p.add_argument("--porta", type=int, default=8080)
    p.add_argument("--pin", default="")
    p.add_argument("--instalar-driver", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--desinstalar-driver", action="store_true",
                   help="remove o monitor virtual (pede administrador)")
    p.add_argument("--iniciar-com-windows", choices=["sim", "nao"],
                   help="abrir o servidor junto com o Windows")
    a = p.parse_args()

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
    if _WIN:
        os.system("title Segunda Tela - servidor %s" % VERSAO)

    Handler.pin = a.pin.strip()
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", a.porta), Handler)
    except OSError as e:
        print("Não foi possível abrir a porta %d: %s" % (a.porta, e))
        input("Enter para sair...")
        sys.exit(1)
    srv.daemon_threads = True

    print("=" * 56)
    print(" Segunda Tela - servidor %s" % VERSAO)
    print("=" * 56)
    # Tela estendida: instala o monitor virtual já na abertura (1ª vez).
    if _WIN:
        tela_virtual.instalar_se_preciso()
    print(" Tela estendida: %s" % ("pronta" if tela_virtual.instalado()
                                   else "indisponível (espelhamento)"))
    print(" Vídeo H.264: %s" % ("pronto" if video.caminho_ffmpeg()
                                else "ffmpeg ausente (modo compatível)"))
    print(" Porta: %d   PIN: %s" % (a.porta, Handler.pin or "(sem PIN)"))
    for ip in ips_locais():
        print(" No app, toque no PC encontrado ou digite: %s" % ip)
    print(" USB: ligue a 'Depuração USB' no tablet e plugue o cabo.")
    print(" Feche esta janela (ou Ctrl+C) para encerrar.")
    print("=" * 56)

    zc, info = anunciar_mdns(a.porta)
    threading.Thread(target=vigiar_usb, args=(a.porta,), daemon=True).start()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        with Controle.lock:
            if Controle.sessao:
                Controle.sessao.parar()
        tela_virtual.desativar()
        if zc:
            zc.unregister_service(info)
            zc.close()
        srv.shutdown()


if __name__ == "__main__":
    main()
