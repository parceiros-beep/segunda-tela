"""
Monitores do Windows: listar, ligar em modo estendido, mudar resolução e
posição, e descobrir o índice DXGI (usado pela captura ddagrab do ffmpeg).

Tudo via ctypes (user32 / dxgi), sem dependências. Fora do Windows vira no-op.
"""
import sys

_WIN = sys.platform == "win32"

if _WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    # ---- DPI: coordenadas sempre em pixels físicos ----
    def ativar_dpi():
        try:
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass

    class DISPLAY_DEVICEW(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD),
                    ("DeviceName", wintypes.WCHAR * 32),
                    ("DeviceString", wintypes.WCHAR * 128),
                    ("StateFlags", wintypes.DWORD),
                    ("DeviceID", wintypes.WCHAR * 128),
                    ("DeviceKey", wintypes.WCHAR * 128)]

    class POINTL(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class DEVMODEW(ctypes.Structure):
        _fields_ = [("dmDeviceName", wintypes.WCHAR * 32),
                    ("dmSpecVersion", wintypes.WORD),
                    ("dmDriverVersion", wintypes.WORD),
                    ("dmSize", wintypes.WORD),
                    ("dmDriverExtra", wintypes.WORD),
                    ("dmFields", wintypes.DWORD),
                    ("dmPosition", POINTL),
                    ("dmDisplayOrientation", wintypes.DWORD),
                    ("dmDisplayFixedOutput", wintypes.DWORD),
                    ("dmColor", ctypes.c_short),
                    ("dmDuplex", ctypes.c_short),
                    ("dmYResolution", ctypes.c_short),
                    ("dmTTOption", ctypes.c_short),
                    ("dmCollate", ctypes.c_short),
                    ("dmFormName", wintypes.WCHAR * 32),
                    ("dmLogPixels", wintypes.WORD),
                    ("dmBitsPerPel", wintypes.DWORD),
                    ("dmPelsWidth", wintypes.DWORD),
                    ("dmPelsHeight", wintypes.DWORD),
                    ("dmDisplayFlags", wintypes.DWORD),
                    ("dmDisplayFrequency", wintypes.DWORD),
                    ("dmICMMethod", wintypes.DWORD),
                    ("dmICMIntent", wintypes.DWORD),
                    ("dmMediaType", wintypes.DWORD),
                    ("dmDitherType", wintypes.DWORD),
                    ("dmReserved1", wintypes.DWORD),
                    ("dmReserved2", wintypes.DWORD),
                    ("dmPanningWidth", wintypes.DWORD),
                    ("dmPanningHeight", wintypes.DWORD)]

    ATTACHED = 0x1
    PRIMARY = 0x4
    ENUM_CURRENT_SETTINGS = -1
    DM_POSITION = 0x20
    DM_DISPLAYORIENTATION = 0x80
    DM_PELSWIDTH = 0x80000
    DM_PELSHEIGHT = 0x100000
    DM_DISPLAYFREQUENCY = 0x400000
    CDS_UPDATEREGISTRY = 0x1
    CDS_NORESET = 0x10000000

    user32.ChangeDisplaySettingsExW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(DEVMODEW), wintypes.HWND,
        wintypes.DWORD, ctypes.c_void_p]

    def listar():
        """Lista de dicts: nome (\\\\.\\DISPLAYn), descricao, ativo, primario,
        e x, y, w, h quando ativo."""
        out = []
        i = 0
        while True:
            dd = DISPLAY_DEVICEW()
            dd.cb = ctypes.sizeof(dd)
            if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
                break
            i += 1
            m = {"nome": dd.DeviceName, "descricao": dd.DeviceString,
                 "ativo": bool(dd.StateFlags & ATTACHED),
                 "primario": bool(dd.StateFlags & PRIMARY)}
            dm = DEVMODEW()
            dm.dmSize = ctypes.sizeof(dm)
            if m["ativo"] and user32.EnumDisplaySettingsW(
                    dd.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
                m.update(x=dm.dmPosition.x, y=dm.dmPosition.y,
                         w=dm.dmPelsWidth, h=dm.dmPelsHeight,
                         hz=dm.dmDisplayFrequency)
            out.append(m)
        return out

    def forcar_estender():
        """Topologia ESTENDER (em vez de duplicar). True se aplicou."""
        SDC_APPLY = 0x00000080
        SDC_TOPOLOGY_EXTEND = 0x00000004
        try:
            return user32.SetDisplayConfig(
                0, None, 0, None, SDC_APPLY | SDC_TOPOLOGY_EXTEND) == 0
        except (AttributeError, OSError):
            return False

    def configurar(nome, w, h, hz, x, y):
        """Define resolução, frequência e posição de um monitor. True se ok."""
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(dm)
        user32.EnumDisplaySettingsW(nome, ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
        dm.dmPelsWidth = w
        dm.dmPelsHeight = h
        dm.dmDisplayFrequency = hz
        dm.dmPosition.x = x
        dm.dmPosition.y = y
        dm.dmDisplayOrientation = 0
        dm.dmFields = (DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY
                       | DM_POSITION | DM_DISPLAYORIENTATION)
        r = user32.ChangeDisplaySettingsExW(
            nome, ctypes.byref(dm), None, CDS_UPDATEREGISTRY | CDS_NORESET, None)
        if r != 0:
            # Sem a frequência (alguns drivers recusam a combinação exata).
            dm.dmFields &= ~DM_DISPLAYFREQUENCY
            r = user32.ChangeDisplaySettingsExW(
                nome, ctypes.byref(dm), None, CDS_UPDATEREGISTRY | CDS_NORESET, None)
        user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
        return r == 0

    def desligar(nome):
        """Tira o monitor da área de trabalho (como "Desconectar esta tela")."""
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(dm)
        dm.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT | DM_POSITION
        r = user32.ChangeDisplaySettingsExW(
            nome, ctypes.byref(dm), None, CDS_UPDATEREGISTRY | CDS_NORESET, None)
        user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
        return r == 0

    def tem_modo(nome, w, h):
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(dm)
        i = 0
        while user32.EnumDisplaySettingsW(nome, i, ctypes.byref(dm)):
            if dm.dmPelsWidth == w and dm.dmPelsHeight == h:
                return True
            i += 1
        return False

    # ---- DXGI: índice da saída, como o ffmpeg (ddagrab) enxerga ----
    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class DXGI_OUTPUT_DESC(ctypes.Structure):
        _fields_ = [("DeviceName", wintypes.WCHAR * 32),
                    ("DesktopCoordinates", RECT),
                    ("AttachedToDesktop", wintypes.BOOL),
                    ("Rotation", ctypes.c_uint),
                    ("Monitor", wintypes.HANDLE)]

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    # IID_IDXGIFactory1 {770aae78-f26f-4dba-a829-253c83d1b387}
    _IID_FACTORY1 = GUID(0x770aae78, 0xf26f, 0x4dba,
                         (ctypes.c_ubyte * 8)(0xa8, 0x29, 0x25, 0x3c,
                                              0x83, 0xd1, 0xb3, 0x87))

    def _metodo(obj, indice, restype, *argtypes):
        vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
        return proto(vtbl[indice])

    def _release(obj):
        if obj:
            _metodo(obj, 2, ctypes.c_ulong)(obj)

    def indice_dxgi(nome):
        """Índice da saída `nome` no adaptador 0 (o que o ddagrab usa) ou None."""
        try:
            dxgi = ctypes.WinDLL("dxgi")
        except OSError:
            return None
        fab = ctypes.c_void_p()
        if dxgi.CreateDXGIFactory1(ctypes.byref(_IID_FACTORY1), ctypes.byref(fab)) != 0:
            return None
        try:
            adap = ctypes.c_void_p()
            # IDXGIFactory::EnumAdapters = slot 7
            if _metodo(fab, 7, ctypes.c_long, ctypes.c_uint,
                       ctypes.POINTER(ctypes.c_void_p))(fab, 0, ctypes.byref(adap)) != 0:
                return None
            try:
                i = 0
                while True:
                    out = ctypes.c_void_p()
                    # IDXGIAdapter::EnumOutputs = slot 7
                    if _metodo(adap, 7, ctypes.c_long, ctypes.c_uint,
                               ctypes.POINTER(ctypes.c_void_p))(
                                   adap, i, ctypes.byref(out)) != 0:
                        return None
                    desc = DXGI_OUTPUT_DESC()
                    # IDXGIOutput::GetDesc = slot 7
                    _metodo(out, 7, ctypes.c_long,
                            ctypes.POINTER(DXGI_OUTPUT_DESC))(out, ctypes.byref(desc))
                    _release(out)
                    if desc.DeviceName.lower() == nome.lower():
                        return i
                    i += 1
            finally:
                _release(adap)
        finally:
            _release(fab)

    # ---- Escala (DPI) por monitor: 100%, 125%, ..., como em Configurações ----
    _ESCALAS = [100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500]

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class DC_HEADER(ctypes.Structure):
        _fields_ = [("type", ctypes.c_int32), ("size", ctypes.c_uint32),
                    ("adapterId", LUID), ("id", ctypes.c_uint32)]

    class DC_SOURCE_NAME(ctypes.Structure):
        _fields_ = [("header", DC_HEADER), ("viewGdiDeviceName", wintypes.WCHAR * 32)]

    class DC_DPI_GET(ctypes.Structure):
        _fields_ = [("header", DC_HEADER), ("minScaleRel", ctypes.c_int32),
                    ("curScaleRel", ctypes.c_int32), ("maxScaleRel", ctypes.c_int32)]

    class DC_DPI_SET(ctypes.Structure):
        _fields_ = [("header", DC_HEADER), ("scaleRel", ctypes.c_int32)]

    class DC_PATH_SOURCE(ctypes.Structure):
        _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32),
                    ("modeInfoIdx", ctypes.c_uint32), ("statusFlags", ctypes.c_uint32)]

    class DC_PATH_INFO(ctypes.Structure):
        _fields_ = [("sourceInfo", DC_PATH_SOURCE),
                    ("targetInfo", ctypes.c_byte * 48),
                    ("flags", ctypes.c_uint32)]

    def _escala_atual(x, y, w, h):
        try:
            user32.MonitorFromPoint.restype = ctypes.c_void_p
            hmon = user32.MonitorFromPoint(POINTL(x + w // 2, y + h // 2), 2)
            dx, dy = ctypes.c_uint(), ctypes.c_uint()
            ctypes.windll.shcore.GetDpiForMonitor(ctypes.c_void_p(hmon), 0,
                                                  ctypes.byref(dx), ctypes.byref(dy))
            return round(dx.value * 100 / 96)
        except (AttributeError, OSError):
            return None

    def definir_escala(nome, pct):
        """Muda a escala do Windows (ex.: 200%) no monitor `nome`. True se ok."""
        try:
            np_, nm = ctypes.c_uint32(), ctypes.c_uint32()
            if user32.GetDisplayConfigBufferSizes(2, ctypes.byref(np_), ctypes.byref(nm)):
                return False
            caminhos = (DC_PATH_INFO * np_.value)()
            modos = (ctypes.c_byte * (64 * max(nm.value, 1)))()
            if user32.QueryDisplayConfig(2, ctypes.byref(np_), caminhos,
                                         ctypes.byref(nm), modos, None):
                return False
            m = next((d for d in listar() if d["nome"].lower() == nome.lower()
                      and "w" in d), None)
            if m is None:
                return False
            for c in caminhos[:np_.value]:
                sn = DC_SOURCE_NAME()
                sn.header = DC_HEADER(1, ctypes.sizeof(sn), c.sourceInfo.adapterId,
                                      c.sourceInfo.id)
                if user32.DisplayConfigGetDeviceInfo(ctypes.byref(sn)):
                    continue
                if sn.viewGdiDeviceName.lower() != nome.lower():
                    continue
                g = DC_DPI_GET()
                g.header = DC_HEADER(-3, ctypes.sizeof(g), c.sourceInfo.adapterId,
                                     c.sourceInfo.id)
                if user32.DisplayConfigGetDeviceInfo(ctypes.byref(g)):
                    return False
                atual = _escala_atual(m["x"], m["y"], m["w"], m["h"])
                if atual is None:
                    return False
                idx_atual = min(range(len(_ESCALAS)),
                                key=lambda i: abs(_ESCALAS[i] - atual))
                idx_alvo = min(range(len(_ESCALAS)),
                               key=lambda i: abs(_ESCALAS[i] - pct))
                recomendado = idx_atual - g.curScaleRel
                rel = max(g.minScaleRel, min(g.maxScaleRel, idx_alvo - recomendado))
                if rel == g.curScaleRel:
                    return True
                st = DC_DPI_SET()
                st.header = DC_HEADER(-4, ctypes.sizeof(st), c.sourceInfo.adapterId,
                                      c.sourceInfo.id)
                st.scaleRel = rel
                return user32.DisplayConfigSetDeviceInfo(ctypes.byref(st)) == 0
        except (AttributeError, OSError):
            pass
        return False

    def tamanho_primario():
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

else:
    def ativar_dpi(): pass
    def listar(): return []
    def forcar_estender(): return False
    def configurar(nome, w, h, hz, x, y): return False
    def desligar(nome): return False
    def tem_modo(nome, w, h): return False
    def definir_escala(nome, pct): return False
    def indice_dxgi(nome): return None
    def tamanho_primario(): return 1920, 1080


def primario():
    for m in listar():
        if m["primario"] and "w" in m:
            return m
    return None
