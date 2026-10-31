; Instalador do servidor Segunda Tela (Inno Setup 6).
; Gerado pelo workflow build-exe.yml a partir de dist\SegundaTela-Servidor.

#define Nome "Segunda Tela"
#define Versao "3.0"
#define Exe "SegundaTela-Servidor.exe"

[Setup]
AppId={{6C1E2B57-4F3A-4E0B-9C1D-5E7A2F3B8D41}
AppName={#Nome}
AppVersion={#Versao}
AppPublisher={#Nome}
DefaultDirName={autopf}\SegundaTela
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=SegundaTela-Instalador
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayIcon={app}\{#Exe}
CloseApplications=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"
Name: "autostart"; Description: "Abrir o Segunda Tela junto com o Windows"; GroupDescription: "Inicialização:"

[Files]
Source: "..\dist\SegundaTela-Servidor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Exe}"
Name: "{group}\Desinstalar {#Nome}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Exe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SegundaTela"; ValueData: """{app}\{#Exe}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; Monitor virtual (tela estendida) + regra do Firewall. O instalador já é admin.
Filename: "{app}\{#Exe}"; Parameters: "--instalar-driver"; StatusMsg: "Instalando o monitor virtual (tela estendida)..."; Flags: runhidden waituntilterminated
Filename: "{app}\{#Exe}"; Description: "Abrir o Segunda Tela agora"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{app}\{#Exe}"; Parameters: "--desinstalar-driver"; Flags: runhidden waituntilterminated; RunOnceId: "RemoverDriver"
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Segunda Tela"""; Flags: runhidden; RunOnceId: "RemoverFirewall"
