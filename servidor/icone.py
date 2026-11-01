"""
Ícone do Segunda Tela: um monitor com uma segunda tela (tablet) na frente,
num quadrado arredondado azul, no estilo One UI.

É desenhado por código (sem arquivos de imagem), então serve para tudo:
  - bandeja do Windows e janela do painel (desenhar / png_bytes);
  - ícone do .exe, dos atalhos e do instalador (python icone.py --ico saida.ico).
"""
import io
import sys

from PIL import Image, ImageDraw, ImageFilter

# cantos do gradiente de fundo: claro (topo/esq.) -> escuro (base/dir.)
_CANTOS = ((86, 176, 255), (24, 128, 250), (24, 128, 250), (0, 84, 214))
_TELA = (10, 92, 214)          # tela do monitor
_TELA2 = (150, 205, 255)       # tela do tablet
_SOMBRA = (0, 40, 130)


def desenhar(tam=256):
    """Devolve o ícone como imagem RGBA tam x tam (suavizado)."""
    S = 1024
    # --- fundo: quadrado arredondado com gradiente nos quatro cantos
    cantos = Image.new("RGB", (2, 2))
    cantos.putpixel((0, 0), _CANTOS[0]); cantos.putpixel((1, 0), _CANTOS[1])
    cantos.putpixel((0, 1), _CANTOS[2]); cantos.putpixel((1, 1), _CANTOS[3])
    fundo = cantos.resize((S, S), Image.BILINEAR).convert("RGBA")
    mascara = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.225), fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(fundo, (0, 0), mascara)

    # --- monitor (atrás)
    cam = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    d.rounded_rectangle((150, 210, 760, 650), radius=58, fill=(255, 255, 255, 255))
    d.rounded_rectangle((186, 246, 724, 614), radius=30, fill=_TELA + (255,))
    d.rectangle((408, 650, 502, 724), fill=(255, 255, 255, 255))
    d.rounded_rectangle((318, 716, 592, 770), radius=27, fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, cam)

    # --- sombra suave do tablet para separar da tela do monitor
    sombra = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((548, 424, 892, 850), radius=64, fill=_SOMBRA + (120,))
    sombra = sombra.filter(ImageFilter.GaussianBlur(22))
    img = Image.alpha_composite(img, sombra)

    # --- tablet (na frente)
    cam = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    d.rounded_rectangle((560, 430, 880, 836), radius=56, fill=(255, 255, 255, 255))
    d.rounded_rectangle((594, 472, 846, 782), radius=28, fill=_TELA2 + (255,))
    d.ellipse((704, 446, 736, 478), fill=(190, 205, 225, 255))
    # cursor na segunda tela (a ideia: arrastar janelas para ela)
    d.polygon([(640, 540), (640, 664), (672, 634), (700, 692), (724, 680), (696, 624), (738, 622)],
              fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, cam)

    return img.resize((tam, tam), Image.LANCZOS)


def png_bytes(tam=256):
    buf = io.BytesIO()
    desenhar(tam).save(buf, format="PNG")
    return buf.getvalue()


def salvar_ico(caminho):
    """Ícone do Windows com todos os tamanhos que o sistema usa."""
    base = desenhar(256)
    base.save(caminho, format="ICO",
              sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (40, 40),
                     (32, 32), (24, 24), (20, 20), (16, 16)])


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--ico" in args:
        salvar_ico(args[args.index("--ico") + 1])
    if "--png" in args:
        caminho = args[args.index("--png") + 1]
        tam = int(args[args.index("--tam") + 1]) if "--tam" in args else 512
        desenhar(tam).save(caminho, format="PNG")
