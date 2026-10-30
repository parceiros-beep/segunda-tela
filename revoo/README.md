# Revoo

Replay 3D de corridas, pedais e trilhas no Android.

- **Importar GPX/TCX**: abra o arquivo exportado do relógio ou do app de treino.
- **Foto neste ponto**: coloca fotos no percurso; elas aparecem durante o replay.
- Distância, tempo, altitude, subida acumulada e velocidade ao vivo, com perfil de altimetria.
- Câmera: Seguir, Panorâmica ou De cima. Replay em 0,5×, 1× ou 2×.

## Baixar o APK

Cada alteração em `revoo/` gera o `revoo.apk` na release **Revoo v1.0** (tag `revoo-v1.0`, aba Releases). No celular, permita "instalar apps desconhecidos" para o navegador ou gerenciador de arquivos.

## Estrutura

O app é um WebView que carrega `app/src/main/assets/index.html` (com o Three.js local em `assets/three.min.js`), então funciona offline.
