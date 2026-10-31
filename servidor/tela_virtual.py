"""
Monitor virtual (tela estendida de verdade, como no Duet Display).

Usa o Virtual Display Driver (código aberto, MIT, assinado):
https://github.com/VirtualDrivers/Virtual-Display-Driver

Fluxo:
  1. instalar_se_preciso(): na 1ª vez, pede permissão de administrador e
     instala o driver que vem embutido no .exe (pasta "drivers").
  2. ativar(w, h, hz, lado): grava a resolução do tablet no vdd_settings.xml,
     liga 1 monitor virtual, coloca à esquerda/direita do principal e devolve
     os dados do monitor (nome \\\\.\\DISPLAYn, x, y, w, h).
  3. desativar(): tira o monitor da área de trabalho (as janelas voltam
     para a tela do PC). O driver continua instalado.
"""
import base64
import os
import shutil
import subprocess
import sys
import time

import win_display

_WIN = sys.platform == "win32"
DIR_CONF = r"C:\VirtualDisplayDriver"
PIPE = r"\\.\pipe\MTTVirtualDisplayPipe"
HWID = r"Root\MttVDD"
DESCRICAO = "virtual display"  # trecho do DeviceString do adaptador

_ativo = False
_nome = ""


def _pasta_embutida():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "drivers")


# ---------------------------------------------------------------- pipe
def _pipe_existe():
    if not _WIN:
        return False
    import ctypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if k32.WaitNamedPipeW(PIPE, 1):
        return True
    return ctypes.get_last_error() == 121  # ERROR_SEM_TIMEOUT: existe, ocupado


def _comando(cmd, ler=False):
    """Envia um comando ao driver pelo named pipe (texto UTF-16)."""
    if not _WIN:
        return None
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    for _ in range(20):
        h = k32.CreateFileW(PIPE, 0xC0000000, 0, None, 3, 0, None)
        if h and h != wintypes.HANDLE(-1).value:
            break
        k32.WaitNamedPipeW(PIPE, 500)
    else:
        return None
    try:
        dados = cmd.encode("utf-16-le")
        n = wintypes.DWORD()
        k32.WriteFile(h, dados, len(dados), ctypes.byref(n), None)
        if ler:
            buf = ctypes.create_string_buffer(512)
            if k32.ReadFile(h, buf, 510, ctypes.byref(n), None):
                return buf.raw[:n.value].decode("utf-16-le", "ignore").strip("\0")
        return ""
    finally:
        k32.CloseHandle(h)


def instalado():
    return _pipe_existe() or _monitor_virtual(apenas_ativo=False) is not None


# ---------------------------------------------------------------- instalação
def instalar_se_preciso():
    """Garante o driver. Pede administrador (UAC) só na primeira vez."""
    if not _WIN or instalado():
        return True
    if not os.path.isdir(_pasta_embutida()):
        print("[tela estendida] Driver não veio junto com o servidor.")
        return False
    print("[tela estendida] Instalando o monitor virtual (1ª vez)...")
    print("                 Aceite o aviso de administrador do Windows.")
    import ctypes
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, "--instalar-driver"
    else:
        exe = sys.executable
        params = '"%s" --instalar-driver' % os.path.abspath(sys.argv[0])
    from ctypes import wintypes as w
    SEE_MASK_NOCLOSEPROCESS = 0x40

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", w.DWORD), ("fMask", ctypes.c_ulong),
                    ("hwnd", w.HWND), ("lpVerb", w.LPCWSTR),
                    ("lpFile", w.LPCWSTR), ("lpParameters", w.LPCWSTR),
                    ("lpDirectory", w.LPCWSTR), ("nShow", ctypes.c_int),
                    ("hInstApp", w.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                    ("lpClass", w.LPCWSTR), ("hkeyClass", w.HKEY),
                    ("dwHotKey", w.DWORD), ("hIcon", w.HANDLE),
                    ("hProcess", w.HANDLE)]

    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "runas"
    sei.lpFile = exe
    sei.lpParameters = params
    sei.nShow = 1
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)):
        print("[tela estendida] Permissão de administrador negada.")
        return False
    ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, 180000)
    ctypes.windll.kernel32.CloseHandle(sei.hProcess)
    for _ in range(30):
        if instalado():
            print("[tela estendida] Monitor virtual instalado.")
            return True
        time.sleep(1)
    print("[tela estendida] O driver não respondeu. Reinicie o PC e tente de novo.")
    return False


