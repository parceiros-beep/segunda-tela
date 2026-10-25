"""
Segunda Tela - Servidor para Windows
Transmite a tela do PC em MJPEG para o app Android "Segunda Tela".

Protocolo (o mesmo que o app usa):
  GET /stream?fps=20&scale=1.0&monitor=1&quality=70   (qualidade fixa)
  GET /stream?fps=30&scale=1.0&monitor=1&bitrate=20   (alvo em Mbps)
  &pin=1234 quando o servidor foi iniciado com PIN.
Descoberta automática: anuncia _segundatela._tcp na rede (mDNS).

Uso:
  SegundaTela-Servidor.exe                 (porta 8080, sem PIN)
  SegundaTela-Servidor.exe --porta 9000 --pin 1234
Modo USB: com o celular ligado no cabo, rode no PC
  adb reverse tcp:8080 tcp:8080
e toque em "Modo USB" no app.
"""

import argparse
import io
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import mss
from PIL import Image

import win_input
import tela_virtual

try:
    from zeroconf import ServiceInfo, Zeroconf
except ImportError:  # descoberta automática é opcional
    Zeroconf = None

BOUNDARY = "segundatela"
VERSAO = "1.0"


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


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SegundaTela/" + VERSAO
    pin = ""
    # Área (left, top, w, h) do monitor que está sendo transmitido agora.
    # Usada para mapear o toque do tablet -> posição na tela do PC.
    area_ativa = None

    def log_message(self, fmt, *args):  # log enxuto no console
        pass

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path in ("/", "/status"):
            corpo = ("Segunda Tela servidor %s - OK\n" % VERSAO).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if url.path != "/stream":
            self.send_error(404, "Nao encontrado")
            return
        if self.pin and qs.get("pin", [""])[0] != self.pin:
            self.send_error(403, "PIN incorreto")
            return
        self.transmitir(qs)

    def do_POST(self):
        if urlparse(self.path).path != "/input":
            self.send_error(404, "Nao encontrado")
            return
        # Resposta mínima; o canal fica aberto recebendo linhas de evento.
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
        print("[controle] %s conectou (mouse/teclado)" % self.client_address[0])
        try:
            self.loop_input()
        except (OSError, ValueError):
            pass
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
            self.aplicar_evento(linha)

    def aplicar_evento(self, linha):
        p = linha.split(" ")
        cmd = p[0]
        area = Handler.area_ativa
        if area is None:
            return
        left, top, w, h = area

        def px(n):  # normalizado -> pixel de tela
            return int(left + float(p[n]) * w)

        def py(n):
            return int(top + float(p[n]) * h)

        try:
            if cmd == "m":
                win_input.move(px(1), py(2))
            elif cmd == "d":
                win_input.left_down(px(1), py(2))
            elif cmd == "u":
                win_input.left_up(px(1), py(2))
            elif cmd == "r":
                win_input.right_click(px(1), py(2))
            elif cmd == "s":
                win_input.wheel(px(1), py(2), int(p[3]))
            elif cmd == "k":
                win_input.key(p[1])
            elif cmd == "t":
                win_input.text(linha[2:].replace("\\n", "\n"))
        except (IndexError, ValueError):
            pass

    def transmitir(self, qs):
        fps = numero(qs, "fps", 20, int, 1, 60)
        escala = numero(qs, "scale", 1.0, float, 0.2, 1.0)
        monitor = numero(qs, "monitor", 1, int, 0)
        qualidade = numero(qs, "quality", 70, int, 10, 95)
        bitrate = numero(qs, "bitrate", 0, float, 0, 100)
        # Bitrate alvo -> orçamento de bytes por quadro; a qualidade se ajusta.
        orcamento = int(bitrate * 1_000_000 / 8 / fps) if bitrate > 0 else 0

        cliente = self.client_address[0]
        print("[+] %s conectou: %d fps, escala %.0f%%, monitor %d, %s"
              % (cliente, fps, escala * 100, monitor,
                 "%g Mbps" % bitrate if bitrate else "qualidade %d" % qualidade))

        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.send_response(200)
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=" + BOUNDARY)
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        extend = qs.get("extend", ["0"])[0] == "1"
        intervalo = 1.0 / fps
        buf = io.BytesIO()
        try:
            with mss.mss() as sct:
                if extend:
                    monitor, aviso = tela_virtual.escolher_monitor_estendido(sct)
                    if aviso:
                        print("[tela estendida] " + aviso)
                if monitor >= len(sct.monitors):
                    monitor = 1
                area = sct.monitors[monitor]
                # Guarda a área para o mapeamento do toque (/input).
                Handler.area_ativa = (area["left"], area["top"],
                                      area["width"], area["height"])
                while True:
                    inicio = time.perf_counter()
                    shot = sct.grab(area)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    if escala < 0.999:
                        img = img.resize((max(1, int(img.width * escala)),
                                          max(1, int(img.height * escala))),
                                         Image.BILINEAR)
                    buf.seek(0)
                    buf.truncate()
                    img.save(buf, "JPEG", quality=qualidade, optimize=False)
                    jpeg = buf.getvalue()

                    if orcamento:  # controle simples de taxa
                        if len(jpeg) > orcamento * 1.1 and qualidade > 20:
                            qualidade -= 5
                        elif len(jpeg) < orcamento * 0.8 and qualidade < 90:
                            qualidade += 2

                    self.wfile.write(
                        ("--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
                         % (BOUNDARY, len(jpeg))).encode("ascii"))
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()

                    resto = intervalo - (time.perf_counter() - inicio)
                    if resto > 0:
                        time.sleep(resto)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        print("[-] %s desconectou" % cliente)


def anunciar_mdns(porta):
    if Zeroconf is None:
        return None, None
    try:
        ips = [ip for ip in ips_locais()]
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


def main():
    p = argparse.ArgumentParser(description="Servidor Segunda Tela")
    p.add_argument("--porta", type=int, default=8080)
    p.add_argument("--pin", default="")
    a = p.parse_args()

    Handler.pin = a.pin.strip()
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", a.porta), Handler)
    except OSError as e:
        print("Não foi possível abrir a porta %d: %s" % (a.porta, e))
        input("Enter para sair...")
        sys.exit(1)
    srv.daemon_threads = True

    zc, info = anunciar_mdns(a.porta)

    print("=" * 52)
    print(" Segunda Tela - servidor %s" % VERSAO)
    print("=" * 52)
    print(" Porta: %d   PIN: %s" % (a.porta, Handler.pin or "(sem PIN)"))
    for ip in ips_locais():
        print(" No app, use o IP: %s" % ip)
    print(" Modo USB: adb reverse tcp:%d tcp:%d" % (a.porta, a.porta))
    print(" Na 1a vez, permita o acesso no aviso do Firewall do Windows.")
    print(" Feche esta janela (ou Ctrl+C) para encerrar.")
    print("=" * 52)

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if zc:
            zc.unregister_service(info)
            zc.close()
        srv.shutdown()


if __name__ == "__main__":
    main()
