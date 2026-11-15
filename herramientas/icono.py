"""Genera el icono de la app (assets/icon.ico) sin dependencias externas de diseno."""
import os
from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "assets", "icon.ico")


def crear():
    """Dibuja un cuadrado azul redondeado con las iniciales RJ en blanco."""
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    lado = 512
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, lado - 8, lado - 8], radius=110, fill=(29, 78, 216, 255))
    # franja inferior mas oscura para dar profundidad
    d.rounded_rectangle([8, lado - 150, lado - 8, lado - 8], radius=110, fill=(23, 62, 173, 255))
    d.rectangle([8, lado - 160, lado - 8, lado - 100], fill=(29, 78, 216, 255))

    fuente = None
    for nombre in ("arialbd.ttf", "seguisb.ttf", "segoeuib.ttf"):
        try:
            fuente = ImageFont.truetype(nombre, 230)
            break
        except OSError:
            continue
    if fuente is None:
        fuente = ImageFont.load_default()

    texto = "RJ"
    caja = d.textbbox((0, 0), texto, font=fuente)
    x = (lado - (caja[2] - caja[0])) / 2 - caja[0]
    y = (lado - (caja[3] - caja[1])) / 2 - caja[1] - 40
    d.text((x, y), texto, font=fuente, fill=(255, 255, 255, 255))

    img.save(SALIDA, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                            (128, 128), (256, 256)])
    print("icono:", SALIDA)


if __name__ == "__main__":
    crear()
