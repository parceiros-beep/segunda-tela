"""
Área de transferência do Windows (texto), via ctypes.

ler() devolve o texto atual (ou None); escrever(texto) troca o conteúdo;
versao() muda a cada cópia (GetClipboardSequenceNumber), para detectar
mudanças sem ler o conteúdo toda hora. Fora do Windows vira no-op.
"""
import sys
import time

_WIN = sys.platform == "win32"

if _WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    def _abrir():
        # Outro programa pode estar com a área de transferência aberta.
        for _ in range(10):
            if user32.OpenClipboard(None):
                return True
            time.sleep(0.02)
        return False

    def versao():
        return user32.GetClipboardSequenceNumber()

    def ler():
        if not _abrir():
            return None
        try:
            h = user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return None
            p = kernel32.GlobalLock(h)
            if not p:
                return None
            try:
                return ctypes.wstring_at(p)
            finally:
                kernel32.GlobalUnlock(h)
        finally:
            user32.CloseClipboard()

    def escrever(texto):
        dados = ctypes.create_unicode_buffer(texto)
        tam = ctypes.sizeof(dados)
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, tam)
        if not h:
            return False
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, dados, tam)
        kernel32.GlobalUnlock(h)
        if not _abrir():
            return False
        try:
            user32.EmptyClipboard()
            # Depois de SetClipboardData o Windows é dono da memória.
            return bool(user32.SetClipboardData(CF_UNICODETEXT, h))
        finally:
            user32.CloseClipboard()

else:
    _texto = [None]
    _ver = [0]

    def versao(): return _ver[0]
    def ler(): return _texto[0]

    def escrever(texto):
        _texto[0] = texto
        _ver[0] += 1
        return True
