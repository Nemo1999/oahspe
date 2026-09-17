#!/usr/bin/env python3
"""Download and thumbnail the 97 Oahspe illustration plates."""

import json
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image
from tqdm import tqdm

BASE_URL = "https://archive.sacred-texts.com/oah/oah/"
ROOT = Path(__file__).parent.parent
PLATES_JSON = ROOT / "content" / "meta" / "plates.json"
FULL_DIR = ROOT / "static" / "plates" / "full"
THUMB_DIR = ROOT / "static" / "plates" / "thumbs"
THUMB_MAX_W = 320

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "oahspe-scraper/1.0 (+https://github.com/Nemo1999/oahspe)"


def img_url(img_id: str) -> str:
    """Construct the Sacred Texts image URL.
    The img_id in plates.json corresponds to the filename stem used on the site.
    Pattern: https://archive.sacred-texts.com/oah/oah/img/{img_id}.jpg
    """
    return f"{BASE_URL}img/{img_id}.jpg"


def download_image(url: str) -> bytes:
    resp = SESSION.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def save_full(data: bytes, plate_id: int) -> Path:
    FULL_DIR.mkdir(parents=True, exist_ok=True)
    path = FULL_DIR / f"plate-{plate_id:03d}.jpg"
    path.write_bytes(data)
    return path


def make_thumb(data: bytes, plate_id: int) -> tuple[Path, int, int]:
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(BytesIO(data))
    orig_w, orig_h = img.size
    # Thumbnail scales in-place, preserving aspect ratio
    img.thumbnail((THUMB_MAX_W, 100_000))
    path = THUMB_DIR / f"plate-{plate_id:03d}-thumb.jpg"
    img.save(path, "JPEG", quality=85, optimize=True)
    return path, orig_w, orig_h


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download Oahspe plates")
    parser.add_argument("--force", action="store_true", help="Re-download already-saved plates")
    args = parser.parse_args()

    if not PLATES_JSON.exists():
        print(f"ERROR: {PLATES_JSON} not found. Run scrape-sacred-texts.py first.")
        sys.exit(1)

    plates = json.loads(PLATES_JSON.read_text())
    updated = False

    for plate in tqdm(plates, desc="Plates", unit="plate"):
        pid = plate["id"]
        img_id = plate.get("img_id", "")
        if not img_id:
            tqdm.write(f"  SKIP plate {pid}: no img_id")
            continue

        full_path = FULL_DIR / f"plate-{pid:03d}.jpg"
        thumb_path = THUMB_DIR / f"plate-{pid:03d}-thumb.jpg"

        if full_path.exists() and thumb_path.exists() and not args.force:
            continue

        url = img_url(img_id)
        try:
            data = download_image(url)
        except Exception as e:
            tqdm.write(f"  ERROR plate {pid} ({url}): {e}")
            continue

        if not full_path.exists() or args.force:
            save_full(data, pid)

        if not thumb_path.exists() or args.force:
            _, w, h = make_thumb(data, pid)
            plate["width"] = w
            plate["height"] = h
            updated = True

        plate["full"] = f"plates/full/plate-{pid:03d}.jpg"
        plate["thumb"] = f"plates/thumbs/plate-{pid:03d}-thumb.jpg"
        updated = True
        time.sleep(0.3)

    if updated:
        PLATES_JSON.write_text(json.dumps(plates, indent=2, ensure_ascii=False))
        print("plates.json updated.")

    print("Done.")


if __name__ == "__main__":
    main()
