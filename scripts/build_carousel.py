#!/usr/bin/env python3
"""Build Instagram carousel slides for @tcg_h_s — Charizard G LV.X DP45."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

SRC = Path("/agent/source-photos/jpg")
OUT = Path("/agent/output/slides")
FILT = Path("/agent/output/filtered")
FONTS = Path("/agent/fonts")

SIZE = 1080  # Instagram square
MARGIN = 48

# Brand palette — charcoal + ember (Charizard), not purple AI defaults
CHARCOAL = (12, 12, 14)
EMBER = (232, 92, 32)
EMBER_SOFT = (255, 140, 70)
SILVER = (210, 214, 220)
WHITE = (255, 255, 255)
MUTED = (170, 172, 178)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS / name
    if not path.exists():
        path = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
    return ImageFont.truetype(str(path), size)


def enhance(im: Image.Image, *, contrast=1.18, color=1.22, brightness=1.04, sharpness=1.55) -> Image.Image:
    """Restoration-page filter: clearer damage, richer holo, deeper blacks."""
    im = im.convert("RGB")
    # Mild clarity via unsharp
    im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=140, threshold=2))
    im = ImageEnhance.Contrast(im).enhance(contrast)
    im = ImageEnhance.Color(im).enhance(color)
    im = ImageEnhance.Brightness(im).enhance(brightness)
    im = ImageEnhance.Sharpness(im).enhance(sharpness)
    # Crush blacks slightly for premium look
    arr_mode = im.point(lambda p: int(max(0, min(255, (p - 8) * 255 / 247))))
    return arr_mode


def smart_square(im: Image.Image, focus: str = "center") -> Image.Image:
    """Crop to square around focus, then resize to SIZE."""
    w, h = im.size
    side = min(w, h)
    if focus == "center":
        left = (w - side) // 2
        top = (h - side) // 2
    elif focus == "top":
        left = (w - side) // 2
        top = 0
    elif focus == "bottom":
        left = (w - side) // 2
        top = h - side
    elif focus == "left":
        left = 0
        top = (h - side) // 2
    elif focus == "right":
        left = w - side
        top = (h - side) // 2
    elif focus == "card":
        # Prefer upper-center for portrait card shots
        left = (w - side) // 2
        top = max(0, (h - side) // 3)
    else:
        left = (w - side) // 2
        top = (h - side) // 2
    crop = im.crop((left, top, left + side, top + side))
    return crop.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def vignette(im: Image.Image, strength: float = 0.35) -> Image.Image:
    w, h = im.size
    overlay = Image.new("RGB", (w, h), CHARCOAL)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    # radial falloff
    cx, cy = w / 2, h / 2
    max_r = math.hypot(cx, cy)
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r = math.hypot(x - cx, y - cy) / max_r
            v = int(min(255, max(0, (r - 0.45) / 0.55 * 255 * strength)))
            draw.rectangle([x, y, x + 1, y + 1], fill=v)
    mask = mask.filter(ImageFilter.GaussianBlur(28))
    return Image.composite(overlay, im, mask)


def gradient_bar(draw: ImageDraw.ImageDraw, xy, height=6):
    x0, y0, x1, _ = xy
    for i in range(height):
        draw.line([(x0, y0 + i), (x1, y0 + i)], fill=EMBER)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_shadow_text(draw, pos, text, fnt, fill=WHITE, shadow=(0, 0, 0)):
    x, y = pos
    draw.text((x + 2, y + 2), text, font=fnt, fill=shadow)
    draw.text((x, y), text, font=fnt, fill=fill)


def add_bottom_brand(im: Image.Image, label: str | None = None) -> Image.Image:
    """Dark gradient footer with brand + optional slide label."""
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # bottom gradient
    for i in range(220):
        alpha = int(210 * (i / 220) ** 1.4)
        y = SIZE - 220 + i
        d.line([(0, y), (SIZE, y)], fill=(8, 8, 10, alpha))
    # top thin brand strip
    for i in range(90):
        alpha = int(160 * (1 - i / 90) ** 1.2)
        d.line([(0, i), (SIZE, i)], fill=(8, 8, 10, alpha))

    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)

    f_brand = font("BebasNeue-Regular.ttf", 42)
    f_handle = font("Montserrat-SemiBold.ttf", 22)
    f_label = font("Oswald-Bold.ttf", 34)

    draw_shadow_text(d, (MARGIN, 28), "TCG HEALING STATION", f_brand, WHITE)
    d.text((MARGIN, 72), "@tcg_h_s", font=f_handle, fill=EMBER_SOFT)

    # ember accent line under brand
    d.rectangle([MARGIN, 104, MARGIN + 72, 108], fill=EMBER)

    if label:
        tw, th = text_size(d, label, f_label)
        pad_x, pad_y = 18, 10
        bx1, by1 = SIZE - MARGIN - tw - pad_x * 2, SIZE - MARGIN - th - pad_y * 2 - 8
        bx2, by2 = SIZE - MARGIN, SIZE - MARGIN - 8
        d.rounded_rectangle([bx1, by1, bx2, by2], radius=6, fill=(18, 18, 20))
        d.rectangle([bx1, by1, bx1 + 5, by2], fill=EMBER)
        d.text((bx1 + pad_x + 4, by1 + pad_y - 2), label, font=f_label, fill=WHITE)

    # bottom-left card ID
    f_small = font("Montserrat-SemiBold.ttf", 18)
    d.text((MARGIN, SIZE - MARGIN - 28), "CHARIZARD G LV.X  ·  DP45", font=f_small, fill=SILVER)
    return base


def make_cover(path: Path) -> Image.Image:
    raw = Image.open(path)
    im = enhance(raw, contrast=1.22, color=1.28, brightness=1.05, sharpness=1.65)
    im = smart_square(im, "card")
    im = vignette(im, 0.28)

    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # strong bottom panel for title
    for i in range(340):
        alpha = int(230 * (i / 340) ** 1.15)
        y = SIZE - 340 + i
        d.line([(0, y), (SIZE, y)], fill=(8, 8, 10, alpha))
    for i in range(120):
        alpha = int(150 * (1 - i / 120))
        d.line([(0, i), (SIZE, i)], fill=(8, 8, 10, alpha))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)

    f_brand = font("BebasNeue-Regular.ttf", 54)
    f_title = font("BebasNeue-Regular.ttf", 78)
    f_sub = font("Montserrat-SemiBold.ttf", 26)
    f_handle = font("Montserrat-SemiBold.ttf", 24)

    d.text((MARGIN, 34), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.text((MARGIN, 90), "@tcg_h_s", font=f_handle, fill=EMBER_SOFT)
    d.rectangle([MARGIN, 126, MARGIN + 90, 130], fill=EMBER)

    y = SIZE - 250
    d.text((MARGIN, y), "CHARIZARD G", font=f_title, fill=WHITE)
    d.text((MARGIN, y + 78), "LV.X  ·  DP PROMO", font=f_title, fill=EMBER_SOFT)
    d.text((MARGIN, y + 168), "INTAKE  ·  SURFACE & EDGE DIAGNOSIS", font=f_sub, fill=SILVER)
    return base


def make_process(path: Path, label: str, focus: str = "center") -> Image.Image:
    raw = Image.open(path)
    im = enhance(raw, contrast=1.2, color=1.15, brightness=1.03, sharpness=1.7)
    im = smart_square(im, focus)
    im = vignette(im, 0.22)
    return add_bottom_brand(im, label)


def make_detail(path: Path, label: str, focus: str = "center", zoom: float = 1.0) -> Image.Image:
    raw = Image.open(path)
    im = enhance(raw, contrast=1.28, color=1.25, brightness=1.06, sharpness=1.85)
    if zoom > 1.0:
        w, h = im.size
        nw, nh = int(w / zoom), int(h / zoom)
        left = (w - nw) // 2
        top = (h - nh) // 2
        im = im.crop((left, top, left + nw, top + nh))
    im = smart_square(im, focus)
    im = vignette(im, 0.2)
    return add_bottom_brand(im, label)


def make_end_cta(path: Path) -> Image.Image:
    raw = Image.open(path)
    im = enhance(raw, contrast=1.22, color=1.3, brightness=1.05, sharpness=1.6)
    im = smart_square(im, "card")
    im = vignette(im, 0.26)

    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # light top brand strip only
    for i in range(110):
        alpha = int(170 * (1 - i / 110) ** 1.1)
        d.line([(0, i), (SIZE, i)], fill=(8, 8, 10, alpha))
    # stronger bottom panel for CTA
    for i in range(300):
        alpha = int(235 * (i / 300) ** 1.05)
        y = SIZE - 300 + i
        d.line([(0, y), (SIZE, y)], fill=(8, 8, 10, alpha))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)

    f_brand = font("BebasNeue-Regular.ttf", 48)
    f_big = font("BebasNeue-Regular.ttf", 70)
    f_sub = font("Montserrat-SemiBold.ttf", 24)

    d.text((MARGIN, 40), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.rectangle([MARGIN, 96, MARGIN + 90, 100], fill=EMBER)

    y = SIZE - 230
    d.text((MARGIN, y), "FOLLOW FOR THE HEAL", font=f_big, fill=WHITE)
    d.text((MARGIN, y + 78), "@tcg_h_s", font=f_big, fill=EMBER_SOFT)
    d.text((MARGIN, y + 160), "DM TO BOOK YOUR CARD  ·  SWIPE FOR DETAILS", font=f_sub, fill=SILVER)
    return base


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FILT.mkdir(parents=True, exist_ok=True)

    slides = [
        ("01_cover.jpg", make_cover(SRC / "IMG_5529.jpg")),
        ("02_inspection.jpg", make_process(SRC / "IMG_5533.jpg", "INSPECTION", "center")),
        ("03_under_scope.jpg", make_process(SRC / "IMG_5536.jpg", "UNDER THE SCOPE", "center")),
        ("04_edge_whitening.jpg", make_process(SRC / "IMG_5537.jpg", "EDGE WHITENING", "top")),
        ("05_surface_wear.jpg", make_detail(SRC / "IMG_5530.jpg", "SURFACE WEAR", "center")),
        ("06_corner_damage.jpg", make_detail(SRC / "IMG_5550.jpg", "CORNER WEAR", "center", zoom=1.15)),
        ("07_promo_edge.jpg", make_detail(SRC / "IMG_5549.jpg", "PROMO EDGE", "center", zoom=1.1)),
        ("08_border_detail.jpg", make_detail(SRC / "IMG_5548.jpg", "BORDER DETAIL", "center", zoom=1.05)),
        ("09_holo_scuffs.jpg", make_detail(SRC / "IMG_5557.jpg", "HOLO SCUFFS", "center", zoom=1.1)),
        ("10_cta.jpg", make_end_cta(SRC / "IMG_5529.jpg")),
    ]

    # Also save a clean filtered full-card without heavy overlay for Stories/Reels
    hero = enhance(Image.open(SRC / "IMG_5529.jpg"), contrast=1.22, color=1.28, brightness=1.05, sharpness=1.65)
    hero = smart_square(hero, "card")
    hero.save(FILT / "hero_filtered.jpg", "JPEG", quality=94, optimize=True)

    for name, slide in slides:
        out = OUT / name
        slide.save(out, "JPEG", quality=94, optimize=True)
        print(f"wrote {out} ({slide.size[0]}x{slide.size[1]})")

    # Write caption
    caption = """Charizard G LV.X · Diamond & Pearl Promo (DP45)

Intake complete. Under the scope for surface haze, edge whitening, corner wear, and holo scuffs.

Swipe through the diagnosis 🔍

Healing starts at @tcg_h_s
TCG Healing Station

DM to book your card.

#tcghealingstation #tcg_h_s #pokemoncards #pokemontcg #charizard #charizardglvx #diamondandpearl #cardrestoration #cardcleaning #tcgrepair #vintagepokemon #holo #thehobby #pokemoncommunity #cardcollector
"""
    (Path("/agent/output") / "instagram_caption.txt").write_text(caption)
    print("caption written")
    print("DONE", len(slides), "slides")


if __name__ == "__main__":
    main()
