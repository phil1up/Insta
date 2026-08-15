# insta-

Instagram posting pack for **TCG Healing Station** (`@tcg_h_s`).

Instagram cannot upload a `.zip`. Post the numbered JPEGs.

## Charizard G LV.X (DP45) — post this

Upload these 10 images **in order** as one carousel:

| File | Slide |
|------|--------|
| `instagram/feed/01.jpg` | Cover |
| `instagram/feed/02.jpg` | Inspection |
| `instagram/feed/03.jpg` | Under the scope |
| `instagram/feed/04.jpg` | Edge whitening |
| `instagram/feed/05.jpg` | Surface wear |
| `instagram/feed/06.jpg` | Corner wear |
| `instagram/feed/07.jpg` | Promo edge |
| `instagram/feed/08.jpg` | Border detail |
| `instagram/feed/09.jpg` | Holo scuffs |
| `instagram/feed/10.jpg` | CTA |

Each feed file is **1080×1350 (4:5)** JPEG, sRGB — Instagram’s recommended feed size.

- Caption: [`instagram/caption.txt`](instagram/caption.txt) (same copy in [`instagram_caption.txt`](instagram_caption.txt))
- Alt text: [`instagram/alt_text.txt`](instagram/alt_text.txt)
- Step-by-step: [`instagram/HOW_TO_POST.txt`](instagram/HOW_TO_POST.txt)
- Download pack: [`tcg_hs_charizard_glvx_instagram_post.zip`](tcg_hs_charizard_glvx_instagram_post.zip)

Optional Story (do **not** add this to the carousel): `instagram/stories/01_hero.jpg` (1080×1920).

## How to post

**Desktop (easiest)**

1. Open [Meta Business Suite](https://business.facebook.com) as `@tcg_h_s`.
2. Create post → Instagram → Carousel.
3. Upload `01.jpg` through `10.jpg` from `instagram/feed/` (or unzip the posting zip and use `feed/`).
4. Paste `instagram/caption.txt`.
5. Add alt text from `instagram/alt_text.txt`.
6. Publish or schedule.

**Phone**

1. Save `instagram/feed/01.jpg` … `10.jpg` to Camera Roll / Gallery.
2. Instagram → **+** → Post → select **01**, then **02**, … **10**.
3. Keep the **4:5 / original** crop. Do not pinch-zoom.
4. Paste the caption and share.

## Source files

Square 1080×1080 masters live in `slides/`. Rebuild the posting pack with:

```bash
pip install -r requirements.txt
python3 scripts/pack_instagram.py
python3 -m unittest tests/test_instagram_pack.py
```

Original square zip: `tcg_hs_charizard_glvx_carousel.zip`  
Carousel builder (needs source photos): `scripts/build_carousel.py`
