#!/usr/bin/env python3
"""Build an Instagram Reels-ready vertical MP4 from carousel slides."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter, ImageEnhance

SLIDES_DIR = Path("/agent/output/slides")
OUT_DIR = Path("/agent/output/reels")
W, H = 1080, 1920  # Reels 9:16
HOLD_SEC = 2.15
FADE_SEC = 0.35
FPS = 30

ORDER = [
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


def make_vertical_frame(src: Path, dest: Path) -> None:
    """Square slide centered on blurred vertical 9:16 background."""
    im = Image.open(src).convert("RGB")
    # Blurred fill background
    bg = im.copy()
    bg = bg.resize((W, H), Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(42))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    bg = ImageEnhance.Color(bg).enhance(0.85)

    # Center square at ~1080 width (full width), vertically centered
    side = W
    card = im.resize((side, side), Image.Resampling.LANCZOS)
    y = (H - side) // 2
    bg.paste(card, (0, y))

    # Thin ember accent lines above/below the square
    from PIL import ImageDraw

    d = ImageDraw.Draw(bg)
    ember = (232, 92, 32)
    d.rectangle([0, y - 6, W, y - 2], fill=ember)
    d.rectangle([0, y + side + 2, W, y + side + 6], fill=ember)

    bg.save(dest, "JPEG", quality=93, optimize=True)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd[:8]), "...")
    subprocess.run(cmd, check=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reel_") as tmp:
        tmp_path = Path(tmp)
        frames = []
        for i, name in enumerate(ORDER):
            src = SLIDES_DIR / name
            if not src.exists():
                raise SystemExit(f"missing {src}")
            frame = tmp_path / f"v_{i:02d}.jpg"
            make_vertical_frame(src, frame)
            frames.append(frame)
            print(f"framed {name}")

        # Build xfade chain
        # Each clip duration = HOLD_SEC; xfade shortens total by FADE_SEC each transition
        n = len(frames)
        inputs = []
        for f in frames:
            inputs += ["-loop", "1", "-t", str(HOLD_SEC), "-i", str(f)]

        if n == 1:
            filter_complex = f"[0:v]format=yuv420p,fps={FPS}[v]"
            out_label = "[v]"
        else:
            # scale/format each, then xfade
            parts = []
            for i in range(n):
                parts.append(f"[{i}:v]format=yuv420p,fps={FPS},setsar=1[v{i}]")
            prev = "v0"
            # offset for xfade: cumulative (HOLD - FADE)
            offset = HOLD_SEC - FADE_SEC
            for i in range(1, n):
                out = "vout" if i == n - 1 else f"vx{i}"
                # offset is when fade starts relative to concatenated timeline of previous result
                # For chained xfades: offset_i = i * (HOLD_SEC - FADE_SEC)
                off = i * (HOLD_SEC - FADE_SEC)
                parts.append(
                    f"[{prev}][v{i}]xfade=transition=fade:duration={FADE_SEC}:offset={off:.3f}[{out}]"
                )
                prev = out
            filter_complex = ";".join(parts)
            out_label = "[vout]"

        out_mp4 = OUT_DIR / "tcg_hs_charizard_glvx_reel.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            out_label,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-r",
            str(FPS),
            str(out_mp4),
        ]
        run(cmd)

        # Also write a slightly shorter "hook" cut if useful? skip — one clean reel is enough
        probe = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size",
                "-show_entries",
                "stream=width,height",
                "-of",
                "default=noprint_wrappers=1",
                str(out_mp4),
            ],
            text=True,
        )
        print(probe)
        print("WROTE", out_mp4)


if __name__ == "__main__":
    main()
