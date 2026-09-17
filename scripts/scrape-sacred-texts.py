#!/usr/bin/env python3
"""Scrape https://archive.sacred-texts.com/oah/oah/ into content/books/<slug>/chapter-NN.json."""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE_URL = "https://archive.sacred-texts.com/oah/oah/"
ROOT = Path(__file__).parent.parent
BOOKS_JSON = ROOT / "content" / "meta" / "books.json"
CONTENT_DIR = ROOT / "content" / "books"
PLATES_JSON = ROOT / "content" / "meta" / "plates.json"


def _build_img_id_to_plate_id() -> dict[str, int]:
    """Load plates.json and return {img_id: plate_integer_id}. Graceful on missing file."""
    if not PLATES_JSON.exists():
        return {}
    data = json.loads(PLATES_JSON.read_text())
    return {p["img_id"]: p["id"] for p in data if p.get("img_id")}

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Book table: maps (file_start, file_end) ranges to book slug + title.
# We derive this from the index structure discovered by reading index.htm.
# Each tuple: (first_oah_file_no, last_oah_file_no, slug, title)
# ---------------------------------------------------------------------------
BOOK_RANGES = [
    (9,  16,  "jehovih",          "Book of Jehovih"),
    (17, 39,  "sethantes",        "Book of Sethantes, Son of Jehovih"),
    (40, 43,  "first-lords",      "First Book of the First Lords"),
    (44, 52,  "ahshong",          "Book of Ah'shong, Son of Jehovih"),
    (53, 54,  "second-lords",     "Second Book of Lords"),
    (55, 57,  "synopsis",         "Synopsis of Sixteen Cycles"),
    (58, 74,  "aph",              "Book of Aph, Son of Jehovih"),
    (75, 77,  "lords-first",      "The Lord's First Book"),
    (78, 84,  "sue",              "Book of Sue, Son of Jehovih"),
    (85, 87,  "lords-second",     "The Lords' Second Book"),
    (88, 102, "apollo",           "Book of Apollo, Son of Jehovih"),
    (103,105, "lords-third",      "The Lord's Third Book"),
    (106,111, "thor",             "Book of Thor, Son of Jehovih"),
    (112,115, "lords-fourth",     "The Lord's Fourth Book"),
    (116,128, "osiris",           "Book of Osiris, Son of Jehovih"),
    (129,135, "lords-fifth",      "The Lord's Fifth Book"),
    (136,178, "fragapatti",       "Book of Fragapatti, Son of Jehovih"),
    (179,207, "gods-word",        "Book of God's Word"),
    (208,225, "divinity",         "Book of Divinity"),
    (226,238, "cpenta-armij",     "Book of Cpenta-Armij, Daughter of Jehovih"),
    (239,266, "gods-first",       "God's First Book"),
    (267,321, "wars",             "Book of Wars Against Jehovih"),
    (322,347, "lika",             "Book of Lika, Son of Jehovih"),
    (348,378, "arc-of-bon",       "Book of the Arc of Bon"),
    (379,389, "gods-ben",         "God's Book of Ben"),
    (390,412, "cosmology",        "Book of Cosmology and Prophecy"),
    (413,442, "saphah",           "Book of Saphah"),
    (443,483, "bons-praise",      "Bon's Book of Praise"),
    (484,543, "eskra",            "God's Book of Eskra"),
    (544,563, "es",               "Book of Es, Daughter of Jehova"),
    (564,601, "judgement",        "Book of Judgement"),
    (602,618, "inspiration",      "Book of Inspiration"),
    (619,644, "jehovih-kingdom",  "Book of Jehovih's Kingdom on Earth"),
    (645,658, "discipline",       "Book of Discipline"),
]

def file_no_to_book(n: int):
    """Return (slug, title) for a given oah file number."""
    for start, end, slug, title in BOOK_RANGES:
        if start <= n <= end:
            return slug, title
    return None, None

def chapter_within_book(n: int) -> int:
    """Return 1-based chapter index within its book."""
    for start, end, slug, title in BOOK_RANGES:
        if start <= n <= end:
            return n - start + 1
    return 0

def slugify_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

HTML_CACHE = Path(__file__).parent / ".htmlcache"

def fetch(url: str) -> BeautifulSoup:
    """Cache-first: read scripts/.htmlcache/<file>.htm if present (Cloudflare blocks
    plain requests; prefetch via a real browser into the cache). Else HTTP fallback."""
    cached = HTML_CACHE / url.rsplit("/", 1)[-1]
    if cached.exists():
        return BeautifulSoup(cached.read_text(encoding="utf-8"), "html.parser")
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")

