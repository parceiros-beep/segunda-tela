"""
Vídeo de baixa latência (H.264 ou H.265) com o ffmpeg embutido no .exe.

Captura: ddagrab (Desktop Duplication, na GPU) -> encoder de hardware
(NVIDIA NVENC, AMD AMF, Intel QuickSync). Se nada disso existir, cai para
gdigrab + x264/x265 (CPU). O ffmpeg entrega FLV (cada quadro com tamanho;
H.265 no "FLV estendido") e aqui viram quadros Annex-B para o MediaCodec.

Tudo é configurável pelo app (Opcoes): codec, bitrate, modo de taxa
(CBR/VBR/qualidade constante), velocidade do encoder, intervalo de
quadro-chave, atualização intra e cursor.
"""
import os
import shutil
import subprocess
import sys
import threading

_WIN = sys.platform == "win32"
_encoder_ok = {}  # codec -> 1ª combinação que funcionou


def caminho_ffmpeg():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for c in (os.path.join(base, "ffmpeg.exe"), os.path.join(base, "ffmpeg")):
        if os.path.isfile(c):
            return c
    return shutil.which("ffmpeg")


class Opcoes:
    """Ajustes de codificação vindos do app (todos com padrão seguro)."""

    def __init__(self, fps=60, kbps=20000, codec="h264", taxa="cbr", cq=23,
                 vel="rapida", gop=2.0, intra=False, cursor=True):
        self.fps = fps
        self.kbps = kbps
        self.codec = codec if codec in ("h264", "h265") else "h264"
        self.taxa = taxa if taxa in ("cbr", "vbr", "cq") else "cbr"
        self.cq = max(10, min(51, int(cq)))
        self.vel = vel if vel in ("rapida", "equilibrada", "qualidade") else "rapida"
        self.gop = max(0.5, min(30.0, float(gop)))
        self.intra = bool(intra)
        self.cursor = bool(cursor)

    def resumo(self):
        taxa = {"cbr": "CBR", "vbr": "VBR", "cq": "qualidade %d" % self.cq}[self.taxa]
        return "%s, %d fps, %d Mbps %s, %s" % (
            self.codec.upper().replace("H", "H."), self.fps,
            self.kbps // 1000, taxa, self.vel)


def _taxa_args(o, familia):
    """Argumentos de controle de taxa por família de encoder."""
    b = "%dk" % o.kbps
    pico = "%dk" % int(o.kbps * (1.0 if o.taxa == "cbr" else 1.5))
    # Buffer pequeno = latência baixa; VBR/CQ ganham folga para picos.
    quadros = 2 if o.taxa == "cbr" else 6
    buf = "%dk" % max(o.kbps // max(o.fps, 1) * quadros, 200)
    if familia == "nvenc":
        if o.taxa == "cbr":
            return ["-rc", "cbr", "-b:v", b, "-maxrate", b, "-bufsize", buf]
        if o.taxa == "vbr":
            return ["-rc", "vbr", "-b:v", b, "-maxrate", pico, "-bufsize", buf]
        return ["-rc", "vbr", "-cq", str(o.cq), "-b:v", "0",
                "-maxrate", pico, "-bufsize", buf]
    if familia == "amf":
        if o.taxa == "cbr":
            return ["-rc", "cbr", "-b:v", b, "-maxrate", b, "-bufsize", buf]
        if o.taxa == "vbr":
            return ["-rc", "vbr_peak", "-b:v", b, "-maxrate", pico, "-bufsize", buf]
        return ["-rc", "cqp", "-qp_i", str(o.cq), "-qp_p", str(o.cq)]
    if familia == "qsv":
        if o.taxa == "cbr":
            return ["-b:v", b, "-maxrate", b, "-bufsize", buf, "-low_delay_brc", "1"]
        if o.taxa == "vbr":
            return ["-b:v", b, "-maxrate", pico, "-bufsize", buf, "-low_delay_brc", "1"]
        return ["-global_quality", str(o.cq)]
    # x264 / x265
    if o.taxa == "cbr":
        return ["-b:v", b, "-maxrate", b, "-bufsize", buf]
    if o.taxa == "vbr":
        return ["-b:v", b, "-maxrate", pico, "-bufsize", buf]
    return ["-crf", str(o.cq), "-maxrate", pico, "-bufsize", buf]


def _encoders(o, codec, origem_gpu):
    """Lista de (nome, filtro, args do encoder) na ordem de preferência."""
    hevc = codec == "h265"
    gop = str(max(1, int(o.fps * o.gop)))
    comum = ["-g", gop, "-bf", "0"]
    sw = "hwdownload,format=bgra,format=yuv420p" if origem_gpu else "format=yuv420p"
    perfil = ["-profile:v", "main" if hevc else "high"]
    nv_preset = {"rapida": "p1", "equilibrada": "p3", "qualidade": "p5"}[o.vel]
    nv_tune = "ull" if o.vel == "rapida" else "ll"
    amf_q = {"rapida": "speed", "equilibrada": "balanced", "qualidade": "quality"}[o.vel]
    qsv_p = {"rapida": "veryfast", "equilibrada": "faster", "qualidade": "medium"}[o.vel]
    x_p = {"rapida": "ultrafast", "equilibrada": "superfast", "qualidade": "veryfast"}[o.vel]

    nv = ["-c:v", "hevc_nvenc" if hevc else "h264_nvenc", "-preset", nv_preset,
          "-tune", nv_tune, "-zerolatency", "1", "-delay", "0"]
    nv += _taxa_args(o, "nvenc") + perfil + comum
    if o.intra:
        nv += ["-intra-refresh", "1", "-forced-idr", "1"]

    amf = ["-c:v", "hevc_amf" if hevc else "h264_amf",
           "-usage", "ultralowlatency" if o.vel == "rapida" else "lowlatency",
           "-quality", amf_q]
    amf += _taxa_args(o, "amf") + perfil + comum

    qsv = ["-c:v", "hevc_qsv" if hevc else "h264_qsv", "-preset", qsv_p,
           "-async_depth", "1", "-look_ahead", "0"]
    qsv += _taxa_args(o, "qsv") + perfil + comum
    if o.intra and not hevc:
        qsv += ["-int_ref_type", "vertical"]

    if hevc:
        cpu = ["-c:v", "libx265", "-preset", x_p, "-tune", "zerolatency"]
        cpu += _taxa_args(o, "x") + perfil + comum
        cpu += ["-x265-params", "log-level=error" + (":intra-refresh=1" if o.intra else "")]
        nome_cpu = "CPU (x265)"
    else:
        cpu = ["-c:v", "libx264", "-preset", x_p, "-tune", "zerolatency"]
        cpu += _taxa_args(o, "x") + perfil + comum
        if o.intra:
            cpu += ["-intra-refresh", "1"]
        nome_cpu = "CPU (x264)"

    return [
        ("NVIDIA NVENC", None if origem_gpu else "format=yuv420p", nv),
        ("AMD AMF", None if origem_gpu else "format=yuv420p", amf),
        ("Intel QuickSync",
         "hwmap=derive_device=qsv,format=qsv,vpp_qsv=format=nv12"
         if origem_gpu else "format=nv12", qsv),
        (nome_cpu, sw, cpu),
    ]


def _entradas(alvo, o):
    """Fontes de captura: ddagrab (GPU) e gdigrab (compatível)."""
    out = []
    mouse = "1" if o.cursor else "0"
    if alvo.get("dxgi") is not None:
        out.append(("ddagrab", True,
                    ["-f", "lavfi", "-i",
                     "ddagrab=output_idx=%d:framerate=%d:draw_mouse=%s"
                     % (alvo["dxgi"], o.fps, mouse)]))
    out.append(("gdigrab", False,
                ["-f", "gdigrab", "-framerate", str(o.fps), "-draw_mouse", mouse,
                 "-offset_x", str(alvo["x"]), "-offset_y", str(alvo["y"]),
                 "-video_size", "%dx%d" % (alvo["w"], alvo["h"]),
                 "-i", "desktop"]))
    return out


class Sessao:
    """Uma transmissão: inicia o ffmpeg e entrega quadros por callback."""

    def __init__(self, alvo, opcoes, ao_quadro):
        self.alvo = alvo          # dict: x, y, w, h, dxgi
        self.o = opcoes
        self.ao_quadro = ao_quadro
        self.proc = None
        self.descricao = ""
        self.codec = opcoes.codec  # codec que de fato ficou ativo
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
        if not caminho_ffmpeg():
            print("[video] ffmpeg não encontrado.")
            return False
        # H.265 pedido: tenta H.265 em todos os encoders; senão cai para H.264.
        codecs = ["h265", "h264"] if self.o.codec == "h265" else ["h264"]
        for codec in codecs:
            combos = []
            for nome_in, gpu, entrada in _entradas(self.alvo, self.o):
                for nome_enc, filtro, enc in _encoders(self.o, codec, gpu):
                    combos.append(("%s + %s" % (nome_in, nome_enc), entrada, filtro, enc))
            ok = _encoder_ok.get(codec)
            if ok:
                combos.sort(key=lambda c: c[0] != ok)
            for desc, entrada, filtro, enc in combos:
                if self._parar:
                    return False
                rotulo = "%s %s" % (desc, "H.265" if codec == "h265" else "H.264")
                if self._tentar(rotulo, self._comando(entrada, filtro, enc), codec):
                    _encoder_ok[codec] = desc
                    print("[video] usando %s (%dx%d; %s)"
                          % (self.descricao, self.alvo["w"], self.alvo["h"], self.o.resumo()))
                    return True
            if codec == "h265":
                print("[video] H.265 indisponível neste PC; usando H.264.")
        print("[video] Nenhum encoder funcionou.")
        return False

    def _tentar(self, desc, cmd, codec):
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
        # Definidos antes dos quadros saírem: o 1º quadro já leva o codec certo.
        self.codec = codec
        self.descricao = desc
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
        if d[0] & 0x80:            # FLV estendido (H.265)
            self._video_ex(d)
            return
        chave = (d[0] >> 4) == 1
        tipo = d[1]
        corpo = d[5:]
        if tipo == 0:
            self.config = self._avcc(corpo)
            return
        if tipo != 1:
            return
        self._quadro(chave, corpo)

    def _video_ex(self, d):
        chave = ((d[0] >> 4) & 0x07) == 1
        tipo = d[0] & 0x0F
        if tipo == 0:              # SequenceStart: HEVCDecoderConfigurationRecord
            self.config = self._hvcc(d[5:])
        elif tipo == 1:            # CodedFrames (com composition time)
            self._quadro(chave, d[8:])
        elif tipo == 3:            # CodedFramesX
            self._quadro(chave, d[5:])

    def _quadro(self, chave, corpo):
        partes = [self.config] if (chave and self.config) else []
        i = 0
        while i + 4 <= len(corpo):
            n = int.from_bytes(corpo[i:i + 4], "big")
            partes.append(self.INICIO + corpo[i + 4:i + 4 + n])
            i += 4 + n
        if partes:
            self.saida(b"".join(partes))

    def _hvcc(self, c):
        """HEVCDecoderConfigurationRecord -> VPS/SPS/PPS em Annex-B."""
        try:
            out = []
            narr = c[22]
            i = 23
            for _ in range(narr):
                n = int.from_bytes(c[i + 1:i + 3], "big")
                i += 3
                for _ in range(n):
                    tam = int.from_bytes(c[i:i + 2], "big")
                    out.append(self.INICIO + c[i + 2:i + 2 + tam])
                    i += 2 + tam
            return b"".join(out)
        except IndexError:
            return b""

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
