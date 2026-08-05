#!/usr/bin/env python3
"""Crop subjects, place on fiery lava backgrounds, rebuild Instagram slides + reel."""

from __future__ import annotations

import math
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

try:
    from rembg import remove as rembg_remove
except Exception:
    rembg_remove = None

SRC = Path("/agent/source-photos/drive2_jpg")
OUT = Path("/agent/output/slides")
FILT = Path("/agent/output/composites")
FONTS = Path("/agent/fonts")
REELS = Path("/agent/output/reels")

SIZE = 1080
MARGIN = 48
CHARCOAL = (12, 12, 14)
EMBER = (232, 92, 32)
EMBER_SOFT = (255, 140, 70)
SILVER = (210, 214, 220)
WHITE = (255, 255, 255)


def font(name: str, size: int):
    path = FONTS / name
    if not path.exists():
        path = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
    return ImageFont.truetype(str(path), size)


def enhance(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=135, threshold=2))
    im = ImageEnhance.Contrast(im).enhance(1.2)
    im = ImageEnhance.Color(im).enhance(1.25)
    im = ImageEnhance.Brightness(im).enhance(1.04)
    im = ImageEnhance.Sharpness(im).enhance(1.45)
    return im


def make_lava(size: int = SIZE, seed: int = 7) -> Image.Image:
    """Procedural fiery lava / ember background."""
    rng = random.Random(seed)
    w = h = size
    # Base dark magma
    arr = np.zeros((h, w, 3), dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    # Flow bands
    for i in range(8):
        amp = rng.uniform(40, 120)
        freq = rng.uniform(0.002, 0.01)
        phase = rng.uniform(0, 10)
        angle = rng.uniform(0, math.pi)
        proj = xx * math.cos(angle) + yy * math.sin(angle)
        wave = np.sin(proj * freq * 2 * math.pi + phase)
        heat = (wave * 0.5 + 0.5) ** 2
        color = np.array(
            [
                rng.uniform(180, 255),  # R
                rng.uniform(40, 120),  # G
                rng.uniform(5, 40),  # B
            ],
            dtype=np.float32,
        )
        arr += heat[:, :, None] * color * (amp / 255.0)

    # Hot cracks / veins
    for i in range(18):
        x0, y0 = rng.randint(0, w - 1), rng.randint(0, h - 1)
        length = rng.randint(80, 420)
        thick = rng.randint(2, 8)
        angle = rng.uniform(0, 2 * math.pi)
        for t in range(length):
            jitter = rng.uniform(-1.2, 1.2)
            x = int(x0 + t * math.cos(angle) + jitter * math.sin(angle) * 8)
            y = int(y0 + t * math.sin(angle) - jitter * math.cos(angle) * 8)
            if 0 <= x < w and 0 <= y < h:
                rr = thick
                x1, x2 = max(0, x - rr), min(w, x + rr + 1)
                y1, y2 = max(0, y - rr), min(h, y + rr + 1)
                arr[y1:y2, x1:x2, 0] += 90
                arr[y1:y2, x1:x2, 1] += 35
                arr[y1:y2, x1:x2, 2] += 5

    # Hot spots
    for i in range(25):
        cx, cy = rng.randint(0, w - 1), rng.randint(0, h - 1)
        rad = rng.randint(30, 160)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        blob = np.clip(1 - dist / rad, 0, 1) ** 2
        arr[:, :, 0] += blob * rng.uniform(60, 140)
        arr[:, :, 1] += blob * rng.uniform(20, 70)

    # Darken edges
    cx, cy = w / 2, h / 2
    dist = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    vignette = np.clip(1.15 - dist * 0.75, 0.35, 1.0)
    arr *= vignette[:, :, None]

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGB")
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    im = ImageEnhance.Contrast(im).enhance(1.15)
    im = ImageEnhance.Color(im).enhance(1.2)
    return im


def cutout_rgba(im: Image.Image) -> Image.Image:
    """Remove background -> RGBA. Prefer rembg; fallback dark/desk mask."""
    im = im.convert("RGB")
    if rembg_remove is not None:
        try:
            out = rembg_remove(im)
            if isinstance(out, (bytes, bytearray)):
                from io import BytesIO

                out = Image.open(BytesIO(out)).convert("RGBA")
            else:
                out = out.convert("RGBA")
            # If rembg nuked almost everything, fall through
            alpha = np.array(out.split()[-1])
            if alpha.mean() > 8:
                return out
        except Exception as e:
            print("rembg failed:", e)

    # Fallback: keep non-dark / non-gray desk pixels
    arr = np.array(im)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # dark background
    dark = lum < 45
    # gray desk-ish
    mx = np.maximum(np.maximum(r, g), b).astype(np.int16)
    mn = np.minimum(np.minimum(r, g), b).astype(np.int16)
    grayish = (mx - mn < 18) & (lum < 110)
    mask = ~(dark | grayish)
    # cleanup
    mask_im = Image.fromarray((mask * 255).astype(np.uint8), "L")
    mask_im = mask_im.filter(ImageFilter.MaxFilter(5))
    mask_im = mask_im.filter(ImageFilter.MinFilter(5))
    mask_im = mask_im.filter(ImageFilter.GaussianBlur(1.2))
    rgba = im.convert("RGBA")
    rgba.putalpha(mask_im)
    return rgba


def fit_on_lava(subject_rgba: Image.Image, lava: Image.Image, scale: float = 0.86) -> Image.Image:
    canvas = lava.copy().convert("RGBA")
    sub = subject_rgba.copy()
    # trim transparent borders
    bbox = sub.getbbox()
    if bbox:
        sub = sub.crop(bbox)
    # scale to fit
    max_w, max_h = int(SIZE * scale), int(SIZE * scale)
    sub.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    x = (SIZE - sub.width) // 2
    y = (SIZE - sub.height) // 2
    # soft shadow
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", (sub.width + 20, sub.height + 20), (0, 0, 0, 0))
    alpha = sub.split()[-1]
    sh_alpha = Image.new("L", sh.size, 0)
    sh_alpha.paste(alpha, (10, 10))
    sh_alpha = sh_alpha.filter(ImageFilter.GaussianBlur(16))
    sh.putalpha(sh_alpha.point(lambda p: int(p * 0.55)))
    shadow.paste(sh, (x - 10 + 8, y - 10 + 14), sh)
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.paste(sub, (x, y), sub)
    return canvas.convert("RGB")


def text_size(draw, text, fnt):
    b = draw.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0], b[3] - b[1]