def extract_chapter(
    soup: BeautifulSoup,
    book_slug: str,
    chapter_num: int,
    book_title: str,
    img_lookup: dict[str, int],
):
    """Parse a chapter page into the canonical JSON structure."""
    body = soup.find("body") or soup

    # Collect visible text blocks in document order.
    # Skip <center> (nav breadcrumb + image alignment, never verse content).
    paragraphs = []
    for tag in body.find_all(["p", "blockquote", "h1", "h2", "h3"]):
        text = tag.get_text(" ", strip=True)
        if text:
            paragraphs.append((tag, text))

    # Split paragraphs into preamble and verses.
    # A verse starts with a digit followed by a period at the beginning.
    verse_re = re.compile(r"^(\d+)\.\s+(.*)", re.DOTALL)
    page_re = re.compile(r"^p\.\s*\d+\s*$", re.I)          # page marker "p. 6"
    chap_re = re.compile(r"^Chapter\s+[\dIVXLCivxlc]+\s*$")  # redundant "Chapter I"
    preamble_parts = []
    raw_verses = []  # list of (verse_num, text, img_src_or_none)
    in_verses = False

    for tag, text in paragraphs:
        m = verse_re.match(text)
        if m:
            in_verses = True
            vnum = int(m.group(1))
            vtext = m.group(2).strip()
            # Capture img src immediately adjacent to this verse paragraph
            img = tag.find("img")
            raw_img = img.get("src") if img else None
            raw_verses.append((vnum, vtext, raw_img))
        elif not in_verses:
            # Drop page markers, redundant title/chapter headings
            if page_re.match(text) or chap_re.match(text):
                continue
            if text.strip().lower() == book_title.lower():
                continue
            preamble_parts.append(text)

    preamble = " ".join(preamble_parts).strip()

    chapter_id = f"{book_slug}.{chapter_num}"
    title_str = f"{book_title} — Chapter {chapter_num}"

    verses = []
    for vnum, vtext, raw_img in raw_verses:
        # Resolve img src to integer plate id; None if unrecognised or absent
        plate_ref: int | None = None
        if raw_img:
            # Sacred Texts img src values look like "img/03700.jpg" or just "03700.jpg"
            stem = re.sub(r"^img/", "", raw_img).removesuffix(".jpg")
            plate_ref = img_lookup.get(stem)
        verses.append({
            "id": f"{chapter_id}.{vnum}",
            "verse_number": vnum,
            "en": vtext,
            "zh_hant": None,
            "zh_hans": None,
            "ja": None,
            "glossary_terms": [],
            "plate_ref": plate_ref,
            "notes": [],
        })

    return {
        "id": chapter_id,
        "book": book_slug,
        "chapter": chapter_num,
        "title": title_str,
        "preamble": preamble,
        "verses": verses,
    }

def build_books_json():
    """Create content/meta/books.json from BOOK_RANGES (chapter counts unknown until scrape)."""
    books = [
        {"slug": slug, "title": title, "chapter_count": end - start + 1}
        for start, end, slug, title in BOOK_RANGES
    ]
    BOOKS_JSON.parent.mkdir(parents=True, exist_ok=True)
    BOOKS_JSON.write_text(json.dumps(books, indent=2, ensure_ascii=False))
    return books

def collect_chapter_urls():
    """Return list of (file_no, url) for every chapter page."""
    # We know the complete range is oah09 through oah658 from the index.
    # The index also lists front-matter files (oah00-oah08) which are not chapters.
    urls = []
    for file_no in range(9, 659):
        book_slug, _ = file_no_to_book(file_no)
        if book_slug is None:
            continue  # gap (shouldn't happen)
        urls.append((file_no, f"{BASE_URL}oah{file_no:02d}.htm"))
    return urls

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Oahspe from Sacred Texts")
    parser.add_argument("--force", action="store_true", help="Re-scrape already-scraped files")
    parser.add_argument("--book", default=None, help="Only scrape this book slug")
    args = parser.parse_args()

    print("Building books.json …")
    build_books_json()
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    img_lookup = _build_img_id_to_plate_id()
    print(f"Loaded {len(img_lookup)} plate img_id mappings.")

    chapter_urls = collect_chapter_urls()

    skipped = 0
    errors = []
    for file_no, url in tqdm(chapter_urls, desc="Chapters", unit="ch"):
        book_slug, book_title = file_no_to_book(file_no)
        if args.book and book_slug != args.book:
            continue
        chapter_num = chapter_within_book(file_no)
        out_dir = CONTENT_DIR / book_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"chapter-{chapter_num:02d}.json"

        if out_path.exists() and not args.force:
            skipped += 1
            continue

        try:
            soup = fetch(url)
            chapter_data = extract_chapter(soup, book_slug, chapter_num, book_title, img_lookup)
            out_path.write_text(json.dumps(chapter_data, indent=2, ensure_ascii=False))
        except Exception as e:
            errors.append(f"oah{file_no}: {e}")
            tqdm.write(f"  ERROR oah{file_no}: {e}")
        finally:
            time.sleep(0.5)

    print(f"\nDone. Skipped {skipped} existing files.")
    if errors:
        print(f"{len(errors)} errors:")
        for e in errors:
            print(" ", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
