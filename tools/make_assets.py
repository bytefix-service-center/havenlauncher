# -*- coding: utf-8 -*-
"""Генерирует все иконки и картинки из assets/logo.png.
Запуск: python tools/make_assets.py   (нужен Pillow: pip install pillow)
"""
import io, os, struct
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "assets")
NAVY, ORANGE, YELLOW = (12, 20, 52), (23, 227, 176), (58, 91, 255)

logo = Image.open(os.path.join(A, "logo.png")).convert("RGBA")


def sq(size, src=None):
    return (src or logo).resize((size, size), Image.LANCZOS)


# ---------- macOS .icns: иконка 824/1024 с мягкой тенью (как у системных) ----------
def mac_master():
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    body = sq(824)
    shadow = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 110), (100, 112), body.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(body, (100, 100))
    return canvas


def write_icns(path, master):
    types = {"icp4": 16, "icp5": 32, "icp6": 64, "ic07": 128, "ic08": 256, "ic09": 512,
             "ic10": 1024, "ic11": 32, "ic12": 64, "ic13": 256, "ic14": 512}
    chunks = b""
    for t, s in types.items():
        buf = io.BytesIO()
        master.resize((s, s), Image.LANCZOS).save(buf, "PNG")
        d = buf.getvalue()
        chunks += t.encode() + struct.pack(">I", len(d) + 8) + d
    with open(path, "wb") as f:
        f.write(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


master = mac_master()
write_icns(os.path.join(A, "icon.icns"), master)
master.resize((512, 512), Image.LANCZOS).save(os.path.join(A, "icon_preview.png"))

# ---------- Windows .ico (во весь размер, скруглённый квадрат из логотипа) ----------
logo.resize((256, 256), Image.LANCZOS).save(
    os.path.join(A, "icon.ico"), format="ICO",
    sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])


# ---------- фон для DMG (светлый: подписи Finder всегда чёрные) ----------
def font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    return ImageFont.truetype(p, size)


def dmg_bg(scale):
    W, H = 660 * scale, 400 * scale
    img = Image.new("RGB", (W, H))
    px = img.load()
    top, bot = (250, 247, 242), (236, 234, 246)
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    # мягкие цветные пятна в углах (маска размывается отдельно, чтобы не было серой каймы)
    img = img.convert("RGBA")
    for box, col, alpha in (((-140, -140, 180, 140), ORANGE, 80), ((460, 210, 780, 530), YELLOW, 110)):
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).ellipse([v * scale for v in box], fill=alpha)
        mask = mask.filter(ImageFilter.GaussianBlur(60 * scale))
        img.alpha_composite(Image.composite(Image.new("RGBA", (W, H), col + (255,)), Image.new("RGBA", (W, H), col + (0,)), mask))

    d = ImageDraw.Draw(img)
    s = scale
    title = "Haven Lands Launcher"
    f = font(26 * s, True)
    d.text((W / 2, 52 * s), title, font=f, fill=NAVY, anchor="mm")

    # стрелка между иконками (180 → 480 по x, y = 185)
    arrow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = ImageDraw.Draw(arrow)
    y = 185 * s
    x0, x1 = 258 * s, 400 * s
    steps = x1 - x0
    for i in range(steps):          # градиентная линия оранжевый → жёлтый
        t = i / steps
        c = tuple(int(ORANGE[k] + (YELLOW[k] - ORANGE[k]) * t) for k in range(3)) + (255,)
        a.line([(x0 + i, y), (x0 + i + 1, y)], fill=c, width=7 * s)
    a.ellipse((x0 - 3.5 * s, y - 3.5 * s, x0 + 3.5 * s, y + 3.5 * s), fill=ORANGE + (255,))
    a.line([(x1 - 14 * s, y - 16 * s), (x1 + 4 * s, y), (x1 - 14 * s, y + 16 * s)],
           fill=YELLOW + (255,), width=7 * s, joint="curve")
    for p in ((x1 - 14 * s, y - 16 * s), (x1 + 4 * s, y), (x1 - 14 * s, y + 16 * s)):
        a.ellipse((p[0] - 3.5 * s, p[1] - 3.5 * s, p[0] + 3.5 * s, p[1] + 3.5 * s), fill=YELLOW + (255,))
    img = Image.alpha_composite(img, arrow)

    d = ImageDraw.Draw(img)
    d.text((W / 2, 332 * s), "Перетащите иконку в папку Applications", font=font(14 * s), fill=NAVY, anchor="mm")
    return img.convert("RGB")


dmg_bg(2).save(os.path.join(A, "dmg_background@2x.png"))
dmg_bg(2).resize((660, 400), Image.LANCZOS).save(os.path.join(A, "dmg_background.png"))


# ---------- картинки мастера установки Windows (Inno Setup) ----------
def wizard_big(w, h):
    img = Image.new("RGB", (w, h), NAVY)
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(NAVY[i] + ((18, 18, 40)[i] - NAVY[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = c
    size = int(w * 0.62)
    ic = sq(size)
    tmp = img.convert("RGBA")
    tmp.alpha_composite(ic, ((w - size) // 2, int(h * 0.22)))
    d = ImageDraw.Draw(tmp)
    cx = w / 2
    d.text((cx, h * 0.22 + size + h * 0.07), "Haven Lands", font=font(int(w * 0.115), True), fill=(255, 255, 255), anchor="mm")
    d.text((cx, h * 0.22 + size + h * 0.12), "Launcher", font=font(int(w * 0.115), True), fill=ORANGE, anchor="mm")
    bar_h = max(4, h // 90)
    d.rectangle((0, h - bar_h, w // 2, h), fill=ORANGE)
    d.rectangle((w // 2, h - bar_h, w, h), fill=YELLOW)
    return tmp.convert("RGB")


def wizard_small(w, h):
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    s = min(w, h) - 4
    img.alpha_composite(sq(s), ((w - s) // 2, (h - s) // 2))
    return img.convert("RGB")


for w, h in ((164, 314), (246, 459), (328, 604)):
    wizard_big(w, h).save(os.path.join(A, "wizard_%d.bmp" % w))
for w, h in ((55, 55), (83, 80), (110, 106)):
    wizard_small(w, h).save(os.path.join(A, "wizard_small_%d.bmp" % w))

print("OK:", sorted(os.listdir(A)))