def instalar_driver_admin():
    """Executado no processo elevado (--instalar-driver)."""
    origem = _pasta_embutida()
    os.makedirs(DIR_CONF, exist_ok=True)
    for nome in os.listdir(origem):
        src = os.path.join(origem, nome)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(DIR_CONF, nome))
    escrever_config(1920, 1080, 60, contagem=1)
    # Usuários e o serviço do driver precisam poder gravar o XML.
    for sid in ("*S-1-5-32-545", "*S-1-5-19", "*S-1-1-0"):
        subprocess.run(["icacls", DIR_CONF, "/grant", sid + ":(OI)(CI)M", "/T", "/Q"],
                       capture_output=True)
    inf = os.path.join(DIR_CONF, "MttVDD.inf")
    cat = os.path.join(DIR_CONF, "mttvdd.cat")
    # Certificado do catálogo -> Editores Confiáveis (instalação silenciosa).
    ps = (
        "$c=New-Object System.Security.Cryptography.X509Certificates."
        "X509Certificate2Collection;$c.Import('%s');"
        "foreach($x in $c){$s=New-Object System.Security.Cryptography."
        "X509Certificates.X509Store('TrustedPublisher','LocalMachine');"
        "$s.Open('ReadWrite');$s.Add($x);$s.Close()}" % cat)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-EncodedCommand",
                    base64.b64encode(ps.encode("utf-16-le")).decode()],
                   capture_output=True)
    nefcon = os.path.join(DIR_CONF, "nefconw.exe")
    r = subprocess.run([nefcon, "install", inf, HWID], capture_output=True)
    print("nefcon:", r.returncode)
    # Registro do caminho de configuração lido pelo driver.
    subprocess.run(["reg", "add", r"HKLM\SOFTWARE\MikeTheTech\VirtualDisplayDriver",
                    "/v", "VDDPATH", "/t", "REG_SZ", "/d", DIR_CONF, "/f"],
                   capture_output=True)
    time.sleep(5)
    for _ in range(10):
        if _monitor_virtual() is not None:
            break
        time.sleep(1)
    recolher()
    return r.returncode == 0


def desinstalar_driver_admin():
    nefcon = os.path.join(DIR_CONF, "nefconw.exe")
    subprocess.run([nefcon, "--remove-device-node", "--hardware-id", HWID,
                    "--class-guid", "4d36e968-e325-11ce-bfc1-08002be10318"],
                   capture_output=True)


# ---------------------------------------------------------------- config
_XML = """<?xml version='1.0' encoding='utf-8'?>
<vdd_settings>
    <monitors><count>{count}</count></monitors>
    <gpu><friendlyname>default</friendlyname></gpu>
    <global>
        <g_refresh_rate>60</g_refresh_rate>
        <g_refresh_rate>{hz}</g_refresh_rate>
    </global>
    <resolutions>
{res}
    </resolutions>
    <logging>
        <SendLogsThroughPipe>false</SendLogsThroughPipe>
        <logging>false</logging>
        <debuglogging>false</debuglogging>
    </logging>
    <colour>
        <SDR10bit>false</SDR10bit>
        <HDRPlus>false</HDRPlus>
        <ColourFormat>RGB</ColourFormat>
    </colour>
    <cursor>
        <HardwareCursor>false</HardwareCursor>
        <CursorMaxX>128</CursorMaxX>
        <CursorMaxY>128</CursorMaxY>
        <AlphaCursorSupport>true</AlphaCursorSupport>
        <XorCursorSupportLevel>2</XorCursorSupportLevel>
    </cursor>
    <edid>
        <CustomEdid>false</CustomEdid>
        <PreventSpoof>false</PreventSpoof>
        <EdidCeaOverride>false</EdidCeaOverride>
    </edid>
</vdd_settings>
"""


