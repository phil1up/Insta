#!/usr/bin/env python3
"""Rebuild carousel on Pokemon hospital background with CARD BOO-BOO / HEALED / DISCHARGED labels."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

SRC = Path("/agent/source-photos/drive2_jpg")
OUT = Path("/agent/output/slides")
FONTS = Path("/agent/fonts")
REELS = Path("/agent/output/reels")
BG_PATH = Path("/opt/cursor/artifacts/assets/pokemon_hospital_bg.png")

SIZE = 1080
MARGIN = 48
TEAL = (46, 160, 170)
TEAL_SOFT = (90, 200, 205)
PINK = (255, 120, 150)
WHITE = (255, 255, 255)
INK = (25, 30, 40)
SILVER = (220, 225, 230)


def font(name: str, size: int):
    path = FONTS / name
    if not path.exists():
        path = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
    return ImageFont.truetype(str(path), size)


def enhance(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=150, threshold=1))
    im = ImageEnhance.Contrast(im).enhance(1.2)
    im = ImageEnhance.Color(im).enhance(1.12)
    im = ImageEnhance.Brightness(im).enhance(1.03)
    im = ImageEnhance.Sharpness(im).enhance(1.5)
    return im


def hospital_bg(variant: int = 0) -> Image.Image:
    bg = Image.open(BG_PATH).convert("RGB")
    bg = ImageOps.fit(bg, (SIZE, SIZE), Image.Resampling.LANCZOS)
    # Soften / dim a bit so card + labels stay readable
    bg = ImageEnhance.Brightness(bg).enhance(0.78 if variant % 2 == 0 else 0.72)
    bg = ImageEnhance.Color(bg).enhance(1.05)
    # Slight center spotlight
    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(SIZE // 2, 0, -2):
        a = int(90 * (1 - i / (SIZE / 2)) ** 1.6)
        # vignette from edges
        d.rectangle([0, 0, SIZE, SIZE // 2 - i], fill=(0, 0, 0, a // 3))
        d.rectangle([0, SIZE // 2 + i, SIZE, SIZE], fill=(0, 0, 0, a // 3))
    # Keep center clearer with a soft light wash
    for r in range(420, 0, -8):
        a = int(28 * (1 - r / 420) ** 2)
        d.ellipse([SIZE // 2 - r, SIZE // 2 - r + 40, SIZE // 2 + r, SIZE // 2 + r + 40], fill=(255, 255, 255, a))
    out = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    if variant % 3 == 1:
        out = ImageOps.mirror(out)
    if variant % 3 == 2:
        out = ImageEnhance.Color(out).enhance(1.15)
    return out


def photo_on_mat(photo: Image.Image, bg: Image.Image, scale: float = 0.78) -> Image.Image:
    """Clinical mat keeps every edge pixel for damage visibility."""
    canvas = bg.copy().convert("RGB")
    photo = photo.convert("RGB")
    max_side = int(SIZE * scale)
    photo = ImageOps.contain(photo, (max_side, max_side), Image.Resampling.LANCZOS)

    pad = 16
    mat_w, mat_h = photo.width + pad * 2, photo.height + pad * 2
    mat = Image.new("RGB", (mat_w, mat_h), (255, 255, 255))
    d = ImageDraw.Draw(mat)
    d.rectangle([0, 0, mat_w - 1, mat_h - 1], outline=(46, 160, 170), width=4)
    d.rectangle([5, 5, mat_w - 6, mat_h - 6], outline=(230, 240, 242), width=1)
    mat.paste(photo, (pad, pad))

    x = (SIZE - mat_w) // 2
    y = (SIZE - mat_h) // 2 - 10

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", (mat_w + 36, mat_h + 36), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([0, 0, mat_w + 35, mat_h + 35], radius=10, fill=(0, 0, 0, 90))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    shadow.paste(sh, (x - 18 + 6, y - 18 + 12), sh)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
    canvas.paste(mat, (x, y))
    return canvas


def text_size(draw, text, fnt):
    b = draw.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0], b[3] - b[1]


def brand(im: Image.Image, status: str) -> Image.Image:
    """status: CARD BOO-BOO, HEALED, or DISCHARGED"""
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(200):
        a = int(200 * (i / 200) ** 1.25)
        d.line([(0, SIZE - 200 + i), (SIZE, SIZE - 200 + i)], fill=(12, 18, 24, a))
    for i in range(100):
        a = int(170 * (1 - i / 100) ** 1.1)
        d.line([(0, i), (SIZE, i)], fill=(12, 18, 24, a))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)

    f_brand = font("BebasNeue-Regular.ttf", 42)
    f_handle = font("Montserrat-SemiBold.ttf", 22)
    f_status = font("Oswald-Bold.ttf", 40)
    f_small = font("Montserrat-SemiBold.ttf", 18)

    d.text((MARGIN, 28), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.text((MARGIN, 72), "@tcg_h_s", font=f_handle, fill=TEAL_SOFT)
    d.rectangle([MARGIN, 104, MARGIN + 72, 108], fill=TEAL)

    d.text((MARGIN, SIZE - MARGIN - 28), "CHARIZARD G LV.X  ·  DP45", font=f_small, fill=SILVER)

    # Status badge
    is_positive = status.upper() in {"HEALED", "DISCHARGED"}
    accent = TEAL if is_positive else PINK
    tw, th = text_size(d, status, f_status)
    pad_x, pad_y = 20, 12
    bx1 = SIZE - MARGIN - tw - pad_x * 2
    by1 = SIZE - MARGIN - th - pad_y * 2 - 8
    bx2, by2 = SIZE - MARGIN, SIZE - MARGIN - 8
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=8, fill=(16, 22, 28))
    d.rectangle([bx1, by1, bx1 + 6, by2], fill=accent)
    d.text((bx1 + pad_x + 4, by1 + pad_y - 2), status, font=f_status, fill=WHITE)
    return base


def cover(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(360):
        a = int(230 * (i / 360) ** 1.1)
        d.line([(0, SIZE - 360 + i), (SIZE, SIZE - 360 + i)], fill=(12, 18, 24, a))
    for i in range(120):
        a = int(160 * (1 - i / 120))
        d.line([(0, i), (SIZE, i)], fill=(12, 18, 24, a))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)
    f_brand = font("BebasNeue-Regular.ttf", 50)
    f_title = font("BebasNeue-Regular.ttf", 74)
    f_sub = font("Montserrat-SemiBold.ttf", 26)
    f_handle = font("Montserrat-SemiBold.ttf", 24)
    f_status = font("Oswald-Bold.ttf", 42)

    d.text((MARGIN, 30), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.text((MARGIN, 84), "@tcg_h_s", font=f_handle, fill=TEAL_SOFT)
    d.rectangle([MARGIN, 118, MARGIN + 90, 122], fill=TEAL)

    y = SIZE - 280
    d.text((MARGIN, y), "CHARIZARD G", font=f_title, fill=WHITE)
    d.text((MARGIN, y + 74), "LV.X  ·  DP PROMO", font=f_title, fill=TEAL_SOFT)
    d.text((MARGIN, y + 158), "POKEMON HOSPITAL INTAKE", font=f_sub, fill=SILVER)

    # Big CARD BOO-BOO badge
    status = "CARD BOO-BOO"
    tw, th = text_size(d, status, f_status)
    bx1, by1 = SIZE - MARGIN - tw - 40, SIZE - MARGIN - th - 28
    bx2, by2 = SIZE - MARGIN, SIZE - MARGIN - 8
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=8, fill=(16, 22, 28))
    d.rectangle([bx1, by1, bx1 + 6, by2], fill=PINK)
    d.text((bx1 + 22, by1 + 8), status, font=f_status, fill=WHITE)
    return base


def discharged_slide(im: Image.Image) -> Image.Image:
    """Finale: DISCHARGED with full bill of health."""
    im = im.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(360):
        a = int(230 * (i / 360) ** 1.1)
        d.line([(0, SIZE - 360 + i), (SIZE, SIZE - 360 + i)], fill=(12, 18, 24, a))
    for i in range(110):
        a = int(150 * (1 - i / 110))
        d.line([(0, i), (SIZE, i)], fill=(12, 18, 24, a))
    base = Image.alpha_composite(im, overlay).convert("RGB")
    d = ImageDraw.Draw(base)
    f_brand = font("BebasNeue-Regular.ttf", 48)
    f_big = font("BebasNeue-Regular.ttf", 78)
    f_mid = font("BebasNeue-Regular.ttf", 48)
    f_handle = font("Oswald-Bold.ttf", 36)
    f_sub = font("Montserrat-SemiBold.ttf", 22)
    f_status = font("Oswald-Bold.ttf", 40)

    d.text((MARGIN, 34), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.rectangle([MARGIN, 90, MARGIN + 90, 94], fill=TEAL)

    y = SIZE - 290
    d.text((MARGIN, y), "DISCHARGED", font=f_big, fill=TEAL_SOFT)
    d.text((MARGIN, y + 78), "FULL BILL OF HEALTH", font=f_mid, fill=WHITE)
    d.text((MARGIN, y + 140), "@TCG_H_S", font=f_handle, fill=WHITE)
    d.text((MARGIN, y + 195), "DM TO BOOK YOUR CARD  ·  FOLLOW FOR THE HEAL", font=f_sub, fill=SILVER)

    # Bottom-right status badge
    status = "DISCHARGED"
    tw, th = text_size(d, status, f_status)
    pad_x, pad_y = 20, 12
    bx1 = SIZE - MARGIN - tw - pad_x * 2
    by1 = SIZE - MARGIN - th - pad_y * 2 - 8
    bx2, by2 = SIZE - MARGIN, SIZE - MARGIN - 8
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=8, fill=(16, 22, 28))
    d.rectangle([bx1, by1, bx1 + 6, by2], fill=TEAL)
    d.text((bx1 + pad_x + 4, by1 + pad_y - 2), status, font=f_status, fill=WHITE)
    return base


def build_reel(paths: list[Path]) -> Path:
    REELS.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    HOLD, FADE, FPS = 2.0, 0.28, 30
    tmp = Path("/tmp/poke_hospital_reel")
    tmp.mkdir(exist_ok=True)
    frames = []
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB")
        bg = ImageOps.fit(im, (W, H), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(34))
        bg = ImageEnhance.Brightness(bg).enhance(0.4)
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
    if not BG_PATH.exists():
        raise SystemExit(f"missing hospital bg: {BG_PATH}")

    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.jpg"):
        p.unlink()

    def make(src: str, variant: int, scale: float = 0.78) -> Image.Image:
        photo = enhance(Image.open(SRC / src))
        return photo_on_mat(photo, hospital_bg(variant), scale=scale)

    # Intake = CARD BOO-BOO, mid = HEALED, finale = DISCHARGED
    slides = [
        ("01_cover.jpg", cover(make("IMG_5547.jpg", 0, 0.70))),
        ("02_inspection.jpg", brand(make("IMG_5533.jpg", 1, 0.80), "CARD BOO-BOO")),
        ("03_under_scope.jpg", brand(make("IMG_5536.jpg", 2, 0.80), "CARD BOO-BOO")),
        ("04_weakness_scope.jpg", brand(make("IMG_5534.jpg", 3, 0.80), "CARD BOO-BOO")),
        ("05_edge_whitening.jpg", brand(make("IMG_5537.jpg", 4, 0.82), "CARD BOO-BOO")),
        ("06_surface_wear.jpg", brand(make("IMG_5531.jpg", 5, 0.78), "CARD BOO-BOO")),
        ("07_weakness_detail.jpg", brand(make("IMG_5532.jpg", 6, 0.78), "HEALED")),
        ("08_corner_wear.jpg", brand(make("IMG_5550.jpg", 7, 0.80), "HEALED")),
        ("09_promo_edge.jpg", brand(make("IMG_5549.jpg", 8, 0.80), "HEALED")),
        ("10_border_detail.jpg", brand(make("IMG_5548.jpg", 9, 0.80), "HEALED")),
        ("11_holo_scuffs.jpg", brand(make("IMG_5557.jpg", 10, 0.80), "HEALED")),
        ("12_nameplate.jpg", brand(make("IMG_5551.jpg", 11, 0.80), "HEALED")),
        ("13_discharged.jpg", discharged_slide(make("IMG_5529.jpg", 12, 0.72))),
    ]

    paths = []
    for name, im in slides:
        p = OUT / name
        im.save(p, "JPEG", quality=93, optimize=True)
        paths.append(p)
        print("wrote", p)
        # Keep legacy filename for the finale slide
        if name == "13_discharged.jpg":
            legacy = OUT / "13_healed.jpg"
            im.save(legacy, "JPEG", quality=93, optimize=True)
            print("wrote", legacy)

    Path("/agent/output/instagram_caption.txt").write_text(
        """Charizard G LV.X · DP Promo

Admitted to the Pokémon hospital at @tcg_h_s 🏥
Card boo-boos under the scope…

Swipe for the heal 💚

TCG Healing Station
DM to book your card.

#tcghealingstation #tcg_h_s #pokemoncards #pokemontcg #charizard #cardrestoration #cardcleaning #healed #cardbooboo #thehobby #pokemoncommunity
"""
    )
    reel = build_reel(paths)
    print("reel", reel)
    print("DONE", len(slides))


if __name__ == "__main__":
    main()
