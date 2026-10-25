# Segunda Tela

App Android + servidor PC: use o tablet/celular como segunda tela via Wi-Fi ou cabo.

## Servidor do PC (Windows)

Baixe `SegundaTela-Servidor.exe` na release **servidor-v1.0** e abra. A janela mostra o IP para digitar no app (ou o app encontra o PC sozinho na rede).

- Porta e PIN: `SegundaTela-Servidor.exe --porta 8080 --pin 1234`
- Modo USB: `adb reverse tcp:8080 tcp:8080` e toque em "Modo USB" no app.
- Na primeira vez, permita o acesso no aviso do Firewall do Windows.

O .exe é gerado pelo workflow `build-exe.yml` a cada alteração em `servidor/` (ou manualmente em Actions).
