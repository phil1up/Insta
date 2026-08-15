#!/usr/bin/env python3
"""Turn the Charizard G LV.X carousel into an Instagram-ready posting pack.

Feed posts use 4:5 (1080×1350) so they fill the Instagram feed. Stories use
9:16 (1080×1920). Output is a folder of numbered JPEGs plus a zip you can
download and upload — Instagram cannot ingest a zip directly.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / "slides"
FILTERED = ROOT / "filtered"
OUT = ROOT / "instagram"
FEED = OUT / "feed"
STORIES = OUT / "stories"
FONTS = Path("/tmp/ig-assets/fonts")
LOCAL_FONTS = ROOT / "fonts"
ICC_PATH = Path("/tmp/ig-assets/sRGB.icc")

FEED_W, FEED_H = 1080, 1350
STORY_W, STORY_H = 1080, 1920
SQUARE = 1080
MARGIN = 48

CHARCOAL = (12, 12, 14)
EMBER = (232, 92, 32)
EMBER_SOFT = (255, 140, 70)
SILVER = (210, 214, 220)
WHITE = (255, 255, 255)

SLIDE_FILES = [
    "01_cover.jpg",
    "02_inspection.jpg",
    "03_under_scope.jpg",
    "04_edge_whitening.jpg",
    "05_surface_wear.jpg",
    "06_corner_damage.jpg",
    "07_promo_edge.jpg",
    "08_border_detail.jpg",
    "09_holo_scuffs.jpg",
    "10_cta.jpg",
]

ALT_TEXT = [
    "Charizard G LV.X Diamond & Pearl promo DP45 on a dark surface. Cover slide: TCG Healing Station intake and surface and edge diagnosis.",
    "Charizard G LV.X under a digital microscope during inspection, with the scope screen showing a magnified view of the card.",
    "Gloved hands holding Charizard G LV.X under a digital microscope. Screen shows a magnified close-up of the Cyrus portrait.",
    "Microscope close-up of edge whitening on the top-left corner of Charizard G LV.X, with visible fiber wear on the card edge.",
    "Macro photo of surface wear on Charizard G LV.X, focusing on the SP logo and card texture under bright inspection light.",
    "Macro photo of corner wear on the top-left of Charizard G LV.X, showing whitening and fray at the LEVEL-UP header.",
    "Macro photo of the DP45 promo star and holographic silver edge on the bottom-right corner of Charizard G LV.X.",
    "Macro photo of holographic border detail and the SP logo on Charizard G LV.X.",
    "Macro photo of holographic scuffs near the Cyrus portrait on Charizard G LV.X.",
    "Charizard G LV.X DP45 with TCG Healing Station call to action: follow @tcg_h_s and DM to book your card.",
]

CAPTION = """Charizard G LV.X · DP45 — intake complete.

Surface haze. Edge whitening. Corner wear. Holo scuffs.

Swipe through the diagnosis 🔍

Healing starts at @tcg_h_s
TCG Healing Station

DM to book your card.

#tcghealingstation #tcg_h_s #pokemoncards #pokemontcg #charizard #charizardglvx #diamondandpearl #cardrestoration #cardcleaning #tcgrepair #vintagepokemon #holo #thehobby #pokemoncommunity #cardcollector
"""

HOW_TO_POST = """HOW TO POST THIS CAROUSEL ON INSTAGRAM
======================================

Instagram cannot upload a .zip. Use the 10 JPEGs in feed/ (01.jpg → 10.jpg).

Desktop (easiest from this folder)
----------------------------------
1. Open Meta Business Suite: https://business.facebook.com
2. Switch to the @tcg_h_s Instagram account.
3. Create post → pick Instagram → Carousel.
4. Upload feed/01.jpg through feed/10.jpg IN ORDER (do not include stories/).
5. Paste caption.txt into the caption box.
6. Add alt text from alt_text.txt (one block per slide).
7. Preview on mobile, then Publish (or Schedule).

iPhone / Android
----------------
1. Unzip this pack and save feed/01.jpg … feed/10.jpg to Camera Roll / Gallery.
   Do not save the story image into the same selection.
2. Instagram → + → Post → Recents.
3. Select 01, then 02, then 03 … through 10 (order of first tap is the carousel order).
4. Leave the crop at original / 4:5. Do not pinch-zoom.
5. Paste caption.txt.
6. Edit → Alt text, paste each line from alt_text.txt.
7. Share.

Stories (optional extra)
------------------------
Upload stories/01_hero.jpg as a Story (9:16). Do not add it to the feed carousel.

