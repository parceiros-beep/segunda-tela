"""
Injeção de mouse e teclado no Windows via SendInput (ctypes, sem dependências).
Em sistemas não-Windows vira no-op, para permitir testes do parser.
"""
import sys

_WIN = sys.platform == "win32"

if _WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    # Métricas do desktop virtual (todos os monitores).
    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_VIRTUALDESK = 0x4000

    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004

    ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class _I(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _I)]

    def _send(*inputs):
        n = len(inputs)
        arr = (INPUT * n)(*inputs)
        user32.SendInput(n, arr, ctypes.sizeof(INPUT))

    def _mi(dx, dy, flags, data=0):
        return INPUT(type=INPUT_MOUSE,
                     u=_I(mi=MOUSEINPUT(dx, dy, data, flags, 0, None)))

    def _ki(vk, flags, scan=0):
        return INPUT(type=INPUT_KEYBOARD,
                     u=_I(ki=KEYBDINPUT(vk, scan, flags, 0, None)))

    def _abs(px, py):
        """Converte coordenada de tela (px) em absoluta do desktop virtual."""
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) or 1
        vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) or 1
        ax = int((px - vx) * 65535 / vw)
        ay = int((py - vy) * 65535 / vh)
        return ax, ay

    VK = {
        "ESC": 0x1B, "TAB": 0x09, "ENTER": 0x0D, "BACKSPACE": 0x08,
        "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
        "WIN": 0x5B, "CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10,
        "DELETE": 0x2E, "HOME": 0x24, "END": 0x23, "SPACE": 0x20,
        "C": 0x43, "V": 0x56, "X": 0x58, "A": 0x41, "Z": 0x5A,
    }

    def move(px, py):
        ax, ay = _abs(px, py)
        _send(_mi(ax, ay, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK))

    def left_down(px, py):
        move(px, py)
        _send(_mi(0, 0, MOUSEEVENTF_LEFTDOWN))

    def left_up(px, py):
        _send(_mi(0, 0, MOUSEEVENTF_LEFTUP))

    def right_click(px, py):
        move(px, py)
        _send(_mi(0, 0, MOUSEEVENTF_RIGHTDOWN))
        _send(_mi(0, 0, MOUSEEVENTF_RIGHTUP))

    def wheel(px, py, ticks):
        move(px, py)
        _send(_mi(0, 0, MOUSEEVENTF_WHEEL, data=ticks * 120 & 0xFFFFFFFF))

    def _tap_combo(tokens):
        """Pressiona uma combinação (ex.: CTRL+C) e solta na ordem inversa."""
        vks = []
        for t in tokens:
            vk = VK.get(t.upper())
            if vk is None and len(t) == 1:
                vk = user32.VkKeyScanW(ord(t)) & 0xFF
            if vk:
                vks.append(vk)
        for vk in vks:
            _send(_ki(vk, 0))
        for vk in reversed(vks):
            _send(_ki(vk, KEYEVENTF_KEYUP))

    def key(code):
        _tap_combo(code.split("+"))

    def text(s):
        for ch in s:
            if ch == "\n":
                _send(_ki(VK["ENTER"], 0)); _send(_ki(VK["ENTER"], KEYEVENTF_KEYUP))
                continue
            code = ord(ch)
            _send(_ki(0, KEYEVENTF_UNICODE, scan=code))
            _send(_ki(0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, scan=code))

else:
    # Stubs para testes fora do Windows.
    def move(px, py): pass
    def left_down(px, py): pass
    def left_up(px, py): pass
    def right_click(px, py): pass
    def wheel(px, py, ticks): pass
    def key(code): pass
    def text(s): pass
