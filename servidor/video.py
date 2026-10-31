"""
Vídeo H.264 de baixa latência com o ffmpeg (embutido no .exe).

Captura: ddagrab (Desktop Duplication, na GPU) -> encoder de hardware
(NVIDIA NVENC, AMD AMF, Intel QuickSync). Se nada disso existir, cai para
gdigrab + libx264 (CPU). O ffmpeg entrega FLV (cada quadro com tamanho) e
aqui viram quadros H.264 Annex-B para o app decodificar com MediaCodec.
"""
import os
import shutil
import subprocess
import sys
import threading
import time

_WIN = sys.platform == "win32"
_encoder_ok = None  # memoriza a 1ª combinação que funcionou


def caminho_ffmpeg():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for c in (os.path.join(base, "ffmpeg.exe"), os.path.join(base, "ffmpeg")):
        if os.path.isfile(c):
            return c
    return shutil.which("ffmpeg")


def _encoders(kbps, fps, origem_gpu):
    """Lista de (nome, filtro, args do encoder) na ordem de preferência."""
    b = "%dk" % kbps
    buf = "%dk" % max(kbps // max(fps, 1) * 2, 200)
    comum = ["-g", str(fps * 2), "-bf", "0"]
    sw = "hwdownload,format=bgra,format=yuv420p" if origem_gpu else "format=yuv420p"
    lista = [
        ("NVIDIA NVENC", None if origem_gpu else "format=yuv420p",
         ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ull", "-rc", "cbr",
          "-b:v", b, "-maxrate", b, "-bufsize", buf, "-zerolatency", "1",
          "-delay", "0", "-profile:v", "high"] + comum),
        ("AMD AMF", None if origem_gpu else "format=yuv420p",
         ["-c:v", "h264_amf", "-usage", "ultralowlatency", "-quality", "speed",
          "-rc", "cbr", "-b:v", b, "-maxrate", b, "-bufsize", buf,
          "-profile:v", "high"] + comum),
        ("Intel QuickSync",
         "hwmap=derive_device=qsv,format=qsv,vpp_qsv=format=nv12"
         if origem_gpu else "format=nv12",
         ["-c:v", "h264_qsv", "-preset", "veryfast", "-low_delay_brc", "1",
          "-async_depth", "1", "-look_ahead", "0", "-b:v", b, "-maxrate", b,
          "-bufsize", buf, "-profile:v", "high"] + comum),
        ("CPU (x264)", sw,
         ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
          "-b:v", b, "-maxrate", b, "-bufsize", buf, "-profile:v", "high"]
         + comum),
    ]
    return lista


def _entradas(alvo, fps):
    """Fontes de captura: ddagrab (GPU) e gdigrab (compatível)."""
    out = []
    if alvo.get("dxgi") is not None:
        out.append(("ddagrab", True,
                    ["-f", "lavfi", "-i",
                     "ddagrab=output_idx=%d:framerate=%d:draw_mouse=1"
                     % (alvo["dxgi"], fps)]))
    out.append(("gdigrab", False,
                ["-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "1",
                 "-offset_x", str(alvo["x"]), "-offset_y", str(alvo["y"]),
                 "-video_size", "%dx%d" % (alvo["w"], alvo["h"]),
                 "-i", "desktop"]))
    return out