Do not post
-----------
- This zip file itself
- stories/ inside the feed carousel
- Any file that is not 01.jpg–10.jpg
"""


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for folder in (FONTS, LOCAL_FONTS):
        path = folder / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    fallback = Path("/usr/share/fonts/truetype/macos/Inter-Bold.ttf")
    return ImageFont.truetype(str(fallback), size)


def icc_bytes() -> bytes | None:
    if ICC_PATH.exists():
        return ICC_PATH.read_bytes()
    return None


def save_jpeg(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "format": "JPEG",
        "quality": 95,
        "optimize": True,
        "progressive": False,
        "subsampling": 1,
    }
    profile = icc_bytes()
    if profile:
        kwargs["icc_profile"] = profile
    im.convert("RGB").save(path, **kwargs)


def patch_cta(im: Image.Image) -> Image.Image:
    """Remove the last-slide 'SWIPE FOR DETAILS' line (swipe belongs on slide 1)."""
    im = im.copy()
    band = im.crop((0, 988, SQUARE, 1004))
    band = band.resize((SQUARE, 92), Image.Resampling.BILINEAR)
    im.paste(band, (0, 988))
    d = ImageDraw.Draw(im)
    f_sub = font("Montserrat-SemiBold.ttf", 24)
    d.text((MARGIN, 1012), "DM TO BOOK YOUR CARD", font=f_sub, fill=SILVER)
    return im


def frame_feed(slide: Image.Image, index: int, total: int, kind: str) -> Image.Image:
    canvas = Image.new("RGB", (FEED_W, FEED_H), CHARCOAL)
    y = (FEED_H - SQUARE) // 2
    canvas.paste(slide.convert("RGB"), (0, y))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, y - 3, FEED_W, y], fill=EMBER)
    d.rectangle([0, y + SQUARE, FEED_W, y + SQUARE + 3], fill=EMBER)

    f_meta = font("Montserrat-SemiBold.ttf", 22)
    f_hint = font("Montserrat-SemiBold.ttf", 22)
    counter = f"{index:02d}  /  {total:02d}"
    cw = d.textlength(counter, font=f_meta)
    bar_top = y + SQUARE + 3
    cy = bar_top + (FEED_H - bar_top - 22) // 2
    d.text((FEED_W - MARGIN - cw, cy), counter, font=f_meta, fill=SILVER)

    if kind == "cover":
        d.text((MARGIN, cy - 2), "SWIPE  >", font=f_hint, fill=EMBER_SOFT)
    elif kind == "cta":
        d.text((MARGIN, cy - 2), "DM TO BOOK", font=f_hint, fill=EMBER_SOFT)
    return canvas


def make_story(hero: Image.Image) -> Image.Image:
    """9:16 Story with text kept inside Instagram safe zones.

    Username/chrome covers ~top 270px; reply bar covers ~bottom 350px.
    """
    canvas = Image.new("RGB", (STORY_W, STORY_H), CHARCOAL)
    # Photo starts below Instagram username chrome (~270px).
    y = 270
    canvas.paste(hero.convert("RGB"), (0, y))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, y - 3, STORY_W, y], fill=EMBER)
    d.rectangle([0, y + SQUARE, STORY_W, y + SQUARE + 3], fill=EMBER)

    f_brand = font("BebasNeue-Regular.ttf", 52)
    f_handle = font("Montserrat-SemiBold.ttf", 24)
    f_title = font("BebasNeue-Regular.ttf", 64)
    f_sub = font("Montserrat-SemiBold.ttf", 24)

    # Brand is drawn on the photo so it is not hidden by Stories chrome.
    d.text((MARGIN + 2, y + 22), "TCG HEALING STATION", font=f_brand, fill=(0, 0, 0))
    d.text((MARGIN, y + 20), "TCG HEALING STATION", font=f_brand, fill=WHITE)
    d.text((MARGIN, y + 76), "@tcg_h_s", font=f_handle, fill=EMBER_SOFT)
    d.rectangle([MARGIN, y + 110, MARGIN + 72, y + 114], fill=EMBER)

    by = y + SQUARE + 28
    d.text((MARGIN, by), "CHARIZARD G  LV.X", font=f_title, fill=WHITE)
    d.text((MARGIN, by + 66), "DP45  ·  INTAKE", font=f_title, fill=EMBER_SOFT)
    d.text((MARGIN, by + 140), "DM TO BOOK YOUR CARD", font=f_sub, fill=SILVER)
    return canvas


def write_text_files() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "caption.txt").write_text(CAPTION)
    alt_body = "\n\n".join(
        f"Slide {i:02d}\n{text}" for i, text in enumerate(ALT_TEXT, start=1)
    )
    (OUT / "alt_text.txt").write_text(alt_body + "\n")
    (OUT / "HOW_TO_POST.txt").write_text(HOW_TO_POST)


def build_zip(zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(FEED.glob("*.jpg")):
            zf.write(path, arcname=f"feed/{path.name}")
        for path in sorted(STORIES.glob("*.jpg")):
            zf.write(path, arcname=f"stories/{path.name}")
        for name in ("caption.txt", "alt_text.txt", "HOW_TO_POST.txt"):
            zf.write(OUT / name, arcname=name)


def main() -> None:
    FEED.mkdir(parents=True, exist_ok=True)
    STORIES.mkdir(parents=True, exist_ok=True)
    FILTERED.mkdir(parents=True, exist_ok=True)

    hero_src = SLIDES / "hero_filtered.jpg"
    hero_dst = FILTERED / "hero_filtered.jpg"
    if hero_src.exists() and not hero_dst.exists():
        hero_src.replace(hero_dst)
    elif hero_src.exists() and hero_dst.exists():
        hero_src.unlink()

    total = len(SLIDE_FILES)
    for i, name in enumerate(SLIDE_FILES, start=1):
        src = SLIDES / name
        if not src.exists():
            raise SystemExit(f"missing slide: {src}")
        slide = Image.open(src).convert("RGB")
        kind = "cover" if i == 1 else "cta" if i == total else "detail"
        if kind == "cta":
            slide = patch_cta(slide)
        framed = frame_feed(slide, i, total, kind)
        save_jpeg(framed, FEED / f"{i:02d}.jpg")
        print(f"feed {i:02d}.jpg {framed.size}")

    hero = Image.open(hero_dst).convert("RGB")
    story = make_story(hero)
    save_jpeg(story, STORIES / "01_hero.jpg")
    print(f"story 01_hero.jpg {story.size}")

    write_text_files()
    zip_path = ROOT / "tcg_hs_charizard_glvx_instagram_post.zip"
    build_zip(zip_path)
    print(f"wrote {zip_path}")
    print("DONE")


if __name__ == "__main__":
    main()
