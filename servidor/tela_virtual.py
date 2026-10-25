"""
Tela estendida (monitor virtual) no Windows.

Comportamento parecido com apps de segunda tela: ao pedir tela estendida,
transmitimos um segundo monitor.

Como (sem embutir drivers de terceiros):
  - Se já existe um 2º monitor (real, dummy HDMI, ou um driver de monitor
    virtual já instalado), usamos ele automaticamente.
  - Se só há um monitor, abrimos a página oficial do driver de monitor virtual
    gratuito e mostramos as instruções. O usuário instala uma vez (precisa de
    administrador). Depois disso, a tela estendida passa a funcionar sozinha.
    Enquanto não houver 2º monitor, espelhamos a tela principal.

Devolve o índice do monitor (formato mss) a transmitir.
"""
import webbrowser

LINK_DRIVER = "https://github.com/VirtualDrivers/Virtual-Display-Driver/releases"
_ja_abriu = False


def _contar_monitores(sct):
    return len(sct.monitors) - 1  # [0] é o conjunto de todos


def escolher_monitor_estendido(sct):
    """Devolve (indice_mss, aviso)."""
    global _ja_abriu
    if _contar_monitores(sct) >= 2:
        return _contar_monitores(sct), None  # usa o último como 2ª tela

    aviso = ("Para a TELA ESTENDIDA de verdade é preciso um 2º monitor.\n"
             "  - Opção 1: conecte um monitor ou um dummy HDMI.\n"
             "  - Opção 2: instale o monitor virtual gratuito (1x, como admin):\n"
             "      " + LINK_DRIVER + "\n"
             "Vou abrir a página do driver. Depois de instalar, marque "
             "'tela estendida' no app de novo. Por enquanto, espelhando a tela "
             "principal.")
    if not _ja_abriu:
        _ja_abriu = True
        try:
            webbrowser.open(LINK_DRIVER)
        except Exception:
            pass
    return 1, aviso


def desativar_virtual():
    """Mantido por compatibilidade; nada a desfazer quando não criamos nada."""
    return