class Sessao:
    """Uma transmissão: inicia o ffmpeg e entrega quadros H.264 por callback."""

    def __init__(self, alvo, fps, kbps, ao_quadro):
        self.alvo = alvo          # dict: x, y, w, h, dxgi
        self.fps = fps
        self.kbps = kbps
        self.ao_quadro = ao_quadro
        self.proc = None
        self.descricao = ""
        self._parar = False

    def _comando(self, entrada, filtro, enc):
        cmd = [caminho_ffmpeg(), "-hide_banner", "-loglevel", "error",
               "-fflags", "nobuffer", "-flags", "low_delay",
               "-probesize", "32", "-analyzeduration", "0"]
        cmd += entrada
        if filtro:
            cmd += ["-vf", filtro]
        cmd += enc
        cmd += ["-an", "-flush_packets", "1", "-flvflags", "no_duration_filesize",
                "-f", "flv", "pipe:1"]
        return cmd

    def iniciar(self):
        global _encoder_ok
        if not caminho_ffmpeg():
            print("[video] ffmpeg não encontrado.")
            return False
        combos = []
        for nome_in, gpu, entrada in _entradas(self.alvo, self.fps):
            for nome_enc, filtro, enc in _encoders(self.kbps, self.fps, gpu):
                combos.append(("%s + %s" % (nome_in, nome_enc), entrada, filtro, enc))
        if _encoder_ok:
            combos.sort(key=lambda c: c[0] != _encoder_ok)
        for desc, entrada, filtro, enc in combos:
            if self._parar:
                return False
            if self._tentar(desc, self._comando(entrada, filtro, enc)):
                _encoder_ok = desc
                self.descricao = desc
                print("[video] usando %s (%dx%d, %d fps, %d kbps)"
                      % (desc, self.alvo["w"], self.alvo["h"], self.fps, self.kbps))
                return True
        print("[video] Nenhum encoder funcionou.")
        return False

    def _tentar(self, desc, cmd):
        flags = 0x08000000 if _WIN else 0  # CREATE_NO_WINDOW
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=flags, bufsize=0)
        except OSError as e:
            print("[video] %s: %s" % (desc, e))
            return False
        primeiro = []
        pronto = threading.Event()

        def ler_inicio():
            try:
                d = p.stdout.read1(65536) if hasattr(p.stdout, "read1") \
                    else os.read(p.stdout.fileno(), 65536)
                if d:
                    primeiro.append(d)
            except OSError:
                pass
            pronto.set()

        threading.Thread(target=ler_inicio, daemon=True).start()
        pronto.wait(6.0)
        if not primeiro:
            erro = b""
            try:
                p.kill()
                erro = p.stderr.read()[-300:]
            except OSError:
                pass
            linha = erro.decode("utf-8", "replace").strip().splitlines()
            print("[video] %s indisponível%s" % (desc, (": " + linha[-1]) if linha else ""))
            return False
        self.proc = p
        threading.Thread(target=self._loop, args=(primeiro[0],), daemon=True).start()
        threading.Thread(target=self._drenar_erros, daemon=True).start()
        return True

    def _drenar_erros(self):
        try:
            for linha in self.proc.stderr:
                t = linha.decode("utf-8", "replace").strip()
                if t:
                    print("[ffmpeg]", t[:200])
        except (OSError, ValueError):
            pass

    def _loop(self, inicial):
        separador = LeitorFLV(self.ao_quadro)
        separador.alimentar(inicial)
        fd = self.proc.stdout.fileno()
        try:
            while not self._parar:
                d = os.read(fd, 262144)
                if not d:
                    break
                separador.alimentar(d)
        except OSError:
            pass
        separador.fim()
        self.ao_quadro(None)  # sinaliza fim

    def parar(self):
        self._parar = True
        p = self.proc
        if p and p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass


class LeitorFLV:
    """Lê o FLV do ffmpeg e entrega cada quadro já em H.264 Annex-B.

    O FLV traz o tamanho de cada quadro, então o quadro sai assim que chega
    (sem esperar o próximo). SPS/PPS vão junto de todo quadro-chave.
    """

    INICIO = b"\x00\x00\x00\x01"

    def __init__(self, saida):
        self.saida = saida
        self.buf = bytearray()
        self.cabecalho = False
        self.config = b""  # SPS+PPS em Annex-B

    def alimentar(self, dados):
        b = self.buf
        b += dados
        if not self.cabecalho:
            if len(b) < 13:
                return
            del b[:13]  # cabeçalho FLV (9) + PreviousTagSize0 (4)
            self.cabecalho = True
        while len(b) >= 11:
            tam = (b[1] << 16) | (b[2] << 8) | b[3]
            total = 11 + tam + 4
            if len(b) < total:
                return
            if b[0] == 9 and tam > 5:  # tag de vídeo
                self._video(bytes(b[11:11 + tam]))
            del b[:total]

    def _video(self, d):
        chave = (d[0] >> 4) == 1
        tipo = d[1]
        corpo = d[5:]
        if tipo == 0:
            self.config = self._avcc(corpo)
            return
        if tipo != 1:
            return
        partes = [self.config] if (chave and self.config) else []
        i = 0
        while i + 4 <= len(corpo):
            n = int.from_bytes(corpo[i:i + 4], "big")
            partes.append(self.INICIO + corpo[i + 4:i + 4 + n])
            i += 4 + n
        if partes:
            self.saida(b"".join(partes))

    def _avcc(self, c):
        """AVCDecoderConfigurationRecord -> SPS/PPS em Annex-B."""
        try:
            out = []
            i = 5
            nsps = c[i] & 0x1F
            i += 1
            for _ in range(nsps):
                n = int.from_bytes(c[i:i + 2], "big")
                out.append(self.INICIO + c[i + 2:i + 2 + n])
                i += 2 + n
            npps = c[i]
            i += 1
            for _ in range(npps):
                n = int.from_bytes(c[i:i + 2], "big")
                out.append(self.INICIO + c[i + 2:i + 2 + n])
                i += 2 + n
            return b"".join(out)
        except IndexError:
            return b""

    def fim(self):
        pass
