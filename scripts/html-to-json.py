#!/usr/bin/env python3
"""
Parse the 1882 Oahspe Word-HTML export into per-chapter JSON files.

Usage: python3 scripts/html-to-json.py [--dry-run]

Produces content/books/<slug>/chapter-NN.json for all books found in the HTML.
Skips any book/chapter whose existing JSON already has non-null zh_hant (preserves translations).
Updates content/meta/books.json chapter_count to match actual HTML counts.
Copies referenced images into site/static/plates/edition1882/.
"""

import json
import re
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).parent.parent
HTML_SRC = ROOT / "sources" / "1882-word-html" / "OAHSPE-1882-Edition.html"
IMG_SRC_DIR = ROOT / "sources" / "1882-word-html"
IMG_DST_DIR = ROOT / "site" / "static" / "plates" / "edition1882"
BOOKS_DIR = ROOT / "content" / "books"
BOOKS_JSON = ROOT / "content" / "meta" / "books.json"

DRY_RUN = "--dry-run" in sys.argv

# ---------------------------------------------------------------------------
# Prefix → slug map (verified against HTML heading text)
# ---------------------------------------------------------------------------
PREFIX_TO_SLUG = {
    "bj":          "jehovih",
    "seth":        "sethantes",
    "fbfl":        "first-lords",
    "ahshong":     "ahshong",
    "sbl":         "second-lords",
    "synopsis":    "synopsis",
    "aph":         "aph",
    "lfb":         "lords-first",
    "sue":         "sue",
    "lsb":         "lords-second",
    "apollo":      "apollo",
    "ltb":         "lords-third",
    "thor":        "thor",
    "l4thb":       "lords-fourth",
    "osiris":      "osiris",
    "LFthB":       "lords-fifth",
    "fragapatti":  "fragapatti",
    "BGW":         "gods-word",
    "bkdivinity":  "divinity",
    "cpentarmig":  "cpenta-armij",
    "firstbkgod":  "gods-first",
    "bkwars":      "wars",
    "lika":        "lika",
    "arcofbon":    "arc-of-bon",
    "godsbkben":   "gods-ben",
    "cosmogony":   "cosmology",
    "eskra":       "eskra",
    "es_":         "es",
    "judgement_":  "judgement",
    "inspiration": "inspiration",
    "shalem":      "jehovih-kingdom",
}

# Section-based books: anchor-prefix → slug (no numbered chapters in HTML)
SECTION_PREFIX_TO_SLUG = {
    "saphah_": "saphah",
    "bon_":    "bons-praise",
}

# Books that already have translations — skip entirely
SKIP_SLUGS = {
    "jehovih",
    "general-statement", "prophets", "hints", "oahspe-intro", "voice-of-man",
}

# Books absent from the 1882 HTML
ABSENT_BOOKS = {"discipline"}


def load_slug_title_map():
    data = json.loads(BOOKS_JSON.read_text())
    return {b["slug"]: b["title"] for b in data}


def has_existing_translation(slug: str) -> bool:
    """Return True if any chapter file for this slug has non-null zh_hant."""
    d = BOOKS_DIR / slug
    if not d.exists():
        return False
    for f in d.glob("chapter-*.json"):
        try:
            data = json.loads(f.read_text())
            if any(v.get("zh_hant") is not None for v in data.get("verses", [])):
                return True
        except Exception:
            pass
    return False


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_verse_para(p: Tag) -> tuple[bool, int, str]:
    """Check if <p> is a numbered verse. Returns (is_verse, verse_num, text)."""
    text = collapse(p.get_text())
    m = re.match(r"^(\d+)\.\s+(.*)", text, re.DOTALL)
    if m:
        return True, int(m.group(1)), collapse(m.group(2))
    return False, 0, ""


def is_chapter_anchor(tag: Tag) -> tuple[bool, str, int]:
    """Check if <a name=...> is a chapter anchor. Returns (is_chapter, prefix, chapter_num)."""
    name = tag.get("name", "")
    if not name:
        return False, "", 0
    m = re.match(r"^(.+?)(\d+)$", name)
    if not m:
        return False, "", 0
    return True, m.group(1), int(m.group(2))


def img_web_path(src: str) -> str:
    """Convert HTML img src to web path for JSON."""
    fname = Path(src).name
    return f"/plates/edition1882/{fname}"


