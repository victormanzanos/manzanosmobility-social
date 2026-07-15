#!/usr/bin/env python3
"""
Manzanos Mobility — image processor for Instagram (@manzanosmobility).

Toma imágenes del blog / fotos de producto (DBoat, Porsche, compraventa) y les aplica:
- crop/resize a 1080x1350 (post) o 1080x1920 (story)
- viñeta sutil en bordes
- marco DOBLE dorado (línea exterior + interior con gap)
- acentos en L en las 4 esquinas
- LOGO Manzanos Mobility dorado compuesto abajo sobre panel translúcido oscuro

Clonado del motor de @manzanoshabitat con la paleta del sitio manzanosmobility.com.

Uso:
    python3 make_manzanosmobility.py post  porsche-taycan-road.jpg  01-taycan.jpg
    python3 make_manzanosmobility.py story porsche-taycan-road.jpg  01-taycan-story.jpg
"""
import os, sys, math
from PIL import Image, ImageDraw

LOCAL       = os.path.expanduser("~/manzanosmobility-social")
RAW         = os.path.join(LOCAL, "raw")           # imágenes fuente (blog/web/producto)
ASSETS      = os.path.join(LOCAL, "assets")
OUT_POSTS   = os.path.join(LOCAL, "posts")
OUT_STORIES = os.path.join(LOCAL, "stories")

# Paleta Manzanos Mobility (del sitio: oro #c5a35b, fondo #0a0a0b)
GOLD     = (197, 163, 91)    # #c5a35b
GOLD_LT  = (212, 185, 119)   # #d4b977
INK      = (10, 10, 11)      # #0a0a0b

POST_W,  POST_H  = 1080, 1350
STORY_W, STORY_H = 1080, 1920

LOGO_GOLD = os.path.join(ASSETS, "logo-mm-gold.png")


def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    nw, nh = int(im.width * s + 1), int(im.height * s + 1)
    im = im.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return im.crop((x0, y0, x0 + w, y0 + h))


def add_vignette(im, strength=0.20):
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    px = mask.load()
    cx, cy = w / 2, h / 2
    max_d = math.hypot(cx, cy)
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy) / max_d
            v = max(0.0, d - 0.55) / 0.45
            px[x, y] = int(255 * v * strength)
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(dark, im, mask)


def draw_double_frame(im, margin_outer, gap, line_outer, line_inner):
    w, h = im.size
    canvas = im.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle([margin_outer, margin_outer, w - margin_outer - 1, h - margin_outer - 1],
                outline=GOLD, width=line_outer)
    mi = margin_outer + gap
    d.rectangle([mi, mi, w - mi - 1, h - mi - 1], outline=GOLD, width=line_inner)
    return Image.alpha_composite(canvas, overlay).convert("RGB")


def draw_corner_accents(im, margin, size, line):
    w, h = im.size
    canvas = im.convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.line([(margin, margin + size), (margin, margin)], fill=GOLD, width=line)
    d.line([(margin, margin), (margin + size, margin)], fill=GOLD, width=line)
    d.line([(w - margin - size, margin), (w - margin - 1, margin)], fill=GOLD, width=line)
    d.line([(w - margin - 1, margin), (w - margin - 1, margin + size)], fill=GOLD, width=line)
    d.line([(margin, h - margin - size), (margin, h - margin - 1)], fill=GOLD, width=line)
    d.line([(margin, h - margin - 1), (margin + size, h - margin - 1)], fill=GOLD, width=line)
    d.line([(w - margin - size, h - margin - 1), (w - margin - 1, h - margin - 1)], fill=GOLD, width=line)
    d.line([(w - margin - 1, h - margin - size), (w - margin - 1, h - margin - 1)], fill=GOLD, width=line)
    return Image.alpha_composite(canvas, overlay).convert("RGB")


def add_logo_bottom(im, story=False, logo_path=LOGO_GOLD):
    """Compone el logo Manzanos Mobility abajo, centrado, sobre panel translúcido
    oscuro con una fina línea dorada encima."""
    w, h = im.size
    canvas = im.convert("RGBA")

    panel_h = 230 if story else 190
    panel_y = h - panel_h - (54 if story else 44)
    panel = Image.new("RGBA", (w, panel_h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    for i in range(panel_h):
        a = int(160 * (i / panel_h) ** 1.4)
        pd.line([(0, i), (w, i)], fill=(INK[0], INK[1], INK[2], a))
    canvas.alpha_composite(panel, (0, panel_y))

    d = ImageDraw.Draw(canvas)
    d.line([(w * 0.34, panel_y), (w * 0.66, panel_y)], fill=GOLD, width=2)

    logo = Image.open(logo_path).convert("RGBA")
    # WHY: el logo hires es 10168x2804 (ratio ~3.6) — al 46% del ancho queda
    # proporcionado dentro del panel sin invadir el marco
    target_w = int(w * (0.50 if story else 0.46))
    target_h = int(target_w * logo.height / logo.width)
    logo = logo.resize((target_w, target_h), Image.LANCZOS)
    lx = (w - target_w) // 2
    ly = panel_y + (panel_h - target_h) // 2 + (6 if story else 4)
    canvas.alpha_composite(logo, (lx, ly))

    return canvas.convert("RGB")


def make_post(src_rel, out_filename, story=False):
    src_path = os.path.join(RAW, src_rel)
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"No existe: {src_path}")
    w, h = (STORY_W, STORY_H) if story else (POST_W, POST_H)
    out_dir = OUT_STORIES if story else OUT_POSTS
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, out_filename)

    img = Image.open(src_path).convert("RGB")
    img = cover(img, w, h)
    img = add_vignette(img, strength=0.20)
    if story:
        img = draw_double_frame(img, 54, 20, 4, 1)
        img = draw_corner_accents(img, 54, 90, 4)
    else:
        img = draw_double_frame(img, 44, 16, 3, 1)
        img = draw_corner_accents(img, 44, 70, 3)
    img = add_logo_bottom(img, story=story)
    img.save(out_path, "JPEG", quality=92, optimize=True)
    print(f"  ✓ {('STORY' if story else 'POST '):<5} {src_rel:<42} → {out_filename}")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] in ("post", "story"):
        make_post(sys.argv[2], sys.argv[3], story=(sys.argv[1] == "story"))
    else:
        print("Uso: make_manzanosmobility.py post|story <src_rel> <out.jpg>")
