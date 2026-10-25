"""
Ajustes de vídeo do Windows para a tela estendida.

- forcar_estender(): troca a topologia dos monitores para ESTENDER (em vez de
  duplicar/clonar). Resolve o caso comum "tenho 2 monitores mas aparece a mesma
  imagem nos dois". Usa SetDisplayConfig (não precisa de administrador).
"""
import sys

_WIN = sys.platform == "win32"


def forcar_estender():
    """Coloca o Windows em modo estendido. True se aplicou."""
    if not _WIN:
        return False
    import ctypes
    SDC_APPLY = 0x00000080
    SDC_TOPOLOGY_EXTEND = 0x00000004
    try:
        r = ctypes.windll.user32.SetDisplayConfig(
            0, None, 0, None, SDC_APPLY | SDC_TOPOLOGY_EXTEND)
        return r == 0  # ERROR_SUCCESS
    except Exception as e:
        print("Não consegui mudar para modo estendido:", e)
        return False