def copy_image(src_attr: str) -> str | None:
    """Copy image from source dir to static dir. Return web path or None if missing."""
    fname = Path(src_attr).name
    src_path = IMG_SRC_DIR / fname
    if not src_path.exists():
        return None
    dst_path = IMG_DST_DIR / fname
    if not DRY_RUN:
        IMG_DST_DIR.mkdir(parents=True, exist_ok=True)
        if not dst_path.exists():
            shutil.copy2(src_path, dst_path)
    return f"/plates/edition1882/{fname}"


def make_verse(slug: str, chap: int, vnum: int, en: str, images: list) -> dict:
    v: dict = {
        "id": f"{slug}.{chap}.{vnum}",
        "verse_number": vnum,
        "en": en,
        "zh_hant": None,
        "zh_hans": None,
        "ja": None,
        "glossary_terms": [],
        "plate_ref": None,
        "notes": [],
    }
    if images:
        v["images"] = images
    return v


def make_chapter(slug: str, chap: int, title: str, preamble: str, verses: list) -> dict:
    return {
        "id": f"{slug}.{chap}",
        "book": slug,
        "chapter": chap,
        "title": title,
        "preamble": preamble,
        "verses": verses,
    }


def write_chapter(slug: str, chap: int, data: dict):
    d = BOOKS_DIR / slug
    if not DRY_RUN:
        d.mkdir(parents=True, exist_ok=True)
    path = d / f"chapter-{chap:02d}.json"
    if not DRY_RUN:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return path


# ---------------------------------------------------------------------------
# Main parse
# ---------------------------------------------------------------------------

def parse_standard_chapters(soup: BeautifulSoup, slug_title: dict):
    """
    Walk the HTML, detect chapter anchors by prefix, extract verses.
    Returns: {slug: {chap_num: chapter_dict}}
    """
    results: dict[str, dict[int, dict]] = {}

    # State
    cur_slug: str | None = None
    cur_chap: int = 0
    cur_title: str = ""
    cur_preamble_parts: list[str] = []
    cur_verses: list[dict] = []
    in_preamble: bool = False
    last_verse_num: int = 0
    pending_images: list[dict] = []  # images waiting to attach to next verse

    def flush_chapter():
        nonlocal cur_slug, cur_chap, cur_preamble_parts, cur_verses, in_preamble
        nonlocal last_verse_num, pending_images
        if cur_slug and cur_chap and cur_verses:
            # Attach any trailing images to last verse
            if pending_images and cur_verses:
                cur_verses[-1].setdefault("images", []).extend(pending_images)
                pending_images = []
            preamble = collapse(" ".join(cur_preamble_parts))
            chap = make_chapter(cur_slug, cur_chap, cur_title, preamble, cur_verses)
            results.setdefault(cur_slug, {})[cur_chap] = chap
        cur_preamble_parts = []
        cur_verses = []
        in_preamble = False
        last_verse_num = 0
        pending_images = []

    # Build a case-insensitive prefix lookup
    # Anchors are case-sensitive in the HTML; prefix map keys are exact
    prefix_map = {p: s for p, s in PREFIX_TO_SLUG.items()}

    def match_prefix(name: str) -> tuple[str | None, int]:
        """Return (slug, chapter_num) or (None, 0)."""
        m = re.match(r"^(.+?)(\d+)$", name)
        if not m:
            return None, 0
        prefix, num = m.group(1), int(m.group(2))
        slug = prefix_map.get(prefix)
        if slug:
            return slug, num
        return None, 0

    all_tags = list(soup.body.descendants) if soup.body else []

    for tag in all_tags:
        if not isinstance(tag, Tag):
            continue

        # --- Check for chapter anchor ---
        if tag.name == "a" and tag.get("name"):
            aname = tag["name"]
            slug, chnum = match_prefix(aname)
            if slug:
                # New chapter starts
                flush_chapter()
                cur_slug = slug
                cur_chap = chnum
                book_title = slug_title.get(slug, slug)
                cur_title = f"{book_title} — Chapter {chnum}"
                in_preamble = True
                continue

        # --- Images ---
        if tag.name == "img":
            src = tag.get("src", "")
            if src and "_files/image" in src.lower():
                web_path = copy_image(src)
                if web_path:
                    img_entry = {"src": web_path, "edition": "1882"}
                    if cur_verses:
                        # Attach to last verse
                        last_v = cur_verses[-1]
                        last_v.setdefault("images", []).append(img_entry)
                    else:
                        # Before first verse — queue for next verse
                        pending_images.append(img_entry)
            continue

        # --- Paragraphs ---
        if tag.name == "p" and cur_slug:
            is_v, vnum, vtext = is_verse_para(tag)
            if is_v and vtext:
                # Attach pending pre-verse images to this verse
                verse = make_verse(cur_slug, cur_chap, vnum, vtext, list(pending_images))
                pending_images = []
                cur_verses.append(verse)
                last_verse_num = vnum
                in_preamble = False
            elif in_preamble:
                # Accumulate preamble text (skip "CHAPTER N." heading text)
                raw = collapse(tag.get_text())
                if raw and not re.match(r"^CHAPTER\s+\d+\.", raw, re.IGNORECASE):
                    cur_preamble_parts.append(raw)

    flush_chapter()
    return results


