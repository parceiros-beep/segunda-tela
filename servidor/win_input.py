"""
Injeção de entrada no Windows (ctypes, sem dependências):
  - mouse e teclado via SendInput;
  - toque multitoque nativo via InjectTouchInput (gestos do Windows: pinça,
    rolagem, arrastar, menu de contexto ao segurar...);
  - caneta com pressão, inclinação, botão lateral e borracha via
    InjectSyntheticPointerInput (Windows 10 1809+), igual a uma mesa
    digitalizadora.
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
        "PGUP": 0x21, "PGDN": 0x22, "INSERT": 0x2D, "PRTSC": 0x2C,
        "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74,
        "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
        "F11": 0x7A, "F12": 0x7B, "PLUS": 0xBB, "MINUS": 0xBD,
        "LBRACKET": 0xDB, "RBRACKET": 0xDD,
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

    def move_rel(dx, dy):
        """Move o cursor a partir da posição atual (touchpad), em pixels."""
        dx = int(round(dx)); dy = int(round(dy))
        if dx or dy:
            _send(_mi(dx, dy, MOUSEEVENTF_MOVE))

    def clique_aqui(direito):
        """Clique na posição atual do cursor, sem mover."""
        if direito:
            _send(_mi(0, 0, MOUSEEVENTF_RIGHTDOWN))
            _send(_mi(0, 0, MOUSEEVENTF_RIGHTUP))
        else:
            _send(_mi(0, 0, MOUSEEVENTF_LEFTDOWN))
            _send(_mi(0, 0, MOUSEEVENTF_LEFTUP))

    def wheel_aqui(ticks):
        _send(_mi(0, 0, MOUSEEVENTF_WHEEL, data=ticks * 120 & 0xFFFFFFFF))

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


    def key_down(vk):
        _send(_ki(vk, 0))

    def key_up(vk):
        _send(_ki(vk, KEYEVENTF_KEYUP))

    # ---------------------------------------------------- ponteiro (toque/caneta)
    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class POINTER_INFO(ctypes.Structure):
        _fields_ = [("pointerType", ctypes.c_uint32),
                    ("pointerId", ctypes.c_uint32),
                    ("frameId", ctypes.c_uint32),
                    ("pointerFlags", ctypes.c_uint32),
                    ("sourceDevice", wintypes.HANDLE),
                    ("hwndTarget", wintypes.HWND),
                    ("ptPixelLocation", POINT),
                    ("ptHimetricLocation", POINT),
                    ("ptPixelLocationRaw", POINT),
                    ("ptHimetricLocationRaw", POINT),
                    ("dwTime", wintypes.DWORD),
                    ("historyCount", ctypes.c_uint32),
                    ("InputData", ctypes.c_int32),
                    ("dwKeyStates", wintypes.DWORD),
                    ("PerformanceCount", ctypes.c_uint64),
                    ("ButtonChangeType", ctypes.c_int)]

    class POINTER_TOUCH_INFO(ctypes.Structure):
        _fields_ = [("pointerInfo", POINTER_INFO),
                    ("touchFlags", ctypes.c_uint32),
                    ("touchMask", ctypes.c_uint32),
                    ("rcContact", RECT),
                    ("rcContactRaw", RECT),
                    ("orientation", ctypes.c_uint32),
                    ("pressure", ctypes.c_uint32)]

    class POINTER_PEN_INFO(ctypes.Structure):
        _fields_ = [("pointerInfo", POINTER_INFO),
                    ("penFlags", ctypes.c_uint32),
                    ("penMask", ctypes.c_uint32),
                    ("pressure", ctypes.c_uint32),
                    ("rotation", ctypes.c_uint32),
                    ("tiltX", ctypes.c_int32),
                    ("tiltY", ctypes.c_int32)]

    class _PTU(ctypes.Union):
        _fields_ = [("touchInfo", POINTER_TOUCH_INFO),
                    ("penInfo", POINTER_PEN_INFO)]

    class POINTER_TYPE_INFO(ctypes.Structure):
        _fields_ = [("type", ctypes.c_uint32), ("u", _PTU)]

    PT_TOUCH, PT_PEN = 2, 3
    PF_NEW, PF_INRANGE, PF_INCONTACT = 0x1, 0x2, 0x4
    PF_FIRSTBUTTON, PF_SECONDBUTTON = 0x10, 0x20
    PF_PRIMARY, PF_CONFIDENCE = 0x2000, 0x4000
    PF_DOWN, PF_UPDATE, PF_UP = 0x10000, 0x20000, 0x40000
    TOUCH_MASK_CONTACTAREA, TOUCH_MASK_ORIENTATION, TOUCH_MASK_PRESSURE = 1, 2, 4
    PEN_FLAG_BARREL, PEN_FLAG_INVERTED, PEN_FLAG_ERASER = 1, 2, 4
    PEN_MASK_PRESSURE, PEN_MASK_TILT_X, PEN_MASK_TILT_Y = 1, 4, 8

    _touch_pronto = False
    _toques = {}       # id -> (x, y)
    _caneta = None     # HSYNTHETICPOINTERDEVICE
    _caneta_estado = {"contato": False}

    def _iniciar_toque():
        global _touch_pronto
        if not _touch_pronto:
            try:
                _touch_pronto = bool(user32.InitializeTouchInjection(10, 1))
            except AttributeError:
                _touch_pronto = False
        return _touch_pronto

    # Combinações aceitas pelo InjectTouchInput (outras dão ERRO 87):
    T_DOWN = PF_DOWN | PF_INRANGE | PF_INCONTACT
    T_MOVE = PF_UPDATE | PF_INRANGE | PF_INCONTACT
    T_UP = PF_UP
    _modo_mouse = {"ativo": False, "dedo": None}

    def _info_toque(pid, x, y, flags):
        t = POINTER_TOUCH_INFO()
        t.pointerInfo.pointerType = PT_TOUCH
        t.pointerInfo.pointerId = pid
        t.pointerInfo.pointerFlags = flags
        t.pointerInfo.ptPixelLocation = POINT(x, y)
        t.touchFlags = 0
        t.touchMask = TOUCH_MASK_CONTACTAREA | TOUCH_MASK_ORIENTATION | TOUCH_MASK_PRESSURE
        t.rcContact = RECT(x - 2, y - 2, x + 2, y + 2)
        t.orientation = 90
        t.pressure = 512  # faixa válida: 0..1024
        return t

    def _injetar_toques(lista):
        if not lista:
            return True
        arr = (POINTER_TOUCH_INFO * len(lista))(*lista)
        if user32.InjectTouchInput(len(lista), arr):
            return True
        erro = ctypes.get_last_error()
        print("[toque] Windows recusou o toque (erro %d)." % erro)
        return False

    def _virar_mouse(motivo):
        if not _modo_mouse["ativo"]:
            _modo_mouse["ativo"] = True
            print("[toque] %s -> usando o toque como mouse." % motivo)

    def _toque_como_mouse(acao, pid, x, y):
        """Plano B: o 1º dedo vira o mouse (tocar = clicar, arrastar = arrastar)."""
        dedo = _modo_mouse["dedo"]
        if acao == "d" and dedo is None:
            _modo_mouse["dedo"] = pid
            left_down(x, y)
        elif acao == "m" and dedo == pid:
            move(x, y)
        elif acao == "u" and dedo == pid:
            move(x, y)
            left_up(x, y)
            _modo_mouse["dedo"] = None

    def touch(acao, pid, x, y):
        """acao: 'd' (encostou), 'm' (moveu), 'u' (soltou). Coords em pixels."""
        pid = int(pid) % 10
        if _modo_mouse["ativo"]:
            _toque_como_mouse(acao, pid, x, y)
            return True
        if not _iniciar_toque():
            _virar_mouse("Toque nativo indisponível neste Windows")
            _toque_como_mouse(acao, pid, x, y)
            return True
        lista = [_info_toque(oid, ox, oy, T_MOVE)
                 for oid, (ox, oy) in _toques.items() if oid != pid]
        if acao == "d":
            if pid in _toques:  # nunca recebeu o "u": solta antes
                ox, oy = _toques.pop(pid)
                _injetar_toques([_info_toque(pid, ox, oy, T_UP)])
                lista = [_info_toque(oid, ox2, oy2, T_MOVE)
                         for oid, (ox2, oy2) in _toques.items()]
            _toques[pid] = (x, y)
            f = T_DOWN
        elif acao == "m":
            if pid not in _toques:
                return True
            _toques[pid] = (x, y)
            f = T_MOVE
        else:
            if pid not in _toques:
                return True
            _toques.pop(pid)
            f = T_UP
        lista.append(_info_toque(pid, x, y, f))
        if not _injetar_toques(lista):
            _toques.clear()
            _virar_mouse("Toque nativo falhou")
            if acao == "d":
                _toque_como_mouse("d", pid, x, y)
        return True

    def touch_move_varios(pontos):
        """Atualiza vários dedos num único quadro: [(id, x, y), ...]."""
        if _modo_mouse["ativo"]:
            for pid, x, y in pontos:
                _toque_como_mouse("m", int(pid) % 10, x, y)
            return
        if not _toques:
            return
        for pid, x, y in pontos:
            if int(pid) % 10 in _toques:
                _toques[int(pid) % 10] = (x, y)
        lista = [_info_toque(oid, ox, oy, T_MOVE) for oid, (ox, oy) in _toques.items()]
        if not _injetar_toques(lista):
            _toques.clear()
            _virar_mouse("Toque nativo falhou")

    def touch_reset():
        if _modo_mouse["dedo"] is not None:
            _modo_mouse["dedo"] = None
            _send(_mi(0, 0, MOUSEEVENTF_LEFTUP))
        lista = [_info_toque(oid, ox, oy, T_UP) for oid, (ox, oy) in _toques.items()]
        _toques.clear()
        if lista and _touch_pronto:
            arr = (POINTER_TOUCH_INFO * len(lista))(*lista)
            user32.InjectTouchInput(len(lista), arr)

    def _iniciar_caneta():
        global _caneta
        if _caneta is None:
            try:
                user32.CreateSyntheticPointerDevice.restype = wintypes.HANDLE
                h = user32.CreateSyntheticPointerDevice(PT_PEN, 1, 1)
                _caneta = h or 0
            except AttributeError:
                _caneta = 0
            if not _caneta:
                print("[caneta] Windows sem suporte a caneta sintética "
                      "(precisa do Windows 10 1809 ou mais novo).")
        return _caneta

    def pen(estado, x, y, pressao, tilt_x, tilt_y, botoes):
        """estado: h (pairando), d (encostou), m (arrastando), u (levantou),
        x (saiu do alcance). pressao 0..1, tilt em graus, botoes: bit0 lateral,
        bit1 borracha."""
        global _caneta
        dev = _iniciar_caneta()
        if not dev:
            # Sem caneta sintética: vira mouse.
            if estado == "d":
                left_down(x, y)
            elif estado in ("m", "h"):
                move(x, y)
            elif estado == "u":
                left_up(x, y)
            return
        info = POINTER_TYPE_INFO()
        info.type = PT_PEN
        p = info.u.penInfo
        p.pointerInfo.pointerType = PT_PEN
        p.pointerInfo.pointerId = 0
        p.pointerInfo.ptPixelLocation = POINT(x, y)
        borracha = bool(botoes & 2)
        lateral = bool(botoes & 1)
        p.penFlags = (PEN_FLAG_BARREL if lateral else 0) | \
                     ((PEN_FLAG_ERASER | PEN_FLAG_INVERTED) if borracha else 0)
        p.penMask = PEN_MASK_PRESSURE | PEN_MASK_TILT_X | PEN_MASK_TILT_Y
        p.tiltX = max(-90, min(90, int(tilt_x)))
        p.tiltY = max(-90, min(90, int(tilt_y)))
        contato = _caneta_estado["contato"]
        botao = 0  # botão lateral vai em penFlags (BARREL)
        flags = PF_UPDATE | PF_INRANGE
        if estado == "d":
            if contato:
                estado = "m"
            else:
                flags = PF_DOWN | PF_INRANGE | PF_INCONTACT | botao
                _caneta_estado["contato"] = True
        if estado == "m":
            if not contato and not _caneta_estado["contato"]:
                flags = PF_DOWN | PF_INRANGE | PF_INCONTACT | botao
                _caneta_estado["contato"] = True
            else:
                flags = PF_UPDATE | PF_INRANGE | PF_INCONTACT | botao
        elif estado == "u":
            flags = PF_UP | PF_INRANGE
            _caneta_estado["contato"] = False
        elif estado == "h":
            if contato:
                flags = PF_UP | PF_INRANGE
                _caneta_estado["contato"] = False
            else:
                flags = PF_UPDATE | PF_INRANGE
        elif estado == "x":
            if contato:
                p.pointerInfo.pointerFlags = PF_UP | PF_INRANGE
                p.pressure = 0
                user32.InjectSyntheticPointerInput(dev, ctypes.byref(info), 1)
                _caneta_estado["contato"] = False
            flags = PF_UPDATE
        p.pointerInfo.pointerFlags = flags
        p.pressure = int(max(0.0, min(1.0, pressao)) * 1024) if flags & PF_INCONTACT else 0
        ok = user32.InjectSyntheticPointerInput(dev, ctypes.byref(info), 1)
        if not ok and estado != "x":  # saída do alcance pode falhar sem problema
            print("[caneta] Windows recusou a caneta (erro %d) -> usando como mouse."
                  % ctypes.get_last_error())
            _caneta = 0
            _caneta_estado["contato"] = False
            if estado == "d":
                left_down(x, y)

else:
    # Stubs para testes fora do Windows.
    def move(px, py): pass
    def left_down(px, py): pass
    def left_up(px, py): pass
    def right_click(px, py): pass
    def wheel(px, py, ticks): pass
    def move_rel(dx, dy): pass
    def clique_aqui(direito): pass
    def wheel_aqui(ticks): pass
    def key(code): pass
    def text(s): pass
    def key_down(vk): pass
    def key_up(vk): pass
    def touch(acao, pid, x, y): return True
    def touch_move_varios(pontos): pass
    def touch_reset(): pass
    def pen(estado, x, y, pressao, tilt_x, tilt_y, botoes): pass