def brand(im: Image.Image, label: str | None = None, card_id: bool = True) -> Image.Image:
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(220):
        a = int(200 * (i / 220) ** 1.35)
        d.line([(0, SIZE - 220 + i), (SIZE, SIZE - 220 + i)], fill=(8, 8, 10, a))
    for i in range(95):
        a = int(170 * (1 - i / 95) ** 1.15)
        d.line([(0, i), (SIZE, i)], fill=(8, 8, 10, a))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)
    f_brand = font("BebasNeue-Regular.ttf", 42)
    f_handle = font("Montserrat-SemiBold.ttf", 22)
    f_label = font("Oswald-Bold.ttf", 34)
    f_small = font("Montserrat-SemiBold.ttf", 18)
    d.text((MARGIN + 2, 30), "TCG HEALING STATION", font=f_brand, fill=(0, 0, 0))
    d.text((MARGIN, 28), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.text((MARGIN, 72), "@tcg_h_s", font=f_handle, fill=EMBER_SOFT)
    d.rectangle([MARGIN, 104, MARGIN + 72, 108], fill=EMBER)
    if card_id:
        d.text((MARGIN, SIZE - MARGIN - 28), "CHARIZARD G LV.X  ·  DP45", font=f_small, fill=SILVER)
    if label:
        tw, th = text_size(d, label, f_label)
        pad_x, pad_y = 18, 10
        bx1 = SIZE - MARGIN - tw - pad_x * 2
        by1 = SIZE - MARGIN - th - pad_y * 2 - 8
        bx2, by2 = SIZE - MARGIN, SIZE - MARGIN - 8
        d.rounded_rectangle([bx1, by1, bx2, by2], radius=6, fill=(18, 18, 20))
        d.rectangle([bx1, by1, bx1 + 5, by2], fill=EMBER)
        d.text((bx1 + pad_x + 4, by1 + pad_y - 2), label, font=f_label, fill=WHITE)
    return base


def cover(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(340):
        a = int(230 * (i / 340) ** 1.1)
        d.line([(0, SIZE - 340 + i), (SIZE, SIZE - 340 + i)], fill=(8, 8, 10, a))
    for i in range(120):
        a = int(160 * (1 - i / 120))
        d.line([(0, i), (SIZE, i)], fill=(8, 8, 10, a))
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
    d.text((MARGIN, y + 168), "FIRE-TYPE INTAKE  ·  UNDER THE HEAT", font=f_sub, fill=SILVER)
    return base


def cta(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(110):
        a = int(170 * (1 - i / 110) ** 1.1)
        d.line([(0, i), (SIZE, i)], fill=(8, 8, 10, a))
    for i in range(300):
        a = int(235 * (i / 300) ** 1.05)
        d.line([(0, SIZE - 300 + i), (SIZE, SIZE - 300 + i)], fill=(8, 8, 10, a))
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


def compose(name: str, seed: int, scale: float = 0.86) -> Image.Image:
    raw = enhance(Image.open(SRC / name))
    lava = make_lava(SIZE, seed=seed)
    cut = cutout_rgba(raw)
    FILT.mkdir(parents=True, exist_ok=True)
    cut.save(FILT / f"cut_{Path(name).stem}.png")
    return fit_on_lava(cut, lava, scale=scale)


def build_reel(slide_paths: list[Path]) -> Path:
    REELS.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    HOLD, FADE, FPS = 2.0, 0.3, 30
    tmp = Path("/tmp/lava_reel_frames")
    tmp.mkdir(exist_ok=True)
    frames = []
    for i, p in enumerate(slide_paths):
        im = Image.open(p).convert("RGB")
        bg = im.copy().resize((W, H), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(40))
        bg = ImageEnhance.Brightness(bg).enhance(0.4)
        card = im.resize((W, W), Image.Resampling.LANCZOS)
        y = (H - W) // 2
        bg.paste(card, (0, y))
        d = ImageDraw.Draw(bg)
        d.rectangle([0, y - 6, W, y - 2], fill=EMBER)
        d.rectangle([0, y + W + 2, W, y + W + 6], fill=EMBER)
        fp = tmp / f"f_{i:02d}.jpg"
        bg.save(fp, "JPEG", quality=92)
        frames.append(fp)

    n = len(frames)
    inputs = []
    for f in frames:
        inputs += ["-loop", "1", "-t", str(HOLD), "-i", str(f)]
    parts = [f"[{i}:v]format=yuv420p,fps={FPS},setsar=1[v{i}]" for i in range(n)]
    prev = "v0"
    for i in range(1, n):
        out = "vout" if i == n - 1 else f"vx{i}"
        off = i * (HOLD - FADE)
        parts.append(f"[{prev}][v{i}]xfade=transition=fade:duration={FADE}:offset={off:.3f}[{out}]")
        prev = out
    out_mp4 = REELS / "tcg_hs_charizard_glvx_reel.mp4"
    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", "[vout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", str(FPS),
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    return out_mp4


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FILT.mkdir(parents=True, exist_ok=True)

    # Prebuild a few lava variants
    lava_cache = {s: make_lava(SIZE, seed=s) for s in range(1, 16)}

    def slide_from(src_name: str, seed: int, scale: float = 0.86) -> Image.Image:
        raw = enhance(Image.open(SRC / src_name))
        cut = cutout_rgba(raw)
        FILT.mkdir(exist_ok=True)
        cut.save(FILT / f"cut_{Path(src_name).stem}.png")
        return fit_on_lava(cut, lava_cache[seed], scale=scale)

    slides = [
        ("01_cover.jpg", cover(slide_from("IMG_5547.jpg", 1, 0.88))),
        ("02_inspection.jpg", brand(slide_from("IMG_5533.jpg", 2, 0.92), "INSPECTION")),
        ("03_under_scope.jpg", brand(slide_from("IMG_5536.jpg", 3, 0.92), "UNDER THE SCOPE")),
        ("04_weakness_scope.jpg", brand(slide_from("IMG_5534.jpg", 4, 0.92), "WEAKNESS CHECK")),
        ("05_edge_whitening.jpg", brand(slide_from("IMG_5537.jpg", 5, 0.9), "EDGE WHITENING")),
        ("06_surface_wear.jpg", brand(slide_from("IMG_5531.jpg", 6, 0.9), "SURFACE WEAR")),
        ("07_weakness_detail.jpg", brand(slide_from("IMG_5532.jpg", 7, 0.9), "WEAKNESS DETAIL")),
        ("08_corner_wear.jpg", brand(slide_from("IMG_5550.jpg", 8, 0.9), "CORNER WEAR")),
        ("09_promo_edge.jpg", brand(slide_from("IMG_5549.jpg", 9, 0.9), "PROMO EDGE")),
        ("10_border_detail.jpg", brand(slide_from("IMG_5548.jpg", 10, 0.9), "BORDER DETAIL")),
        ("11_holo_scuffs.jpg", brand(slide_from("IMG_5557.jpg", 11, 0.9), "HOLO SCUFFS")),
        ("12_nameplate.jpg", brand(slide_from("IMG_5551.jpg", 12, 0.9), "NAMEPLATE")),
        ("13_cta.jpg", cta(slide_from("IMG_5529.jpg", 13, 0.88))),
    ]

    paths = []
    for name, im in slides:
        p = OUT / name
        im.save(p, "JPEG", quality=94, optimize=True)
        paths.append(p)
        print("wrote", p)

    # caption
    caption = """Charizard G LV.X · Diamond & Pearl Promo (DP45)

Fire-type intake under the heat 🔥
Surface wear · edge whitening · weakness check · holo scuffs

Swipe the diagnosis
Healing starts at @tcg_h_s
TCG Healing Station

DM to book your card.

#tcghealingstation #tcg_h_s #pokemoncards #pokemontcg #charizard #charizardglvx #diamondandpearl #cardrestoration #cardcleaning #tcgrepair #firetype #thehobby #pokemoncommunity
"""
    Path("/agent/output/instagram_caption.txt").write_text(caption)

    reel = build_reel(paths)
    print("reel", reel)
    print("DONE", len(slides), "slides")


if __name__ == "__main__":
    main()
