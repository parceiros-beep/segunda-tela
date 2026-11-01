"""
Painel de controle do Segunda Tela (interface no estilo One UI).

É uma página (painel/index.html) servida pelo próprio servidor e aberta numa
janela sem barras do navegador (modo "app" do Edge/Chrome). Fechar a janela não
encerra nada: o servidor continua em segundo plano com o ícone da bandeja.

Segurança: só responde a este PC (127.0.0.1), com o nome de host esperado e
com uma chave secreta (token) guardada na pasta do usuário. Isso impede que
um site aberto no navegador mande comandos ao servidor.
"""
import base64
import io
import os
import secrets
import subprocess
import sys
import webbrowser

import config

_WIN = sys.platform == "win32"
TITULO_JANELA = "Segunda Tela - Painel"


def token():
    t = config.ler("painel_token")
    if not t:
        t = secrets.token_urlsafe(24)
        config.gravar("painel_token", t)
    return t


def _base():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def caminho_pagina():
    return os.path.join(_base(), "painel", "index.html")


def pagina_html():
    with open(caminho_pagina(), "rb") as f:
        return f.read()


_qr = {}


def qr_data_url(texto):
    """QR code como imagem embutida (data URL); None se a biblioteca faltar."""
    if texto in _qr:
        return _qr[texto]
    try:
        import qrcode
        img = qrcode.make(texto, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        url = None
    _qr[texto] = url
    return url


def ler_log(linhas=80):
    caminho = os.path.join(config.pasta(), "servidor.log")
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()[-linhas:]
    except OSError:
        return []


def iniciado_com_windows():
    if not _WIN:
        return False
    try:
        import winreg
        chave = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
            winreg.QueryValueEx(k, "SegundaTela")
        return True
    except OSError:
        return False


def _navegador():
    """Edge (vem com o Windows) ou Chrome, para abrir como janela de aplicativo."""
    pastas = [os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
              os.environ.get("LOCALAPPDATA")]
    relativos = [r"Microsoft\Edge\Application\msedge.exe",
                 r"Google\Chrome\Application\chrome.exe"]
    for rel in relativos:
        for pasta in pastas:
            if pasta:
                c = os.path.join(pasta, rel)
                if os.path.isfile(c):
                    return c
    return None


def focar():
    """Se o painel já está aberto, traz para a frente. True se achou."""
    if not _WIN:
        return False
    try:
        import ctypes
        u = ctypes.WinDLL("user32")
        u.FindWindowW.restype = ctypes.c_void_p
        u.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        hwnd = u.FindWindowW(None, TITULO_JANELA)
        if not hwnd:
            return False
        u.ShowWindow(hwnd, 9)  # SW_RESTORE
        u.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def abrir(porta):
    """Abre (ou traz para a frente) o painel numa janela própria."""
    if focar():
        return
    url = "http://127.0.0.1:%d/painel?t=%s" % (porta, token())
    exe = _navegador()
    try:
        if exe:
            perfil = os.path.join(config.pasta(), "perfil-painel")
            subprocess.Popen([exe, "--app=" + url, "--window-size=1120,780",
                              "--user-data-dir=" + perfil, "--no-first-run",
                              "--no-default-browser-check", "--disable-extensions"])
            return
    except OSError:
        pass
    webbrowser.open(url)
