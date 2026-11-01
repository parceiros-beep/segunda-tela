"""
Conexão direta: o PC cria a própria rede Wi-Fi (o "Hotspot móvel" do
Windows) em 5 GHz ou 2,4 GHz, e o tablet conecta nela sem roteador no meio.

Usa a API do Windows (NetworkOperatorTetheringManager) pelo PowerShell.
Limites do hardware: a placa Wi-Fi precisa aceitar a faixa pedida e, se o PC
estiver no Wi-Fi do roteador, a mesma placa costuma ficar presa à faixa dessa
conexão. Com o PC no cabo de rede, qualquer faixa suportada funciona.
"""
import base64
import json
import os
import secrets
import string
import subprocess
import sys

_WIN = sys.platform == "win32"
IP_PC = "192.168.137.1"  # endereço do PC na rede do hotspot do Windows
_ligado_por_nos = False

# Estado que o painel mostra: desligado | ligando | ligado | erro
ESTADO = {"estado": "desligado", "ssid": "", "senha": "", "banda": "", "msg": ""}

_BANDAS = {"auto": 0, "2.4": 1, "5": 2}
_NOMES = {"TwoPointFourGigahertz": "2,4 GHz", "FiveGigahertz": "5 GHz",
          "SixGigahertz": "6 GHz", "Auto": "automática"}


def _arquivo():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    pasta = os.path.join(base, "SegundaTela")
    os.makedirs(pasta, exist_ok=True)
    return os.path.join(pasta, "conexao_direta.json")


def credenciais():
    """Nome e senha da rede direta (criados uma vez e reaproveitados)."""
    try:
        with open(_arquivo(), encoding="utf-8") as f:
            c = json.load(f)
        if c.get("ssid") and len(c.get("senha", "")) >= 8:
            return c
    except (OSError, ValueError):
        pass
    letras = string.ascii_letters + string.digits
    c = {"ssid": "SegundaTela-" + "".join(secrets.choice(string.digits) for _ in range(4)),
         "senha": "".join(secrets.choice(letras) for _ in range(12))}
    try:
        with open(_arquivo(), "w", encoding="utf-8") as f:
            json.dump(c, f)
    except OSError:
        pass
    return c


_SCRIPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
$r = @{ ok = $false; msg = ''; banda = ''; ativo = $false; suporta5 = $null }
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $m = [System.WindowsRuntimeSystemExtensions].GetMethods()
  $asOp = ($m | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  $asAc = ($m | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
  function Esperar($op, [Type]$tipo) { $t = $asOp.MakeGenericMethod($tipo).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
  function EsperarAcao($ac) { $t = $asAc.Invoke($null, @($ac)); $t.Wait(-1) | Out-Null }
  [void][Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
  [void][Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
  $Res = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]
  $Ligado = [Windows.Networking.NetworkOperators.TetheringOperationalState]::On
  $perfil = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
  if ($perfil -eq $null) { $perfil = [Windows.Networking.Connectivity.NetworkInformation]::GetConnectionProfiles() | Select-Object -First 1 }
  if ($perfil -eq $null) { throw 'O PC não está em nenhuma rede. O hotspot do Windows precisa de uma conexão (cabo ou Wi-Fi) para ligar.' }
  $tm = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($perfil)
  if ('__ACAO__' -eq 'ligar') {
    $cfg = $tm.GetCurrentAccessPointConfiguration()
    $cfg.Ssid = '__SSID__'
    $cfg.Passphrase = '__SENHA__'
    $banda = __BANDA__
    try {
      $b = [Windows.Networking.NetworkOperators.TetheringWiFiBand]$banda
      if ($banda -eq 0 -or $cfg.IsBandSupported($b)) { $cfg.Band = $b }
      else { $r.msg = 'A placa Wi-Fi deste PC não aceita essa faixa no hotspot; usando a automática.' }
    } catch { if ($banda -ne 0) { $r.msg = 'Este Windows não deixa escolher a faixa (precisa do Windows 10 2004 ou mais novo); usando a automática.' } }
    EsperarAcao ($tm.ConfigureAccessPointAsync($cfg))
    if ($tm.TetheringOperationalState -eq $Ligado) { $null = Esperar ($tm.StopTetheringAsync()) $Res }
    $s = Esperar ($tm.StartTetheringAsync()) $Res
    if ($s.Status -ne [Windows.Networking.NetworkOperators.TetheringOperationStatus]::Success) {
      throw ('O Windows não ligou o hotspot (' + $s.Status + '). ' + $s.AdditionalErrorMessage)
    }
  } elseif ('__ACAO__' -eq 'desligar') {
    if ($tm.TetheringOperationalState -eq $Ligado) { $null = Esperar ($tm.StopTetheringAsync()) $Res }
  }
  $r.ativo = ($tm.TetheringOperationalState -eq $Ligado)
  try { $c2 = $tm.GetCurrentAccessPointConfiguration(); $r.banda = [string]$c2.Band
        $r.suporta5 = $c2.IsBandSupported([Windows.Networking.NetworkOperators.TetheringWiFiBand]::FiveGigahertz) } catch {}
  $r.ok = $true
} catch { $r.msg = $_.Exception.Message }
$r | ConvertTo-Json -Compress
"""


def _rodar(acao, banda="auto"):
    if not _WIN:
        return {"ok": False, "msg": "Conexão direta só funciona no Windows."}
    c = credenciais()
    script = (_SCRIPT.replace("__ACAO__", acao).replace("__SSID__", c["ssid"])
              .replace("__SENHA__", c["senha"]).replace("__BANDA__", str(_BANDAS.get(banda, 0))))
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand",
             base64.b64encode(script.encode("utf-16-le")).decode()],
            capture_output=True, timeout=90, creationflags=0x08000000)
        linhas = r.stdout.decode("utf-8", "replace").strip().splitlines()
        res = json.loads(linhas[-1]) if linhas else {"ok": False, "msg": "sem resposta"}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as e:
        res = {"ok": False, "msg": "Falha ao falar com o Windows: %s" % e}
    res["banda_nome"] = _NOMES.get(res.get("banda", ""), res.get("banda", ""))
    return res


def ligar(banda="5"):
    """Liga a rede direta. banda: "5", "2.4" ou "auto"."""
    global _ligado_por_nos
    ESTADO.update(estado="ligando", msg="", banda="")
    res = _rodar("ligar", banda)
    res.update(credenciais())
    res["ip"] = IP_PC
    if res.get("ok") and res.get("ativo"):
        _ligado_por_nos = True
        ESTADO.update(estado="ligado", ssid=res["ssid"], senha=res["senha"],
                      banda=res.get("banda_nome", ""), msg=res.get("msg", ""))
        print("[direto] Rede direta ligada: %s (senha %s), faixa %s."
              % (res["ssid"], res["senha"], res["banda_nome"] or "?"))
        if res.get("msg"):
            print("[direto] " + res["msg"])
    else:
        ESTADO.update(estado="erro", msg=res.get("msg", "") or "O Windows não ligou o hotspot.")
        print("[direto] Não consegui ligar a rede direta: %s" % res.get("msg", ""))
    return res


def desligar():
    global _ligado_por_nos
    res = _rodar("desligar")
    _ligado_por_nos = False
    ESTADO.update(estado="desligado", msg="", banda="")
    print("[direto] Rede direta desligada.")
    return res


def mostrar_qr():
    """Abre um QR code com nome e senha da rede direta (a câmera do Android
    conecta lendo o código). Sem a biblioteca, abre um texto com os dados."""
    c = credenciais()
    pasta = os.path.dirname(_arquivo())
    texto = "WIFI:T:WPA;S:%s;P:%s;;" % (c["ssid"], c["senha"])
    try:
        import qrcode
        img = qrcode.make(texto)
        caminho = os.path.join(pasta, "conexao_direta_qr.png")
        img.save(caminho)
    except Exception:
        caminho = os.path.join(pasta, "conexao_direta.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("Rede: %s\nSenha: %s\n" % (c["ssid"], c["senha"]))
    if _WIN:
        os.startfile(caminho)
    return caminho


def desligar_se_nosso():
    """Ao fechar o servidor: só desliga o hotspot se fomos nós que ligamos."""
    if _ligado_por_nos:
        desligar()
