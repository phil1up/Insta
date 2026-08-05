#!/usr/bin/env python3
"""Rebuild carousel with clinical hospital backgrounds and edge-preserving crops."""

from __future__ import annotations

import math
import random
import subprocess
from io import BytesIO
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
TEAL = (46, 160, 170)
TEAL_SOFT = (120, 210, 215)
WHITE = (255, 255, 255)
INK = (20, 28, 34)
SILVER = (200, 210, 215)
EMBER = (232, 92, 32)  # keep accent for CTA labels only lightly


def font(name: str, size: int):
    path = FONTS / name
    if not path.exists():
        path = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
    return ImageFont.truetype(str(path), size)


def enhance(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=150, threshold=1))
    im = ImageEnhance.Contrast(im).enhance(1.22)
    im = ImageEnhance.Color(im).enhance(1.12)
    im = ImageEnhance.Brightness(im).enhance(1.03)
    im = ImageEnhance.Sharpness(im).enhance(1.55)
    return im


def make_hospital(size: int = SIZE, seed: int = 3) -> Image.Image:
    """Bright clinical hospital backdrop so card edges/whitening pop.

    Sterile white + soft mint, tile wall, clean tray — high contrast vs
    silver borders and white edge damage.
    """
    rng = random.Random(seed)
    w = h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    # Bright sterile wall (white -> soft clinical mint)
    t = yy / h
    r = 236 - t * 8
    g = 244 - t * 4
    b = 248 - t * 2
    arr = np.dstack([r, g, b]).astype(np.float32)

    # Soft overhead OR light
    cx, cy = w * 0.5, h * 0.2
    dist = np.sqrt(((xx - cx) / (w * 0.7)) ** 2 + ((yy - cy) / (h * 0.85)) ** 2)
    light = np.clip(1.1 - dist, 0, 1) ** 1.8
    arr += light[:, :, None] * np.array([18, 20, 16])

    # Clean hospital tile grid (light lines)
    tile = 72
    gx = ((xx % tile) < 1.2) | ((yy % tile) < 1.2)
    arr[gx] = arr[gx] * 0.92 + np.array([170, 200, 205]) * 0.08

    # Soft mint wall panels
    for i in range(2):
        px = rng.uniform(0.2, 0.8) * w
        band = np.exp(-((xx - px) ** 2) / (2 * (55 + 25 * i) ** 2))
        arr += band[:, :, None] * np.array([4, 14, 16])

    # Faint medical cross watermark
    cross = np.zeros((h, w), dtype=np.float32)
    cw, ch = int(w * 0.05), int(h * 0.16)
    cx0, cy0 = w // 2, int(h * 0.4)
    cross[cy0 - ch // 2 : cy0 + ch // 2, cx0 - cw // 2 : cx0 + cw // 2] = 1
    cross[cy0 - cw // 2 : cy0 + cw // 2, cx0 - ch // 2 : cx0 + ch // 2] = 1
    cross = Image.fromarray((cross * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(22))
    cross_a = np.array(cross).astype(np.float32) / 255.0
    arr = arr * (1 - 0.06 * cross_a[:, :, None]) + cross_a[:, :, None] * np.array([200, 230, 232])

    # Steel instrument tray at bottom (slightly cooler gray so cards lift)
    tray = np.clip((yy - h * 0.82) / (h * 0.18), 0, 1)
    tray_col = np.array([210, 220, 224], dtype=np.float32)
    arr = arr * (1 - 0.55 * tray[:, :, None]) + tray_col * (0.55 * tray[:, :, None])

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGB")
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    return im


def cutout_preserve_edges(im: Image.Image) -> Image.Image:
    """Background remove while protecting pale card-edge whitening."""
    im = im.convert("RGB")
    rgba = None
    if rembg_remove is not None:
        try:
            out = rembg_remove(im)
            if isinstance(out, (bytes, bytearray)):
                out = Image.open(BytesIO(out)).convert("RGBA")
            else:
                out = out.convert("RGBA")
            alpha = np.array(out.split()[-1])
            if alpha.mean() > 8:
                rgba = out
        except Exception as e:
            print("rembg failed:", e)

    if rgba is None:
        arr = np.array(im)
        r, g, b = arr[:, :, 0].astype(np.int16), arr[:, :, 1].astype(np.int16), arr[:, :, 2].astype(np.int16)
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        mx = np.maximum(np.maximum(r, g), b)
        mn = np.minimum(np.minimum(r, g), b)
        dark = lum < 42
        grayish = ((mx - mn) < 16) & (lum < 105)
        mask = ~(dark | grayish)
        mask_im = Image.fromarray((mask.astype(np.uint8) * 255), "L")
        mask_im = mask_im.filter(ImageFilter.MaxFilter(7))
        mask_im = mask_im.filter(ImageFilter.MinFilter(3))
        rgba = im.convert("RGBA")
        rgba.putalpha(mask_im)

    # Dilate alpha so worn white edges aren't shaved off
    a = rgba.split()[-1]
    a = a.point(lambda p: 255 if p > 20 else 0)
    a = a.filter(ImageFilter.MaxFilter(9))  # grow outward
    a = a.filter(ImageFilter.GaussianBlur(1.1))
    rgb = rgba.convert("RGB")
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def fit_on_hospital(subject: Image.Image, bg: Image.Image, scale: float = 0.82) -> Image.Image:
    """Place subject with room around edges so damage stays visible."""
    canvas = bg.copy().convert("RGBA")
    sub = subject.copy()
    bbox = sub.getbbox()
    if bbox:
        # pad bbox so we don't crop whitening at the crop stage
        pad = 12
        x0, y0, x1, y1 = bbox
        x0 = max(0, x0 - pad)
        y0 = max(0, y0 - pad)
        x1 = min(sub.width, x1 + pad)
        y1 = min(sub.height, y1 + pad)
        sub = sub.crop((x0, y0, x1, y1))

    max_w = int(SIZE * scale)
    max_h = int(SIZE * scale)
    sub.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    x = (SIZE - sub.width) // 2
    y = (SIZE - sub.height) // 2

    # Soft dark shadow — lifts card off bright hospital wall so edges read
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    alpha = sub.split()[-1]
    sh = Image.new("L", (sub.width + 48, sub.height + 48), 0)
    sh.paste(alpha, (24, 24))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    sh_rgba = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    sh_rgba.putalpha(sh.point(lambda p: int(p * 0.42)))
    shadow.paste(sh_rgba, (x - 24 + 4, y - 24 + 10), sh_rgba)
    canvas = Image.alpha_composite(canvas, shadow)

    canvas.paste(sub, (x, y), sub)
    return canvas.convert("RGB")


def text_size(draw, text, fnt):
    b = draw.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0], b[3] - b[1]


def brand(im: Image.Image, label: str | None = None) -> Image.Image:
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(210):
        a = int(195 * (i / 210) ** 1.3)
        d.line([(0, SIZE - 210 + i), (SIZE, SIZE - 210 + i)], fill=(10, 16, 20, a))
    for i in range(90):
        a = int(160 * (1 - i / 90) ** 1.1)
        d.line([(0, i), (SIZE, i)], fill=(10, 16, 20, a))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)
    f_brand = font("BebasNeue-Regular.ttf", 42)
    f_handle = font("Montserrat-SemiBold.ttf", 22)
    f_label = font("Oswald-Bold.ttf", 34)
    f_small = font("Montserrat-SemiBold.ttf", 18)
    d.text((MARGIN, 28), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.text((MARGIN, 72), "@tcg_h_s", font=f_handle, fill=TEAL_SOFT)
    d.rectangle([MARGIN, 104, MARGIN + 72, 108], fill=TEAL)
    d.text((MARGIN, SIZE - MARGIN - 28), "CHARIZARD G LV.X  ·  DP45", font=f_small, fill=SILVER)
    if label:
        tw, th = text_size(d, label, f_label)
        pad_x, pad_y = 18, 10
        bx1 = SIZE - MARGIN - tw - pad_x * 2
        by1 = SIZE - MARGIN - th - pad_y * 2 - 8
        bx2, by2 = SIZE - MARGIN, SIZE - MARGIN - 8
        d.rounded_rectangle([bx1, by1, bx2, by2], radius=6, fill=(16, 24, 28))
        d.rectangle([bx1, by1, bx1 + 5, by2], fill=TEAL)
        d.text((bx1 + pad_x + 4, by1 + pad_y - 2), label, font=f_label, fill=WHITE)
    return base


def cover(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(340):
        a = int(225 * (i / 340) ** 1.1)
        d.line([(0, SIZE - 340 + i), (SIZE, SIZE - 340 + i)], fill=(10, 16, 20, a))
    for i in range(120):
        a = int(150 * (1 - i / 120))
        d.line([(0, i), (SIZE, i)], fill=(10, 16, 20, a))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)
    f_brand = font("BebasNeue-Regular.ttf", 54)
    f_title = font("BebasNeue-Regular.ttf", 78)
    f_sub = font("Montserrat-SemiBold.ttf", 26)
    f_handle = font("Montserrat-SemiBold.ttf", 24)
    d.text((MARGIN, 34), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.text((MARGIN, 90), "@tcg_h_s", font=f_handle, fill=TEAL_SOFT)
    d.rectangle([MARGIN, 126, MARGIN + 90, 130], fill=TEAL)
    y = SIZE - 250
    d.text((MARGIN, y), "CHARIZARD G", font=f_title, fill=WHITE)
    d.text((MARGIN, y + 78), "LV.X  ·  DP PROMO", font=f_title, fill=TEAL_SOFT)
    d.text((MARGIN, y + 168), "ADMITTED FOR EDGE & SURFACE CARE", font=f_sub, fill=SILVER)
    return base


def cta(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(110):
        a = int(160 * (1 - i / 110) ** 1.1)
        d.line([(0, i), (SIZE, i)], fill=(10, 16, 20, a))
    for i in range(300):
        a = int(230 * (i / 300) ** 1.05)
        d.line([(0, SIZE - 300 + i), (SIZE, SIZE - 300 + i)], fill=(10, 16, 20, a))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)
    f_brand = font("BebasNeue-Regular.ttf", 48)
    f_big = font("BebasNeue-Regular.ttf", 70)
    f_sub = font("Montserrat-SemiBold.ttf", 24)
    d.text((MARGIN, 40), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.rectangle([MARGIN, 96, MARGIN + 90, 100], fill=TEAL)
    y = SIZE - 230
    d.text((MARGIN, y), "FOLLOW FOR THE HEAL", font=f_big, fill=WHITE)
    d.text((MARGIN, y + 78), "@tcg_h_s", font=f_big, fill=TEAL_SOFT)
    d.text((MARGIN, y + 160), "DM TO BOOK YOUR CARD  ·  SWIPE FOR DETAILS", font=f_sub, fill=SILVER)
    return base


def fit_photo_on_mat(photo: Image.Image, bg: Image.Image, scale: float = 0.78) -> Image.Image:
    """Place full photo on hospital bg inside a clinical mat — keeps EVERY edge pixel."""
    canvas = bg.copy().convert("RGB")
    photo = photo.convert("RGB")
    max_side = int(SIZE * scale)
    # Keep aspect, fit inside square mat
    photo = ImageOps.contain(photo, (max_side, max_side), Image.Resampling.LANCZOS)

    # White clinical mat with thin teal rule so card edges contrast
    pad = 18
    mat_w, mat_h = photo.width + pad * 2, photo.height + pad * 2
    mat = Image.new("RGB", (mat_w, mat_h), (252, 252, 253))
    d = ImageDraw.Draw(mat)
    d.rectangle([0, 0, mat_w - 1, mat_h - 1], outline=(46, 160, 170), width=3)
    d.rectangle([4, 4, mat_w - 5, mat_h - 5], outline=(220, 230, 232), width=1)
    mat.paste(photo, (pad, pad))

    x = (SIZE - mat_w) // 2
    y = (SIZE - mat_h) // 2

    # Soft shadow under mat
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", (mat_w + 30, mat_h + 30), (0, 0, 0, 0))
    sh_draw = ImageDraw.Draw(sh)
    sh_draw.rounded_rectangle([0, 0, mat_w + 29, mat_h + 29], radius=8, fill=(0, 0, 0, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    shadow.paste(sh, (x - 15 + 5, y - 15 + 10), sh)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
    canvas.paste(mat, (x, y))
    return canvas


def compose(name: str, seed: int, scale: float = 0.80, mode: str = "cutout") -> Image.Image:
    raw = enhance(Image.open(SRC / name))
    bg = make_hospital(SIZE, seed=seed)
    FILT.mkdir(parents=True, exist_ok=True)
    if mode == "mat":
        # Preserve edges/damage perfectly — no background removal
        return fit_photo_on_mat(raw, bg, scale=scale)
    cut = cutout_preserve_edges(raw)
    cut.save(FILT / f"cut_{Path(name).stem}.png")
    return fit_on_hospital(cut, bg, scale=scale)


def build_reel(slide_paths: list[Path]) -> Path:
    REELS.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    HOLD, FADE, FPS = 2.05, 0.3, 30
    tmp = Path("/tmp/hospital_reel_frames")
    tmp.mkdir(exist_ok=True)
    frames = []
    for i, p in enumerate(slide_paths):
        im = Image.open(p).convert("RGB")
        bg = im.copy().resize((W, H), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(36))
        bg = ImageEnhance.Brightness(bg).enhance(0.42)
        card = im.resize((W, W), Image.Resampling.LANCZOS)
        y = (H - W) // 2
        bg.paste(card, (0, y))
        d = ImageDraw.Draw(bg)
        d.rectangle([0, y - 6, W, y - 2], fill=TEAL)
        d.rectangle([0, y + W + 2, W, y + W + 6], fill=TEAL)
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
    subprocess.run(
        [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", ";".join(parts),
            "-map", "[vout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", str(FPS),
            str(out_mp4),
        ],
        check=True,
    )
    return out_mp4


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # clear old slides
    for p in OUT.glob("*.jpg"):
        p.unlink()

    def s(name, seed, scale=0.80, mode="mat"):
        return compose(name, seed, scale, mode=mode)

    # "mat" keeps every edge pixel visible (best for damage).
    # "cutout" only for clean hero cards.
    slides = [
        ("01_cover.jpg", cover(s("IMG_5547.jpg", 1, 0.72, "cutout"))),
        ("02_inspection.jpg", brand(s("IMG_5533.jpg", 2, 0.82, "mat"), "INSPECTION")),
        ("03_under_scope.jpg", brand(s("IMG_5536.jpg", 3, 0.82, "mat"), "UNDER THE SCOPE")),
        ("04_weakness_scope.jpg", brand(s("IMG_5534.jpg", 4, 0.82, "mat"), "WEAKNESS CHECK")),
        ("05_edge_whitening.jpg", brand(s("IMG_5537.jpg", 5, 0.84, "mat"), "EDGE WHITENING")),
        ("06_surface_wear.jpg", brand(s("IMG_5531.jpg", 6, 0.80, "mat"), "SURFACE WEAR")),
        ("07_weakness_detail.jpg", brand(s("IMG_5532.jpg", 7, 0.80, "mat"), "WEAKNESS DETAIL")),
        ("08_corner_wear.jpg", brand(s("IMG_5550.jpg", 8, 0.82, "mat"), "CORNER WEAR")),
        ("09_promo_edge.jpg", brand(s("IMG_5549.jpg", 9, 0.82, "mat"), "PROMO EDGE")),
        ("10_border_detail.jpg", brand(s("IMG_5548.jpg", 10, 0.82, "mat"), "BORDER DETAIL")),
        ("11_holo_scuffs.jpg", brand(s("IMG_5557.jpg", 11, 0.82, "mat"), "HOLO SCUFFS")),
        ("12_nameplate.jpg", brand(s("IMG_5551.jpg", 12, 0.82, "mat"), "NAMEPLATE")),
        ("13_cta.jpg", cta(s("IMG_5529.jpg", 13, 0.72, "cutout"))),
    ]

    paths = []
    for name, im in slides:
        p = OUT / name
        im.save(p, "JPEG", quality=94, optimize=True)
        paths.append(p)
        print("wrote", p)

    Path("/agent/output/instagram_caption.txt").write_text(
        """Charizard G LV.X · Diamond & Pearl Promo (DP45)

Admitted to TCG Healing Station 🏥
Edge whitening · surface wear · corner damage · holo scuffs

Swipe the diagnosis
Healing starts at @tcg_h_s

DM to book your card.

#tcghealingstation #tcg_h_s #pokemoncards #pokemontcg #charizard #charizardglvx #cardrestoration #cardcleaning #tcgrepair #thehobby #pokemoncommunity
"""
    )
    reel = build_reel(paths)
    print("reel", reel)
    print("DONE", len(slides))


if __name__ == "__main__":
    main()
