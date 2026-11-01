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
| Conexão direta 5 / 2,4 GHz | O PC cria a própria rede Wi‑Fi (Hotspot móvel do Windows) e o tablet entra nela sozinho, sem roteador no meio. Pelo app ou pelo ícone da bandeja. |
| Som do PC | O som que sai no PC toca no tablet (opcional). |
| Área de transferência | Copiou no PC, cola no tablet, e o contrário (texto). |
| Ajustes por PC | O app lembra a configuração usada com cada computador. |
| Barra personalizável | Você escolhe quais botões aparecem na barra de atalhos. |
| Bitrate automático | Durante o uso, baixa o bitrate quando a rede piora e sobe quando melhora (opcional). |
| Barra por programa | A barra de atalhos troca os botões conforme o programa aberto no PC. |
| Gestos de borda | Deslizar da lateral abre a barra; de cima, abre o menu. |
| QR code da rede direta | Pela bandeja do PC: a câmera do tablet lê e entra na rede. |
| Conexão direta ao abrir | Pela bandeja: o PC liga a rede direta sozinho quando o servidor abre. |
| Botão "Conexão direta" | Segundo botão no painel rápido do Android. |

## Instalação

1. **PC (Windows 10 1809+ ou 11):** baixe `SegundaTela-Instalador.exe` na release **servidor-v3.0** (ou a mais recente) e instale. O instalador instala o monitor virtual, libera o Firewall e cria os atalhos.
2. **Tablet:** instale `segunda-tela.apk` da release mais recente: https://github.com/parceiros-beep/segunda-tela/releases/latest
3. Abra o Segunda Tela no PC e no tablet, na mesma rede Wi‑Fi, e toque no computador que aparecer.

**Pelo cabo USB (mais rápido):** ative *Opções do desenvolvedor › Depuração USB* no tablet, plugue no PC com o servidor aberto, aceite o aviso no tablet e toque em *Conectar pelo cabo USB*.

## Conexão direta (sem roteador)

No app, toque em **Conexão direta 5 GHz** (ou 2,4 GHz). O PC liga o Hotspot móvel do Windows com nome e senha próprios, o tablet entra nessa rede (o Android pede confirmação uma vez) e conecta. Também dá para ligar pelo ícone da bandeja ou com `SegundaTela-Servidor.exe --direto 5`.

- A placa Wi‑Fi do PC precisa aceitar a faixa escolhida.
- Com o PC no **cabo de rede**, qualquer faixa suportada funciona. Com o PC no **Wi‑Fi do roteador**, a mesma placa costuma ficar presa à faixa dessa conexão.
- Enquanto estiver na rede direta, o tablet sai do Wi‑Fi de casa. Use **Voltar para a rede normal** no app para sair.

## Fora de casa

Instale o [Tailscale](https://tailscale.com) (gratuito) no PC e no tablet, com a mesma conta. No app, digite o IP do PC no Tailscale (100.x.x.x) e toque em Conectar. Use um PIN no servidor (`--pin`).

## Painel e segundo plano (sem janela preta)

O servidor roda **escondido**: só o ícone perto do relógio do Windows (se não aparecer, clique na setinha ^). Não precisa deixar nenhuma janela aberta.

**O painel** (estilo One UI para computador: barra lateral com Visão geral, Conexão direta, Recursos, Aparência, Registro e Sobre; atalhos **Alt+1 a Alt+6**; tema claro/escuro e cor de destaque à sua escolha; em janela estreita vira uma coluna única) abre ao clicar no ícone, ao abrir o programa pelo atalho, ou ao abrir de novo se já estiver rodando. Nele você vê:

- se o tablet está conectado (resolução, encoder, tempo), o IP do PC e o PIN;
- a conexão direta 5 GHz / 2,4 GHz com QR code, nome e senha da rede;
- os recursos (tela estendida, som, área de transferência) e as opções gerais, como abrir com o Windows;
- o registro (log) do servidor e o botão para encerrar.

**Fechar a janela do painel não encerra nada.** Para encerrar de verdade, use *Encerrar o Segunda Tela* no painel ou *Sair* no menu do ícone.

O painel só responde a este PC e exige uma chave secreta guardada na sua pasta de usuário, então nenhum site aberto no navegador consegue mexer no servidor. Os avisos do servidor ficam em `%APPDATA%\SegundaTela\servidor.log`, e erros graves em `erro.log`.

## Servidor

- Porta e PIN: `SegundaTela-Servidor.exe --porta 8080 --pin 1234`
- Abrir com o Windows: `SegundaTela-Servidor.exe --iniciar-com-windows sim`
- Ligar a conexão direta ao abrir: `SegundaTela-Servidor.exe --direto 5` (ou `2.4`, `auto`)
- Remover o monitor virtual: `SegundaTela-Servidor.exe --desinstalar-driver`

O console mostra o que está acontecendo: monitor virtual criado (nome, resolução, posição), encoder de vídeo usado e conexões. Se algo falhar, copie essas linhas.

## Desenvolvimento

- `servidor/`: servidor Python (gerado como instalador pelo workflow `build-exe.yml`, que embute ffmpeg, o driver, nefcon e adb).
- `android/`: app Android em Kotlin (APK gerado pelo workflow `build.yml`).
