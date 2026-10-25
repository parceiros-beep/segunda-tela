"""
Tela estendida (monitor virtual) no Windows.

Estratégia honesta e segura:
  - NÃO instala driver em silêncio (isso exige administrador e é escolha do
    usuário). Em vez disso, DETECTA se já existe um segundo monitor (real,
    um "dummy plug" HDMI, ou um driver de monitor virtual já instalado) e usa
    ele como a segunda tela.
  - Se só houver um monitor, explica como adicionar um monitor virtual (driver
    gratuito e de código aberto), e o servidor segue espelhando a tela
    principal até o usuário instalar.

Retorna o índice do monitor (no formato do mss) que deve ser transmitido.
"""
import webbrowser

LINK_DRIVER = "https://github.com/VirtualDrivers/Virtual-Display-Driver/releases"


def escolher_monitor_estendido(sct):
    """sct.monitors: [0]=tudo, [1]=principal, [2..]=secundários.
    Devolve (indice, mensagem). indice=1 (principal) se não houver segundo."""
    reais = sct.monitors[1:]
    if len(reais) >= 2:
        # Usa o último monitor como "segunda tela".
        return len(reais), None
    msg = ("Só encontrei um monitor. Para a TELA ESTENDIDA de verdade, instale "
           "um monitor virtual (gratuito):\n  " + LINK_DRIVER +
           "\nDepois de instalar, marque 'tela estendida' no app de novo. "
           "Por enquanto vou espelhar a tela principal.")
    return 1, msg


def abrir_link_driver():
    try:
        webbrowser.open(LINK_DRIVER)
    except Exception:
        pass