def parse_section_chapters(soup: BeautifulSoup, section_prefix: str, slug: str, slug_title: dict):
    """
    Parse section-based books (saphah_*, bon_*) where each named anchor
    is a 'chapter'. Returns {chap_num: chapter_dict}.
    """
    results: dict[int, dict] = {}
    book_title = slug_title.get(slug, slug)

    # Collect all section anchors in document order
    section_anchors = []
    for tag in soup.find_all("a", attrs={"name": True}):
        name = tag["name"]
        if name.startswith(section_prefix) and not any(
            name.startswith(p) for p in ["plate_", "semoim_", "tablet_"]
        ):
            section_anchors.append((name, tag))

    if not section_anchors:
        return results

    # Collect content for each section; only keep non-empty ones; number sequentially
    sections_with_content = []
    for idx, (aname, anchor_tag) in enumerate(section_anchors):
        preamble_parts: list[str] = []
        verses_raw: list[tuple[int, str]] = []  # (vnum, text)
        pending_imgs: list[dict] = []
        in_preamble = True

        next_anchor_name = section_anchors[idx + 1][0] if idx + 1 < len(section_anchors) else None

        cur = anchor_tag
        while True:
            cur = cur.find_next(["a", "p", "img"])
            if cur is None:
                break
            if cur.name == "a" and cur.get("name"):
                aname_cur = cur["name"]
                if aname_cur == next_anchor_name:
                    break
                # For the last section (no next anchor), stop at any foreign anchor
                if next_anchor_name is None:
                    NON_CONTENT = ["plate_", "semoim_", "tablet_"]
                    if not aname_cur.startswith(section_prefix) and not any(
                        aname_cur.startswith(p) for p in NON_CONTENT
                    ):
                        break
            if cur.name == "img":
                src = cur.get("src", "")
                if src and "_files/image" in src.lower():
                    web_path = copy_image(src)
                    if web_path:
                        pending_imgs.append({"src": web_path, "edition": "1882", "_pending": True})
            elif cur.name == "p":
                is_v, vnum, vtext = is_verse_para(cur)
                if is_v and vtext:
                    verses_raw.append((vnum, vtext, list(pending_imgs)))
                    pending_imgs = []
                    in_preamble = False
                elif in_preamble:
                    raw_t = collapse(cur.get_text())
                    if raw_t:
                        preamble_parts.append(raw_t)

        if verses_raw:
            sections_with_content.append((preamble_parts, verses_raw))

    # Now assign sequential chapter numbers 1..N to non-empty sections only
    for chap_num, (preamble_parts, verses_raw) in enumerate(sections_with_content, 1):
        title = f"{book_title} — Chapter {chap_num}"
        verses = []
        for vnum, vtext, imgs in verses_raw:
            # Strip internal _pending marker
            clean_imgs = [{"src": i["src"], "edition": i["edition"]} for i in imgs]
            verse = make_verse(slug, chap_num, vnum, vtext, clean_imgs)
            verses.append(verse)
        preamble = collapse(" ".join(preamble_parts))
        results[chap_num] = make_chapter(slug, chap_num, title, preamble, verses)
    return results



