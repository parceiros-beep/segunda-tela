"""
Som do PC no tablet: captura o que está tocando no Windows (WASAPI em modo
"loopback", sem precisar de "Mixagem estéreo") e envia PCM 16 bits,
48 kHz, estéreo. O app toca com AudioTrack em modo de baixa latência.

Sem as bibliotecas (soundcard + numpy), disponivel() devolve False e o
servidor responde 503 a quem pedir o som.
"""
import sys

_WIN = sys.platform == "win32"
TAXA = 48000
CANAIS = 2
BLOCO = 480  # 10 ms por pacote


def disponivel():
    try:
        import importlib
        importlib.import_module("numpy")
        importlib.import_module("soundcard")
        return True
    except Exception:  # a importação pode falhar de várias formas no Windows
        return False


def transmitir(sock, continuar):
    """Envia o som até continuar() devolver False ou o tablet desconectar."""
    if _WIN:
        import ctypes
        # A captura usa COM; cada thread precisa inicializar.
        ctypes.windll.ole32.CoInitializeEx(None, 0)
    import numpy as np
    import soundcard as sc
    alto_falante = sc.default_speaker()
    print("[som] Enviando o som de: %s" % alto_falante.name)
    mic = sc.get_microphone(id=str(alto_falante.name), include_loopback=True)
    with mic.recorder(samplerate=TAXA, channels=CANAIS, blocksize=BLOCO) as rec:
        while continuar():
            dados = rec.record(numframes=BLOCO)
            pcm = (np.clip(dados, -1.0, 1.0) * 32767).astype("<i2").tobytes()
            sock.sendall(pcm)
