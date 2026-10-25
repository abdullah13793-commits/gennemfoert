"""Cover (1600x1200) and the register/labels gallery image."""
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "publish"
F = lambda s, b=False: ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf" if b else r"C:\Windows\Fonts\segoeui.ttf", s)


def cover():
    hero = Image.open(ROOT / "renders" / "hero.png").convert("RGB").resize((1600, 1200))
    d = ImageDraw.Draw(hero, "RGBA")
    grad = Image.new("L", (1600, 1200), 0)
    gd = ImageDraw.Draw(grad)
    for y in range(1200):
        gd.line([(0, y), (1600, y)], fill=int(max(0, 235 - y * 0.62)))
    hero.paste(Image.new("RGB", (1600, 1200), (8, 9, 13)), (0, 0), grad)
    d = ImageDraw.Draw(hero, "RGBA")
    d.rounded_rectangle([64, 64, 104, 104], 9, fill=(232, 163, 23))
    d.ellipse([75, 75, 93, 93], outline=(17, 17, 17), width=5)
    d.text((122, 60), "Gennemført", font=F(44, True), fill=(245, 246, 248))
    d.text((64, 140), "Every penetration of a fire separation,", font=F(52, True), fill=(245, 246, 248))
    d.text((64, 204), "checked against the exact tested configuration.", font=F(52, True), fill=(245, 246, 248))
    d.text((64, 286), "IFC model  →  ETA rows with page citations  →  register, QR labels, BCF, IFC, assessment drafts, MCP",
           font=F(25), fill=(200, 206, 214))
    chips = [("36 tested", (31, 157, 87)), ("17 deviations named", (232, 163, 23)), ("3 not covered", (214, 59, 59)),
             ("59/59 answer key", (60, 66, 78))]
    x = 64
    for txt, col in chips:
        w = d.textlength(txt, font=F(24, True)) + 36
        d.rounded_rectangle([x, 1088, x + w, 1136], 24, fill=col)
        d.text((x + 18, 1095), txt, font=F(24, True), fill=(255, 255, 255))
        x += w + 14
    d.text((1536, 1150), "Demonstration building (fictitious) · ETA-21/0110", font=F(18), fill=(150, 156, 166), anchor="rs")
    hero.save(PUB / "01_cover.png")
    hero.save(PUB / "01_cover.jpg", quality=90)


def register_image():
    doc = pymupdf.open(ROOT / "out" / "Gennemfoeringsregister.pdf")
    a = Image.frombytes("RGB", *[(p.width, p.height) for p in [doc[0].get_pixmap(dpi=110)]][0:1], doc[0].get_pixmap(dpi=110).samples)
    lp = doc[doc.page_count - 2].get_pixmap(dpi=110)
    b = Image.frombytes("RGB", (lp.width, lp.height), lp.samples)
    W = 1600
    a = a.resize((W // 2 - 30, int(a.height * (W // 2 - 30) / a.width)))
    b = b.resize((W // 2 - 30, int(b.height * (W // 2 - 30) / b.width)))
    canvas = Image.new("RGB", (W, max(a.height, b.height) + 120), (12, 14, 18))
    for im, x in ((a, 20), (b, W // 2 + 10)):
        sh = Image.new("RGBA", (im.width + 30, im.height + 30), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rectangle([15, 15, im.width + 15, im.height + 15], fill=(0, 0, 0, 150))
        canvas.paste(sh.filter(ImageFilter.GaussianBlur(10)), (x - 15, 85), sh.filter(ImageFilter.GaussianBlur(10)))
        canvas.paste(im, (x, 90))
    d = ImageDraw.Draw(canvas)
    d.text((20, 26), "Penetration register (PDF/Excel) and QR site labels, one per seal", font=F(30, True), fill=(240, 242, 245))
    canvas.save(PUB / "07_register_labels.png")


if __name__ == "__main__":
    cover()
    register_image()
    print("ok")
