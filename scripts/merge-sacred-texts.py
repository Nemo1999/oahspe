#!/usr/bin/env python3
"""Overlay Sacred Texts chapter epigraphs onto JSON preamble.en where empty.

Schema note:
  preamble = {"en": str, "zh_hant": str|null, "zh_hans": str|null, "ja": str|null}
  preamble_source = "word-1882" | "sacred-texts" | null

Precedence (per chapter):
  1. Word-HTML preamble present  → keep it, preamble_source = "word-1882"
  2. Sacred Texts has epigraph   → use it, preamble_source = "sacred-texts"
  3. Neither                     → leave empty, preamble_source = null

Re-runnable and idempotent: a second run makes no changes.
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Reused from scrape-sacred-texts.py — do not modify independently.
# ---------------------------------------------------------------------------
BOOK_RANGES = [
    (2,  2,   "general-statement", "A General Statement of the Contents of Oahspe"),
    (5,  5,   "prophets",          "List of the Principal Prophets and Law-Givers"),
    (6,  6,   "hints",             "Hints to the Reader"),
    (7,  7,   "oahspe-intro",      "Oahspe"),
    (8,  8,   "voice-of-man",      "The Voice of Man"),
    (9,  16,  "jehovih",           "Book of Jehovih"),
    (17, 39,  "sethantes",         "Book of Sethantes, Son of Jehovih"),
    (40, 43,  "first-lords",       "First Book of the First Lords"),
    (44, 52,  "ahshong",           "Book of Ah'shong, Son of Jehovih"),
    (53, 54,  "second-lords",      "Second Book of Lords"),
    (55, 57,  "synopsis",          "Synopsis of Sixteen Cycles"),
    (58, 74,  "aph",               "Book of Aph, Son of Jehovih"),
    (75, 77,  "lords-first",       "The Lord's First Book"),
    (78, 84,  "sue",               "Book of Sue, Son of Jehovih"),
    (85, 87,  "lords-second",      "The Lords' Second Book"),
    (88, 102, "apollo",            "Book of Apollo, Son of Jehovih"),
    (103,105, "lords-third",       "The Lord's Third Book"),
    (106,111, "thor",              "Book of Thor, Son of Jehovih"),
    (112,115, "lords-fourth",      "The Lord's Fourth Book"),
    (116,128, "osiris",            "Book of Osiris, Son of Jehovih"),
    (129,135, "lords-fifth",       "The Lord's Fifth Book"),
    (136,178, "fragapatti",        "Book of Fragapatti, Son of Jehovih"),
    (179,207, "gods-word",         "Book of God's Word"),
    (208,225, "divinity",          "Book of Divinity"),
    (226,238, "cpenta-armij",      "Book of Cpenta-Armij, Daughter of Jehovih"),
    (239,266, "gods-first",        "God's First Book"),
    (267,321, "wars",              "Book of Wars Against Jehovih"),
    (322,347, "lika",              "Book of Lika, Son of Jehovih"),
    (348,378, "arc-of-bon",        "Book of the Arc of Bon"),
    (379,389, "gods-ben",          "God's Book of Ben"),
    (390,412, "cosmology",         "Book of Cosmology and Prophecy"),
    (413,442, "saphah",            "Book of Saphah"),
    (443,483, "bons-praise",       "Bon's Book of Praise"),
    (484,543, "eskra",             "God's Book of Eskra"),
    (544,563, "es",                "Book of Es, Daughter of Jehova"),
    (564,601, "judgement",         "Book of Judgement"),
    (602,618, "inspiration",       "Book of Inspiration"),
    (619,644, "jehovih-kingdom",   "Book of Jehovih's Kingdom on Earth"),
    (645,658, "discipline",        "Book of Discipline"),
]


def file_no_to_book(n: int):
    for start, end, slug, _title in BOOK_RANGES:
        if start <= n <= end:
            return slug
    return None


def chapter_within_book(n: int) -> int:
    for start, end, _slug, _title in BOOK_RANGES:
        if start <= n <= end:
            return n - start + 1
    return 0

# ---------------------------------------------------------------------------
# Page-number pattern: lines like "p. 6", "p. 68a", "p. xv"
# ---------------------------------------------------------------------------
_PAGE_RE = re.compile(r"^p\.\s+\S+$", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^chapter\s+\d+", re.IGNORECASE)
_VERSE_RE = re.compile(r"^\d+\.\s")
_SACRED_TEXTS_FOOTER = re.compile(r"sacred.texts", re.IGNORECASE)


def extract_epigraph(path: Path) -> str:
    """Return the epigraph text from an ST chapter file (may be empty string)."""
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
    paragraphs = soup.find_all("p")

    # Collect text blocks between the first heading-like paragraph and verse 1.
    # The first paragraph is often a page marker or the book title/chapter heading.
    # We skip:
    #   - page-number lines ("p. N")
    #   - lines that look like book/chapter headings (all-caps short, or match CHAPTER N)
    # We stop at the first verse ("N. text...").
    # Everything in between is epigraph.

    epigraph_parts = []
    passed_start = False

    for p in paragraphs:
        text = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if not text:
            continue
        # Stop at first verse
        if _VERSE_RE.match(text):
            break
        # Skip page markers
        if _PAGE_RE.match(text):
            continue
        # Skip "Sacred Texts | Oahspe" footer
        if _SACRED_TEXTS_FOOTER.search(text):
            continue
        # Skip "CHAPTER N" lines
        if _CHAPTER_RE.match(text):
            continue
        # Mark that we've passed the first non-page non-verse block
        passed_start = True
        epigraph_parts.append(text)

    if not passed_start or not epigraph_parts:
        return ""

    return " ".join(epigraph_parts)


# ---------------------------------------------------------------------------
# Main merge logic
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
CACHE_DIR = Path(__file__).parent / ".htmlcache"
CONTENT_DIR = ROOT / "content" / "books"


def load_chapter_json(slug: str, chapter: int) -> tuple[Path | None, dict | None]:
    path = CONTENT_DIR / slug / f"chapter-{chapter:02d}.json"
    if not path.exists():
        return None, None
    return path, json.loads(path.read_text())


def save_chapter_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def ensure_preamble_shape(preamble) -> dict:
    """Normalise preamble to the i18n dict shape."""
    if isinstance(preamble, dict):
        return preamble
    # Legacy string form — wrap it
    return {"en": preamble or "", "zh_hant": None, "zh_hans": None, "ja": None}


def merge():
    # Counters
    total = 0
    word_1882 = 0
    sacred_texts_filled = 0
    still_empty = 0
    unmapped: list[str] = []
    skipped_absent: list[str] = []

    cache_files = sorted(CACHE_DIR.glob("oah*.htm"))

    for cache_file in cache_files:
        # Parse file number from filename (oahNN.htm)
        m = re.match(r"oah(\d+)\.htm$", cache_file.name)
        if not m:
            continue
        file_no = int(m.group(1))

        slug = file_no_to_book(file_no)
        if slug is None:
            unmapped.append(cache_file.name)
            continue

        chapter = chapter_within_book(file_no)
        if chapter == 0:
            unmapped.append(cache_file.name)
            continue

        path, data = load_chapter_json(slug, chapter)
        if data is None:
            skipped_absent.append(f"{slug}.{chapter}")
            continue

        total += 1

        preamble = ensure_preamble_shape(data.get("preamble", {}))
        existing_en = preamble.get("en", "")
        current_source = data.get("preamble_source")  # may not exist yet

        if current_source == "word-1882":
            # Already tagged from Word-HTML; idempotent path
            word_1882 += 1
            continue
        elif current_source == "sacred-texts":
            # Already filled from Sacred Texts; idempotent path
            sacred_texts_filled += 1
            continue
        elif existing_en and current_source is None:
            # Has Word-HTML preamble but not yet tagged — tag it
            new_source = "word-1882"
            new_en = existing_en
            word_1882 += 1
        else:
            # Empty preamble — try to extract from Sacred Texts
            epigraph = extract_epigraph(cache_file)
            if epigraph:
                new_source = "sacred-texts"
                new_en = epigraph
                sacred_texts_filled += 1
            else:
                new_source = None
                new_en = ""
                still_empty += 1

        # Idempotency check: only write if something changed
        changed = False
        if new_en != preamble.get("en", ""):
            preamble["en"] = new_en
            changed = True
        if current_source != new_source:
            changed = True

        if changed:
            # Preserve all translation fields; only en may have changed
            data["preamble"] = preamble
            data["preamble_source"] = new_source
            save_chapter_json(path, data)
        elif "preamble_source" not in data:
            # First run: tag is missing even if content unchanged
            data["preamble_source"] = new_source
            save_chapter_json(path, data)

    return {
        "total": total,
        "word_1882": word_1882,
        "sacred_texts_filled": sacred_texts_filled,
        "still_empty": still_empty,
        "unmapped": unmapped,
        "skipped_absent": skipped_absent,
    }


def verify(stats: dict) -> None:
    """Spot-check key invariants and print verification lines."""
    print("\n--- Verification ---")

    # 1. jehovih.1 translation preserved
    path, data = load_chapter_json("jehovih", 1)
    if data:
        zh = data.get("preamble", {}).get("zh_hant")
        src = data.get("preamble_source")
        ok = "✓" if zh else "✗ MISSING"
        print(f"  jehovih.1 preamble.zh_hant preserved: {ok}")
        print(f"  jehovih.1 preamble_source: {src!r}")
    else:
        print("  jehovih.1: FILE NOT FOUND")

    # 2. sethantes.1 epigraph filled
    path2, data2 = load_chapter_json("sethantes", 1)
    if data2:
        en = data2.get("preamble", {}).get("en", "")[:80]
        src2 = data2.get("preamble_source")
        print(f"  sethantes.1 preamble_source: {src2!r}")
        print(f"  sethantes.1 preamble.en[:80]: {en!r}")
    else:
        print("  sethantes.1: FILE NOT FOUND")

    # 3. aph.1 epigraph filled
    path3, data3 = load_chapter_json("aph", 1)
    if data3:
        en3 = data3.get("preamble", {}).get("en", "")[:80]
        src3 = data3.get("preamble_source")
        print(f"  aph.1 preamble_source: {src3!r}")
        print(f"  aph.1 preamble.en[:80]: {en3!r}")
    else:
        print("  aph.1: FILE NOT FOUND")


def main():
    print("=== Merging Sacred Texts epigraphs into JSON preambles ===\n")
    stats = merge()

    print("\n--- Summary ---")
    print(f"  Total chapters processed:   {stats['total']}")
    print(f"  word-1882 preambles kept:   {stats['word_1882']}")
    print(f"  sacred-texts filled:        {stats['sacred_texts_filled']}")
    print(f"  still empty:                {stats['still_empty']}")
    print(f"  ST files unmapped:          {len(stats['unmapped'])}")
    if stats["unmapped"]:
        print(f"    {', '.join(stats['unmapped'])}")
    if stats["skipped_absent"]:
        print(f"  JSON absent (skipped):      {len(stats['skipped_absent'])}")
        for s in stats["skipped_absent"][:10]:
            print(f"    {s}")

    verify(stats)
    print()


if __name__ == "__main__":
    main()
