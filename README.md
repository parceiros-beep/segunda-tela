# Segunda Tela

App Android + servidor PC: use o tablet/celular como segunda tela via Wi-Fi ou cabo.

## Servidor do PC (Windows)

Baixe `SegundaTela-Servidor.exe` na release **servidor-v1.0** e abra. A janela mostra o IP para digitar no app (ou o app encontra o PC sozinho na rede).

- Porta e PIN: `SegundaTela-Servidor.exe --porta 8080 --pin 1234`
- Modo USB: `adb reverse tcp:8080 tcp:8080` e toque em "Modo USB" no app.
- Na primeira vez, permita o acesso no aviso do Firewall do Windows.

O .exe é gerado pelo workflow `build-exe.yml` a cada alteração em `servidor/` (ou manualmente em Actions).

## Tela estendida — passo a passo

A tela estendida transmite um **segundo monitor** do PC. O Windows não tem monitor virtual nativo, então é preciso ter um 2º monitor de alguma forma:

1. **Já tem 2 monitores?** Abra o servidor e marque "tela estendida" no app. Se a imagem estiver duplicada, o servidor força o modo **Estender** automaticamente.
2. **Só tem 1 monitor?** Escolha uma opção, uma única vez:
   - um monitor comum ou um **dummy HDMI** (plugue barato), ou
   - o **driver de monitor virtual gratuito**: https://github.com/VirtualDrivers/Virtual-Display-Driver/releases — baixe o instalador oficial, instale como administrador e reinicie se pedir.
3. Confira em **Configurações do Windows → Tela**: devem aparecer 2 telas e o modo **"Estender estas telas"** (não "Duplicar"). Atalho: tecla **Win+P → Estender**.
4. No console do servidor aparece "Monitores detectados: N". Com N ≥ 2, a tela estendida funciona.

Enquanto houver só 1 monitor, o app espelha a tela principal.