def escrever_config(w, h, hz, contagem=1):
    # A resolução do tablet vem primeiro (preferida); outras de reserva.
    lista = [(w, h)]
    for r in ((1920, 1080), (1920, 1200), (2560, 1600), (1280, 800)):
        if r not in lista:
            lista.append(r)
    res = "\n".join(
        "        <resolution><width>%d</width><height>%d</height>"
        "<refresh_rate>%d</refresh_rate></resolution>" % (a, b, hz)
        for a, b in lista)
    with open(os.path.join(DIR_CONF, "vdd_settings.xml"), "w", encoding="utf-8") as f:
        f.write(_XML.format(count=contagem, hz=hz, res=res))


# ---------------------------------------------------------------- uso
def _monitor_virtual(apenas_ativo=True):
    for m in win_display.listar():
        if DESCRICAO in m["descricao"].lower() and (m["ativo"] or not apenas_ativo):
            return m
    return None


def _config_desatualizada():
    """Instalações antigas usavam cursor por hardware: o cursor não entrava
    na imagem capturada e sumia no tablet. Precisa regravar e recarregar."""
    try:
        with open(os.path.join(DIR_CONF, "vdd_settings.xml"), encoding="utf-8") as f:
            return "<HardwareCursor>true" in f.read()
    except OSError:
        return False


def ativar(w, h, hz=60, lado="direita"):
    """Liga o monitor virtual no tamanho do tablet. Devolve dict ou None."""
    global _ativo, _nome
    if not _WIN:
        return None
    if not instalar_se_preciso():
        return None
    mon = _monitor_virtual(apenas_ativo=False)
    if (mon is None or not win_display.tem_modo(mon["nome"], w, h)
            or _config_desatualizada()):
        # Resolução nova: grava no XML e recarrega o driver.
        try:
            escrever_config(w, h, hz, contagem=1)
        except OSError as e:
            print("[tela estendida] Não consegui gravar a configuração:", e)
        _comando("RELOAD_DRIVER")
        for _ in range(60):
            time.sleep(0.25)
            mon = _monitor_virtual(apenas_ativo=False)
            if mon is not None and win_display.tem_modo(mon["nome"], w, h):
                break
    if mon is None:
        win_display.forcar_estender()
        time.sleep(1.0)
        mon = _monitor_virtual(apenas_ativo=False)
    if mon is None:
        print("[tela estendida] O monitor virtual não apareceu no Windows.")
        return None
    pw, ph = win_display.tamanho_primario()
    if lado == "esquerda":
        x, y = -w, max(0, (ph - h) // 2)
    elif lado == "acima":
        x, y = max(0, (pw - w) // 2), -h
    else:
        x, y = pw, max(0, (ph - h) // 2)
    # Posicionar um monitor desligado já o liga na área de trabalho.
    win_display.configurar(mon["nome"], w, h, hz, x, y)
    for _ in range(20):
        atual = _monitor_virtual()
        if atual is not None and "w" in atual:
            mon = atual
            break
        time.sleep(0.25)
    else:
        win_display.forcar_estender()
        time.sleep(1.0)
        win_display.configurar(mon["nome"], w, h, hz, x, y)
        mon = _monitor_virtual() or mon
    if "w" not in mon:
        print("[tela estendida] O Windows não ligou o monitor virtual.")
        return None
    _ativo, _nome = True, mon["nome"]
    print("[tela estendida] Monitor virtual %s: %dx%d em (%d,%d)"
          % (mon["nome"], mon["w"], mon["h"], mon["x"], mon["y"]))
    return mon


def recolher():
    """Desliga o monitor virtual se estiver ligado sem tablet conectado
    (ex.: logo após instalar o driver ou se o servidor fechou de repente)."""
    if not _WIN:
        return
    mon = _monitor_virtual()
    if mon is not None:
        win_display.desligar(mon["nome"])
        print("[tela estendida] Monitor virtual guardado até o tablet conectar.")


def desativar():
    """Tira o monitor virtual da área de trabalho (as janelas voltam ao PC)."""
    global _ativo
    if not _ativo:
        return
    _ativo = False
    win_display.desligar(_nome)
    print("[tela estendida] Monitor virtual desligado.")
