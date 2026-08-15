#!/usr/bin/env python3
"""Checks the Instagram posting pack is upload-ready."""

from __future__ import annotations

import unittest
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "instagram" / "feed"
STORIES = ROOT / "instagram" / "stories"
ZIP_PATH = ROOT / "tcg_hs_charizard_glvx_instagram_post.zip"


class TestInstagramPack(unittest.TestCase):
    def test_feed_slides_are_instagram_4x5(self) -> None:
        files = sorted(FEED.glob("*.jpg"))
        self.assertEqual([p.name for p in files], [f"{i:02d}.jpg" for i in range(1, 11)])
        for path in files:
            with Image.open(path) as im:
                self.assertEqual(im.size, (1080, 1350), path.name)
                self.assertEqual(im.mode, "RGB")
                self.assertEqual(im.format, "JPEG")
                self.assertIn("icc_profile", im.info)
                self.assertLess(path.stat().st_size, 8 * 1024 * 1024)

    def test_story_is_9x16(self) -> None:
        path = STORIES / "01_hero.jpg"
        self.assertTrue(path.exists())
        with Image.open(path) as im:
            self.assertEqual(im.size, (1080, 1920))
            self.assertEqual(im.format, "JPEG")
            self.assertIn("icc_profile", im.info)

    def test_caption_and_alt_text_exist(self) -> None:
        caption = (ROOT / "instagram" / "caption.txt").read_text()
        self.assertIn("@tcg_h_s", caption)
        self.assertLessEqual(len(caption), 2200)
        alt = (ROOT / "instagram" / "alt_text.txt").read_text()
        self.assertEqual(alt.count("Slide "), 10)

    def test_posting_zip_has_only_upload_files(self) -> None:
        self.assertTrue(ZIP_PATH.exists())
        with zipfile.ZipFile(ZIP_PATH) as zf:
            names = set(zf.namelist())
        expected_feed = {f"feed/{i:02d}.jpg" for i in range(1, 11)}
        self.assertTrue(expected_feed <= names)
        self.assertIn("caption.txt", names)
        self.assertIn("HOW_TO_POST.txt", names)
        self.assertIn("stories/01_hero.jpg", names)
        self.assertFalse(any(n.endswith("hero_filtered.jpg") for n in names))
        self.assertFalse(any(n.endswith(".zip") for n in names))


if __name__ == "__main__":
    unittest.main()
