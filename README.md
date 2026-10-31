# Segunda Tela

Transforma o tablet ou celular Android num **monitor de verdade** para o PC com Windows: estender ou espelhar, por Wi‑Fi ou cabo USB, com toque e caneta.

## Recursos

| Recurso | Como funciona |
|---|---|
| **Tela estendida real** | O servidor cria um monitor virtual do tamanho exato do tablet. O driver (Virtual Display Driver, código aberto e assinado) é instalado pelo instalador; o monitor aparece ao conectar e some ao desconectar. |
| Espelhar | Mostra a tela principal do PC. |
| Posição | À esquerda, à direita ou acima do monitor do PC. |
| Resolução e escala | Máxima (nativa do tablet), Alta, Equilibrada, Desempenho. A escala do Windows (100%–300%) é ajustada sozinha para os itens não ficarem minúsculos. |
| Vídeo fluido | H.264 com o encoder da placa de vídeo (NVIDIA NVENC, AMD AMF, Intel QuickSync; CPU se não houver), até 60 fps, decodificação por hardware no tablet. Modo compatível MJPEG opcional. |
| Toque do Windows | Multitoque nativo: tocar, arrastar, pinça para zoom, rolar com dois dedos, segurar para menu. Ou modo mouse. |
| Caneta (S Pen) | Pressão, inclinação, botão lateral e borracha, como uma mesa digitalizadora. Rejeição da palma automática com a caneta perto da tela. |
| Barra de atalhos | Ctrl/Shift/Alt fixos (para usar com a caneta), desfazer, refazer, copiar, colar, salvar, Esc, Iniciar, Alt+Tab, zoom e mais. |
| Teclado | Teclado físico do tablet (Book Cover, Bluetooth) vira teclado do PC; teclado da tela também. |
| Conexão | Descoberta automática na rede; cabo USB com `adb reverse` automático. PIN opcional. |
| Ajustes ao vivo | Dá para mudar fps, bitrate, codec e qualidade com a tela aberta. A imagem reinicia só quando uma opção de vídeo muda. |
| Touchpad e mesa | Modo touchpad (o dedo arrasta o cursor, toque = clique, dois dedos = rolagem) e modo mesa digitalizadora (só a caneta). |
| Girar o tablet | No automático, a transmissão acompanha a nova orientação. |
| Teste de rede | Mede o atraso até o PC e sugere o perfil que combina com a rede. |
| Painel rápido | Botão do Android que conecta direto no último PC. |
| Bandeja do Windows | Ícone com status, desligar a tela estendida e sair. |

## Instalação

1. **PC (Windows 10 1809+ ou 11):** baixe `SegundaTela-Instalador.exe` na release **servidor-v3.0** (ou a mais recente) e instale. O instalador instala o monitor virtual, libera o Firewall e cria os atalhos.
2. **Tablet:** instale `segunda-tela.apk` da release mais recente: https://github.com/parceiros-beep/segunda-tela/releases/latest
3. Abra o Segunda Tela no PC e no tablet, na mesma rede Wi‑Fi, e toque no computador que aparecer.

**Pelo cabo USB (mais rápido):** ative *Opções do desenvolvedor › Depuração USB* no tablet, plugue no PC com o servidor aberto, aceite o aviso no tablet e toque em *Conectar pelo cabo USB*.

## Servidor

- Porta e PIN: `SegundaTela-Servidor.exe --porta 8080 --pin 1234`
- Abrir com o Windows: `SegundaTela-Servidor.exe --iniciar-com-windows sim`
- Remover o monitor virtual: `SegundaTela-Servidor.exe --desinstalar-driver`

O console mostra o que está acontecendo: monitor virtual criado (nome, resolução, posição), encoder de vídeo usado e conexões. Se algo falhar, copie essas linhas.

## Desenvolvimento

- `servidor/`: servidor Python (gerado como instalador pelo workflow `build-exe.yml`, que embute ffmpeg, o driver, nefcon e adb).
- `android/`: app Android em Kotlin (APK gerado pelo workflow `build.yml`).