def update_books_json(chapter_counts: dict[str, int]):
    """Update chapter_count in books.json to match actual parsed counts."""
    data = json.loads(BOOKS_JSON.read_text())
    changed = False
    for book in data:
        slug = book["slug"]
        if slug in chapter_counts:
            new_count = chapter_counts[slug]
            if book.get("chapter_count") != new_count:
                print(f"  books.json: {slug} chapter_count {book.get('chapter_count')} → {new_count}")
                book["chapter_count"] = new_count
                changed = True
    if changed and not DRY_RUN:
        BOOKS_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    print(f"Reading {HTML_SRC} …")
    raw = HTML_SRC.read_bytes().decode("windows-1252", errors="replace")
    print("Parsing HTML …")
    soup = BeautifulSoup(raw, "html.parser")

    slug_title = load_slug_title_map()

    # ------------------------------------------------------------------
    # Phase 1: parse standard chapter-anchored books
    # ------------------------------------------------------------------
    print("\nPhase 1: standard chapter anchors …")
    all_chapters: dict[str, dict[int, dict]] = parse_standard_chapters(soup, slug_title)

    # ------------------------------------------------------------------
    # Phase 2: parse section-based books
    # ------------------------------------------------------------------
    print("Phase 2: section-based books (saphah, bons-praise) …")
    for sec_prefix, slug in SECTION_PREFIX_TO_SLUG.items():
        sec_results = parse_section_chapters(soup, sec_prefix, slug, slug_title)
        if sec_results:
            all_chapters[slug] = sec_results
            print(f"  {slug}: {len(sec_results)} sections parsed as chapters")

    # ------------------------------------------------------------------
    # Phase 3: write JSON, skipping translated books
    # ------------------------------------------------------------------
    print("\nPhase 3: writing chapter JSON …")
    stats = {"books": 0, "chapters": 0, "verses": 0}
    chapter_counts: dict[str, int] = {}

    for slug in sorted(all_chapters):
        if slug in SKIP_SLUGS:
            print(f"  SKIP {slug} (has translations)")
            continue
        if has_existing_translation(slug):
            print(f"  SKIP {slug} (existing zh_hant detected)")
            continue

        chap_map = all_chapters[slug]
        if not chap_map:
            continue

        stats["books"] += 1
        n_chapters = 0
        for chap_num in sorted(chap_map):
            chap = chap_map[chap_num]
            vcount = len(chap["verses"])
            if vcount == 0:
                continue
            write_chapter(slug, chap_num, chap)
            stats["chapters"] += 1
            stats["verses"] += vcount
            n_chapters += 1

        chapter_counts[slug] = n_chapters
        print(f"  {slug}: {n_chapters} chapters, "
              f"{sum(len(chap_map[c]['verses']) for c in chap_map if c in sorted(chap_map)[:n_chapters])} verses")

    # ------------------------------------------------------------------
    # Phase 4: count images placed
    # ------------------------------------------------------------------
    images_placed = len(list(IMG_DST_DIR.glob("*"))) if IMG_DST_DIR.exists() else 0

    # ------------------------------------------------------------------
    # Phase 5: update books.json chapter counts
    # ------------------------------------------------------------------
    print("\nPhase 5: updating books.json chapter_count …")
    update_books_json(chapter_counts)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    print("\n=== REPORT ===")
    print(f"  Books created/updated : {stats['books']}")
    print(f"  Total chapters        : {stats['chapters']}")
    print(f"  Total verses          : {stats['verses']}")
    print(f"  Images placed         : {images_placed}")
    print(f"\n  Absent from 1882 HTML (no chapter anchors found):")
    for slug in sorted(ABSENT_BOOKS):
        print(f"    - {slug} ({slug_title.get(slug, '?')}) — not present in this edition")
    print(f"\n  Section-based (no numbered chapter anchors, treated as sequential chapters):")
    for _, slug in SECTION_PREFIX_TO_SLUG.items():
        n = len(all_chapters.get(slug, {}))
        print(f"    - {slug}: {n} sections → {n} chapters")
    print(f"\n  Chapter count differences vs original books.json:")
    orig = {b["slug"]: b.get("chapter_count", 0)
            for b in json.loads(BOOKS_JSON.read_text())}
    for slug, count in sorted(chapter_counts.items()):
        o = orig.get(slug, 0)
        if o != count:
            print(f"    {slug}: was {o}, now {count}")
    if DRY_RUN:
        print("\n  (DRY RUN — no files written)")


if __name__ == "__main__":
    main()
