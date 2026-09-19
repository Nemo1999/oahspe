#!/usr/bin/env python3
"""
Position 1882-edition images onto verses using the Word-export body HTML.

The Word HTML (sources/1882-word-html/OAHSPE-1882-Edition.html) carries named
chapter anchors (<a name="bj1"> = Book of Jehovih ch.1, "seth3" = Sethantes ch.3,
…) and numbered verses. We walk the DOM tracking the current (book, chapter) from
the anchor and the last-seen verse number, then attach each <img> to the verse it
follows. This yields EXACT positions, chapter-aware (verse numbers reset per chapter).

Output: writes an `images` array onto each affected verse in content/books/<slug>/
chapter-NN.json, and copies referenced images into static/plates/. Idempotent.

Only positions images for books/chapters that already exist as scraped JSON;
images for not-yet-scraped books are recorded in the sidecar map for later.
"""
import json
import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
SRC_HTML = ROOT / "sources" / "1882-word-html" / "OAHSPE-1882-Edition.html"
SRC_IMG_DIR = ROOT / "sources" / "1882-word-html"
CONTENT_DIR = ROOT / "content" / "books"
PLATES_DIR = ROOT / "site" / "static" / "plates" / "edition1882"
SIDECAR = ROOT / "content" / "meta" / "image-positions.json"

# Word anchor prefix → our book slug.
PREFIX_TO_SLUG = {
    "bj": "jehovih", "seth": "sethantes", "fbfl": "first-lords", "ahshong": "ahshong",
    "sbl": "second-lords", "synopsis": "synopsis", "aph": "aph", "lfb": "lords-first",
    "sue": "sue", "lsb": "lords-second", "apollo": "apollo", "ltb": "lords-third",
    "thor": "thor", "osiris": "osiris", "fragapatti": "fragapatti",
    "bkdivinity": "divinity", "cpentarmig": "cpenta-armij", "firstbkgod": "gods-first",
    "bkwars": "wars", "lika": "lika", "arcofbon": "arc-of-bon", "godsbkben": "gods-ben",
    "cosmogony": "cosmology", "eskra": "eskra", "inspiration": "inspiration", "shalem": "es",
}


def extract_positions() -> list[dict]:
    """Return [{image, book, chapter, after_verse}] in document order."""
    html = SRC_HTML.read_text(encoding="windows-1252", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    cur_prefix = cur_ch = None
    last_verse = 0
    out = []
    for el in soup.descendants:
        nm = getattr(el, "name", None)
        if nm == "a" and el.get("name"):
            m = re.match(r"^([a-z]+)(\d+)$", el.get("name"))
            if m and m.group(1) in PREFIX_TO_SLUG:
                cur_prefix, cur_ch = m.group(1), int(m.group(2))
                last_verse = 0
        elif isinstance(el, str):
            mv = re.match(r"^(\d+)\.\s", el.strip())
            if mv:
                last_verse = int(mv.group(1))
        elif nm == "img":
            f = el.get("src", "").split("/")[-1]
            if cur_prefix and f:
                out.append({
                    "image": f,
                    "book": PREFIX_TO_SLUG[cur_prefix],
                    "chapter": cur_ch,
                    "after_verse": last_verse,
                })
    return out


def main():
    positions = extract_positions()
    SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    SIDECAR.write_text(json.dumps(positions, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(positions)} image positions → {SIDECAR.relative_to(ROOT)}")

    PLATES_DIR.mkdir(parents=True, exist_ok=True)
    placed = missing_img = missing_verse = 0

    # Group by (book, chapter) so we open each chapter file once.
    by_ch: dict[tuple[str, int], list[dict]] = {}
    for p in positions:
        by_ch.setdefault((p["book"], p["chapter"]), []).append(p)

    for (book, chapter), imgs in by_ch.items():
        ch_path = CONTENT_DIR / book / f"chapter-{chapter:02d}.json"
        if not ch_path.exists():
            continue  # book/chapter not scraped yet — sidecar keeps the record
        chap = json.loads(ch_path.read_text(encoding="utf-8"))
        verses = {v["verse_number"]: v for v in chap["verses"]}
        changed = False
        for p in imgs:
            src_img = SRC_IMG_DIR / p["image"]
            if not src_img.exists():
                missing_img += 1
                continue
            # Attach to the verse it follows (fall back to verse 1 if after_verse=0).
            target = verses.get(p["after_verse"]) or verses.get(1)
            if not target:
                missing_verse += 1
                continue
            # Copy image into static/plates/edition1882/ (dedup by name).
            dst = PLATES_DIR / p["image"]
            if not dst.exists():
                shutil.copy2(src_img, dst)
            entry = {"src": f"/plates/edition1882/{p['image']}", "edition": "1882"}
            imgs_list = target.setdefault("images", [])
            if entry not in imgs_list:
                imgs_list.append(entry)
                placed += 1
                changed = True
        if changed:
            ch_path.write_text(json.dumps(chap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Placed {placed} images onto verses "
          f"({missing_img} not-yet-downloaded, {missing_verse} verse-miss).")


if __name__ == "__main__":
    main()
