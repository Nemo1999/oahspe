#!/usr/bin/env python3
"""
Parse the 1882 Oahspe Word-HTML export into per-chapter JSON files.

Usage: python3 scripts/html-to-json.py [--dry-run]

Produces content/books/<slug>/chapter-NN.json for all books found in the HTML.

Key rules:
- Book frontispiece images (between book-title anchor and chapter-1 anchor)
  attach to chapter 1 verse 1.
- Images in special gallery sections (godsbkbenpics, cosmogony_plates) attach
  to the correct book's last-chapter last-verse (godsbkbenpics → gods-ben ch10
  last verse; cosmogony_plates → cosmology ch1 v1 frontispiece).
- Inline images (between chapter N anchor and chapter N+1 anchor, after at
  least one verse) attach to the last verse seen.
- Translated books (jehovih + 5 front-matter) are never re-generated; only a
  targeted image-merge is done (inject missing images without touching text/translations).
- image002.jpg (cover) → targeted merge into oahspe-intro ch1 v1.
- image233.jpg (colophon) → jehovih-kingdom ch26 last verse, caption "End of Oahspe".
- Copies every referenced image into site/static/plates/edition1882/.
- Updates content/meta/books.json chapter_count to actual HTML counts.
- Idempotent and re-runnable.
"""

import json
import re
import shutil
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).parent.parent
HTML_SRC = ROOT / "sources" / "1882-word-html" / "OAHSPE-1882-Edition.html"
IMG_SRC_DIR = ROOT / "sources" / "1882-word-html"
IMG_DST_DIR = ROOT / "site" / "static" / "plates" / "edition1882"
BOOKS_DIR = ROOT / "content" / "books"
BOOKS_JSON = ROOT / "content" / "meta" / "books.json"

DRY_RUN = "--dry-run" in sys.argv

# ---------------------------------------------------------------------------
# Chapter-anchor prefix → slug
# Covers all schemes: prefix+N, bk<book>N, es_/judgement_ underscore, l4thb, LFthB
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

# Book-title anchors (bare, no trailing digit) → slug.
# Seeing one of these triggers: flush current chapter, reset state, begin
# watching for a frontispiece image before chapter 1.
BOOK_TITLE_TO_SLUG = {
    "bkjehovih":           "jehovih",
    "sethantes":           "sethantes",
    "firstbookfirstlords": "first-lords",
    "ahshong":             "ahshong",
    "secondbklords":       "second-lords",
    "synopsis":            "synopsis",
    "aph":                 "aph",
    "lordsfirstbk":        "lords-first",
    "sue":                 "sue",
    "lordssecondbk":       "lords-second",
    "apollo":              "apollo",
    "lordfthirdbk":        "lords-third",
    "thor":                "thor",
    "lordsforthbk":        "lords-fourth",
    "osiris":              "osiris",
    "lordsfifthbk":        "lords-fifth",
    "fragapatti":          "fragapatti",
    "bkgodsword":          "gods-word",
    "bkdivinity":          "divinity",
    "cpentarmig":          "cpenta-armij",
    "firstbkgod":          "gods-first",
    "bkwars":              "wars",
    "lika":                "lika",
    "arcofbon":            "arc-of-bon",
    "godsbkben":           "gods-ben",
    "cosmogony":           "cosmology",
    "eskra":               "eskra",
    "bkofes":              "es",
    "judgement":           "judgement",
    "inspiration":         "inspiration",
    "jkoe":                "jehovih-kingdom",
    # Section-based books — flush standard parser when encountered
    "saphah":              "saphah",
    "bonsbkpraise":        "bons-praise",
}

# Special gallery anchors: flush current book's chapter and attribute
# the following images to a specific target.
# Format: anchor_name → (slug, chap, "last_verse" | "frontispiece")
GALLERY_ANCHORS = {
    # God's Book of Ben plate appendix — images belong on gods-ben ch10 last verse
    "godsbkbenpics": ("gods-ben", 10, "last_verse"),
    # cosmogony_plates section — images belong on cosmology ch1 as frontispiece
    "cosmogony_plates": ("cosmology", 1, "frontispiece"),
}

# Section-based books: anchor-prefix → slug
SECTION_PREFIX_TO_SLUG = {
    "saphah_": "saphah",
    "bon_":    "bons-praise",
}

# Books with existing translations — SKIP regeneration (targeted image-merge only)
SKIP_SLUGS = {
    "jehovih",
    "general-statement", "prophets", "hints", "oahspe-intro", "voice-of-man",
}

# Books absent from the 1882 HTML entirely
ABSENT_BOOKS = {"discipline"}

# ---------------------------------------------------------------------------
# Image caption map: filename → human caption string (None = no caption)
# Built from plate_* anchor names preceding each <img>.
# ---------------------------------------------------------------------------
IMG_CAPTIONS: dict[str, str | None] = {
    "image002.jpg": "Oahspe — Title Page",
    "image004.jpg": "Jehovih Speaks",
    "image006.gif": None,
    "image008.jpg": "Semuan Firmament",
    "image010.jpg": "XSARJIS",
    "image012.jpg": "Hosts Descending",
    "image014.jpg": "Races",
    "image016.jpg": "Races",
    "image018.jpg": "Ethereans Visiting Earth",
    "image020.jpg": "C'evorkum",
    "image022.jpg": "C'evorkum",
    "image024.jpg": "C'evorkum",
    "image026.jpg": "Bridge of Chinvat",
    "image028.jpg": "Earth in Aji",
    "image030.jpg": "Aries",
    "image032.jpg": "Starworshippers",
    "image034.jpg": "Etherea",
    "image036.jpg": "Hoab",
    "image038.jpg": "Signature",
    "image040.jpg": "Ug Sa",
    "image042.jpg": "Divine Seal",
    "image044.jpg": "Ocgokuk",
    "image046.jpg": "Flatheads",
    "image048.jpg": "Gall",
    "image050.jpg": "Osiris",
    "image052.jpg": "Isis",
    "image054.jpg": "Tablet of Osiris",
    "image056.jpg": "Kaskak",
    "image058.jpg": "Earth in Arc of Bon",
    "image060.jpg": "Nine Entities",
    "image062.jpg": "Nine Entities",
    "image063.gif": "Nine Entities",
    "image065.jpg": "Nine Entities",
    "image066.gif": "Nine Entities",
    "image068.jpg": "Nine Entities",
    "image070.jpg": "Nine Entities",
    "image072.jpg": "Nine Entities",
    "image074.jpg": "Nine Entities",
    "image076.jpg": "Cyclic Coil",
    "image078.jpg": "Etherea Space",
    "image080.jpg": "Earth Atmosphere",
    "image082.jpg": "Serpent Planets",
    "image084.jpg": "Dissection of Serpent",
    "image086.jpg": "Towsang",
    "image088.gif": "Deviation of Serpent",
    "image090.jpg": "Serpent's Orbit",
    "image092.jpg": "Anoad",
    "image094.jpg": "Prophetic Numbers",
    "image096.jpg": "Shamael",
    "image098.jpg": "Earth in Semu",
    "image100.jpg": "Jiay",
    "image102.jpg": "Aji",
    "image104.jpg": "Hyarti Nebula",
    "image106.jpg": "Jiniquin Swamp",
    "image108.gif": "Primary Vortex",
    "image110.jpg": "Secondary Vortex",
    "image112.jpg": "Third Age of Vortex",
    "image114.jpg": "Fourth Age of Vortex",
    "image116.jpg": "Organic Wark",
    "image118.jpg": "Shattered Wark",
    "image120.jpg": "Photosphere",
    "image122.jpg": "Earth and Atmosphere",
    "image124.jpg": "Snowflakes",
    "image126.jpg": "Sun and Earth",
    "image128.jpg": "C'evorkum Roadway Solar Phalanx",
    "image130.jpg": "C'evorkum Roadway Solar Phalanx",
    "image132.jpg": "1st, 2nd, 3rd Resurrection",
    "image134.jpg": "Mathematical Problems",
    "image136.jpg": "Travels of Solar Phalanx",
    "image138.jpg": "Travels of Solar Phalanx",
    "image140.jpg": "Travels of Solar Phalanx",
    "image142.jpg": "Travels of Solar Phalanx",
    "image144.jpg": "Travels of Solar Phalanx",
    "image146.jpg": "Travels of Solar Phalanx",
    "image148.jpg": "Travels of Solar Phalanx",
    "image150.jpg": "Travels of Solar Phalanx",
    "image152.jpg": "Travels of Solar Phalanx",
    "image154.jpg": "Light Illustrated",
    "image156.jpg": "Lens Illustrated",
    "image158.jpg": "Planets",
    "image160.jpg": "Orachnebuahgalah",
    "image162.jpg": "Pan Map",
    "image164.jpg": "Earth Division Map",
    "image166.jpg": "Tree",
    "image168.jpg": "Tree",
    "image170.jpg": "Tree",
    "image172.jpg": "Onk",
    "image174.jpg": "Aries",
    "image176.jpg": "Tau",
    "image178.jpg": "Views of Etherean Worlds",
    "image180.jpg": "Starworshippers",
    "image181.jpg": "Bridge of Chinvat",
    "image183.jpg": "Bridge of Chinvat",
    "image185.jpg": "Kii Tablet",
    "image187.jpg": "Kii Tablet",
    "image189.jpg": "Tablet Zerl",
    "image191.jpg": "Tablet Zerl",
    "image192.jpg": "Divine Seal",
    "image194.jpg": "Divine Seal",
    "image196.jpg": "Tablet Fonece",
    "image198.jpg": "Ihin",
    "image200.jpg": "Tablet of Ancient Egypt",
    "image202.jpg": "Tablet of Hyyi",
    "image204.jpg": "Sun Degree",
    "image206.jpg": "Sun Degree",
    "image208.jpg": "Algonquin Tablet",
    "image210.jpg": "Anubis",
    "image212.jpg": "Mound Builders",
    "image214.jpg": "Baugh-Ghan-Ghad",
    "image216.jpg": "Skull Temple",
    "image218.jpg": "Skull Temple Sectional",
    "image220.jpg": "Emethachava",
    "image222.jpg": "Holy Mass",
    "image224.jpg": "Loiask",
    "image226.jpg": "Arc of Kosmon",
    "image228.jpg": "Grades",
    "image230.jpg": "Rates",
    "image232.jpg": "Judgement Symbol",
    "image233.jpg": "End of Oahspe",
}


def load_slug_title_map() -> dict[str, str]:
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


def match_chapter_prefix(name: str) -> tuple[str | None, int]:
    """Return (slug, chapter_num) or (None, 0) for a chapter anchor name."""
    m = re.match(r"^(.+?)(\d+)$", name)
    if not m:
        return None, 0
    prefix, num = m.group(1), int(m.group(2))
    slug = PREFIX_TO_SLUG.get(prefix)
    if slug:
        return slug, num
    return None, 0


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


def make_img_entry(src_attr: str) -> dict | None:
    """Build an image entry dict with caption. Returns None if file missing."""
    web_path = copy_image(src_attr)
    if not web_path:
        return None
    fname = Path(src_attr).name
    caption = IMG_CAPTIONS.get(fname)
    entry: dict = {"src": web_path, "edition": "1882"}
    if caption:
        entry["caption"] = caption
    return entry


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
# Targeted image merge (for translated/skip-listed books)
# ---------------------------------------------------------------------------

def targeted_image_merge(slug: str, chap: int, verse_num: int, new_images: list[dict]):
    """
    Inject new_images into an existing chapter JSON at the specified verse,
    without touching any text or translation fields.
    Skips if verse already has these images (idempotent).
    """
    path = BOOKS_DIR / slug / f"chapter-{chap:02d}.json"
    if not path.exists():
        print(f"  WARN: targeted merge skipped — {path} does not exist")
        return
    data = json.loads(path.read_text())
    changed = False
    for v in data["verses"]:
        if v["verse_number"] == verse_num:
            existing_srcs = {img["src"] for img in v.get("images", [])}
            to_add = [img for img in new_images if img["src"] not in existing_srcs]
            if to_add:
                v.setdefault("images", []).extend(to_add)
                changed = True
            break
    if changed and not DRY_RUN:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        print(f"  MERGE: {slug}.{chap}.{verse_num} ← {len(new_images)} image(s)")


# ---------------------------------------------------------------------------
# Main parse: standard chapter-anchored books
# ---------------------------------------------------------------------------

def parse_standard_chapters(soup: BeautifulSoup, slug_title: dict) -> dict[str, dict[int, dict]]:
    """
    Walk the HTML in document order, detect chapter anchors by prefix,
    extract verses and images, attach images correctly.

    Image placement rules:
    1. Images between book-title anchor and first verse of chapter 1
       → pending_images, attached to chapter 1 verse 1.
    2. Images after verse N and before verse N+1 (same chapter)
       → attached to verse N (last seen verse).
    3. Images after last verse of chapter N and before next chapter anchor
       → attached to last verse of chapter N, UNLESS we cross a book boundary
         (book-title anchor or gallery anchor) first — in that case, flush.
    4. Gallery anchors (godsbkbenpics, cosmogony_plates) flush current chapter
       and redirect subsequent images to a specific target.

    Returns: {slug: {chap_num: chapter_dict}}
    """
    results: dict[str, dict[int, dict]] = {}

    cur_slug: str | None = None
    cur_chap: int = 0
    cur_title: str = ""
    cur_preamble_parts: list[str] = []
    cur_verses: list[dict] = []
    in_preamble: bool = False
    pending_images: list[dict] = []  # awaiting first verse of current chapter

    # Gallery redirect state: when not None, images go to a specific slot
    # Format: (slug, chap, "last_verse" | "frontispiece", [accumulated_imgs])
    gallery_target: tuple | None = None

    def flush_chapter():
        nonlocal cur_slug, cur_chap, cur_preamble_parts, cur_verses
        nonlocal in_preamble, pending_images
        if cur_slug and cur_chap and cur_verses:
            # Any remaining pending_images attach to last verse
            if pending_images:
                cur_verses[-1].setdefault("images", []).extend(pending_images)
                pending_images = []
            preamble = collapse(" ".join(cur_preamble_parts))
            chap = make_chapter(cur_slug, cur_chap, cur_title, preamble, cur_verses)
            results.setdefault(cur_slug, {})[cur_chap] = chap
            # Only clear pending_images when a real chapter was flushed
            cur_preamble_parts = []
            cur_verses = []
            in_preamble = False
            pending_images = []
        else:
            # No real chapter to flush (cur_chap=0 or no verses).
            # Preserve pending_images so frontispiece images carry to ch1 v1.
            cur_preamble_parts = []
            cur_verses = []
            in_preamble = False
            # do NOT clear pending_images here

    def flush_gallery():
        """Commit accumulated gallery images to their target."""
        nonlocal gallery_target
        if gallery_target is None:
            return
        g_slug, g_chap, g_mode, g_imgs = gallery_target
        gallery_target = None
        if not g_imgs:
            return
        if g_mode == "last_verse":
            # Attach to last verse of g_chap in results
            chap_data = results.get(g_slug, {}).get(g_chap)
            if chap_data and chap_data["verses"]:
                chap_data["verses"][-1].setdefault("images", []).extend(g_imgs)
            else:
                print(f"  WARN: gallery last_verse target {g_slug}.{g_chap} has no verses")
        elif g_mode == "frontispiece":
            # Store for attachment to chapter 1 verse 1 when it's created
            # We store them as pending_images for the upcoming chapter
            pending_images.extend(g_imgs)

    all_tags = list(soup.body.descendants) if soup.body else []

    for tag in all_tags:
        if not isinstance(tag, Tag):
            continue

        if tag.name == "a" and tag.get("name"):
            aname = tag["name"]

            # --- Gallery anchor ---
            if aname in GALLERY_ANCHORS:
                flush_chapter()
                flush_gallery()
                g_slug, g_chap, g_mode = GALLERY_ANCHORS[aname]
                gallery_target = (g_slug, g_chap, g_mode, [])
                cur_slug = None
                cur_chap = 0
                continue

            # --- Book-title anchor ---
            if aname in BOOK_TITLE_TO_SLUG:
                flush_chapter()
                flush_gallery()
                new_slug = BOOK_TITLE_TO_SLUG[aname]
                # For section-based books (saphah, bons-praise), stop tracking
                if new_slug in ("saphah", "bons-praise"):
                    cur_slug = None
                    cur_chap = 0
                else:
                    # Prepare for this book's chapters; pending_images will collect frontispiece
                    cur_slug = new_slug
                    cur_chap = 0
                    in_preamble = False
                continue

            # --- Chapter anchor ---
            slug, chnum = match_chapter_prefix(aname)
            if slug:
                flush_gallery()
                flush_chapter()
                cur_slug = slug
                cur_chap = chnum
                book_title = slug_title.get(slug, slug)
                cur_title = f"{book_title} — Chapter {chnum}"
                in_preamble = True
                continue

            # --- Ignore all other anchors (plate_, aries, symbol, etc.) ---
            continue

        # --- Images ---
        if tag.name == "img":
            src = tag.get("src", "")
            if not src or "_files/image" not in src.lower():
                continue
            img_entry = make_img_entry(src)
            if not img_entry:
                continue

            # Gallery mode: accumulate for gallery target
            if gallery_target is not None:
                gallery_target[3].append(img_entry)
                continue

            # Normal mode: cur_chap=0 means we're after a book-title anchor but before ch1
            # (i.e. frontispiece zone). Still accumulate into pending_images.
            if cur_slug:
                if cur_verses:
                    # Attach to last verse
                    cur_verses[-1].setdefault("images", []).append(img_entry)
                else:
                    # Before first verse — frontispiece / book-title pending
                    pending_images.append(img_entry)
            # cur_slug=None: image before all content anchors (e.g. image002)
            # handled by targeted merge; drop here.
            continue

        # --- Paragraphs ---
        if tag.name == "p" and cur_slug and cur_chap:
            is_v, vnum, vtext = is_verse_para(tag)
            if is_v and vtext:
                verse = make_verse(cur_slug, cur_chap, vnum, vtext, list(pending_images))
                pending_images = []
                cur_verses.append(verse)
                in_preamble = False
            elif in_preamble:
                raw = collapse(tag.get_text())
                if raw and not re.match(r"^CHAPTER\s+\d+\.", raw, re.IGNORECASE):
                    cur_preamble_parts.append(raw)

    flush_gallery()
    flush_chapter()
    return results


# ---------------------------------------------------------------------------
# Section-based books (saphah_*, bon_*)
# ---------------------------------------------------------------------------

def parse_section_chapters(soup: BeautifulSoup, section_prefix: str, slug: str,
                            slug_title: dict) -> dict[int, dict]:
    """
    Parse section-based books where each named anchor is a 'chapter'.
    Handles inline images within each section correctly.
    Returns {chap_num: chapter_dict}.
    """
    results: dict[int, dict] = {}
    book_title = slug_title.get(slug, slug)

    # Anchors to skip when iterating within a section
    NON_CONTENT = {"plate_", "semoim_", "tablet_"}

    section_anchors = []
    for a in soup.find_all("a", attrs={"name": True}):
        name = a["name"]
        if name.startswith(section_prefix) and not any(name.startswith(p) for p in NON_CONTENT):
            section_anchors.append((name, a))

    if not section_anchors:
        return results

    sections_with_content = []
    carry_forward: list[dict] = []  # images from verse-less sections, forwarded to next section

    for idx, (aname, anchor_tag) in enumerate(section_anchors):
        preamble_parts: list[str] = []
        verses_raw: list[tuple[int, str, list]] = []
        # Initialise pending with any carried-forward images from previous verse-less sections
        pending_imgs: list[dict] = list(carry_forward)
        carry_forward = []
        in_preamble = True
        next_name = section_anchors[idx + 1][0] if idx + 1 < len(section_anchors) else None

        cur = anchor_tag
        while True:
            cur = cur.find_next(["a", "p", "img"])
            if cur is None:
                break
            if cur.name == "a" and cur.get("name"):
                cur_name = cur["name"]
                if cur_name == next_name:
                    break
                # For last section, stop at any non-section/non-plate anchor
                if next_name is None and not cur_name.startswith(section_prefix) and \
                        not any(cur_name.startswith(p) for p in NON_CONTENT):
                    break
            elif cur.name == "img":
                src = cur.get("src", "")
                if src and "_files/image" in src.lower():
                    entry = make_img_entry(src)
                    if entry:
                        pending_imgs.append(entry)
            elif cur.name == "p":
                is_v, vnum, vtext = is_verse_para(cur)
                if is_v and vtext:
                    verses_raw.append((vnum, vtext, list(pending_imgs)))
                    pending_imgs = []
                    in_preamble = False
                elif in_preamble:
                    raw = collapse(cur.get_text())
                    if raw:
                        preamble_parts.append(raw)

        if verses_raw:
            # Attach any trailing images (after the last verse) to the last verse
            if pending_imgs:
                last_vnum, last_vtext, last_imgs = verses_raw[-1]
                verses_raw[-1] = (last_vnum, last_vtext, last_imgs + pending_imgs)
            sections_with_content.append((preamble_parts, verses_raw))
        else:
            # No verses in this section: carry images forward to next section
            if pending_imgs:
                carry_forward.extend(pending_imgs)

    for chap_num, (preamble_parts, verses_raw) in enumerate(sections_with_content, 1):
        title = f"{book_title} — Chapter {chap_num}"
        verses = [make_verse(slug, chap_num, vnum, vtext, imgs)
                  for vnum, vtext, imgs in verses_raw]
        preamble = collapse(" ".join(preamble_parts))
        results[chap_num] = make_chapter(slug, chap_num, title, preamble, verses)

    return results


# ---------------------------------------------------------------------------
# Targeted merges for translated books
# ---------------------------------------------------------------------------

def do_targeted_merges():
    """
    Inject specific images into translated/skip-listed books without overwriting translations.
    Covers:
      - image002.jpg → oahspe-intro ch1 v1  (cover/title-page)
      - image004.jpg → jehovih ch1 v1        (book frontispiece)
      - image006.gif → jehovih ch1 v7        (inline symbol, already present in some runs)
    """
    # image002 → oahspe-intro.1.1
    img002 = make_img_entry("OAHSPE%20-%20The%201882%20Edition_files/image002.jpg")
    if not img002:
        # Try plain filename
        web = copy_image("image002.jpg")
        if web:
            img002 = {"src": web, "edition": "1882", "caption": "Oahspe — Title Page"}
    if img002:
        targeted_image_merge("oahspe-intro", 1, 1, [img002])

    # image004 → jehovih.1.1
    img004 = make_img_entry("OAHSPE%20-%20The%201882%20Edition_files/image004.jpg")
    if not img004:
        web = copy_image("image004.jpg")
        if web:
            img004 = {"src": web, "edition": "1882", "caption": "Jehovih Speaks"}
    if img004:
        targeted_image_merge("jehovih", 1, 1, [img004])

    # image006.gif → jehovih.1.7 (inline, no caption)
    img006 = make_img_entry("OAHSPE%20-%20The%201882%20Edition_files/image006.gif")
    if not img006:
        web = copy_image("image006.gif")
        if web:
            img006 = {"src": web, "edition": "1882"}
    if img006:
        targeted_image_merge("jehovih", 1, 7, [img006])


# ---------------------------------------------------------------------------
# books.json updater
# ---------------------------------------------------------------------------

def update_books_json(chapter_counts: dict[str, int]):
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Reading {HTML_SRC} …")
    raw = HTML_SRC.read_bytes().decode("windows-1252", errors="replace")
    print("Parsing HTML …")
    soup = BeautifulSoup(raw, "html.parser")

    slug_title = load_slug_title_map()

    # Phase 1: standard chapter-anchored books
    print("\nPhase 1: standard chapter anchors …")
    all_chapters: dict[str, dict[int, dict]] = parse_standard_chapters(soup, slug_title)
    for slug, chaps in sorted(all_chapters.items()):
        print(f"  {slug}: {len(chaps)} chapters")

    # Phase 2: section-based books
    print("\nPhase 2: section-based books (saphah, bons-praise) …")
    for sec_prefix, slug in SECTION_PREFIX_TO_SLUG.items():
        sec_results = parse_section_chapters(soup, sec_prefix, slug, slug_title)
        if sec_results:
            all_chapters[slug] = sec_results
            print(f"  {slug}: {len(sec_results)} sections → chapters")

    # Phase 3: write JSON (skip translated books)
    print("\nPhase 3: writing chapter JSON …")
    stats = {"books": 0, "chapters": 0, "verses": 0, "images": 0}
    chapter_counts: dict[str, int] = {}

    for slug in sorted(all_chapters):
        if slug in SKIP_SLUGS:
            print(f"  SKIP {slug} (translated)")
            continue
        if has_existing_translation(slug):
            print(f"  SKIP {slug} (zh_hant detected)")
            continue

        chap_map = all_chapters[slug]
        if not chap_map:
            continue

        stats["books"] += 1
        n_ch = 0
        for chap_num in sorted(chap_map):
            chap = chap_map[chap_num]
            vcount = len(chap["verses"])
            if vcount == 0:
                continue
            write_chapter(slug, chap_num, chap)
            stats["chapters"] += 1
            stats["verses"] += vcount
            for v in chap["verses"]:
                stats["images"] += len(v.get("images", []))
            n_ch += 1

        chapter_counts[slug] = n_ch

    # Phase 4: targeted merges for translated books
    print("\nPhase 4: targeted image merges for translated books …")
    do_targeted_merges()

    # Phase 5: update books.json
    print("\nPhase 5: updating books.json …")
    update_books_json(chapter_counts)

    # Report
    orig_counts = {b["slug"]: b.get("chapter_count", 0)
                   for b in json.loads(BOOKS_JSON.read_text())}
    print("\n=== REPORT ===")
    print(f"  Books written/updated : {stats['books']}")
    print(f"  Total chapters        : {stats['chapters']}")
    print(f"  Total verses          : {stats['verses']}")
    print(f"  Images placed inline  : {stats['images']}")
    img_dst_count = len(list(IMG_DST_DIR.glob("*"))) if IMG_DST_DIR.exists() else 0
    print(f"  Images copied to dst  : {img_dst_count}")

    print(f"\n  Absent from 1882 HTML:")
    for s in sorted(ABSENT_BOOKS):
        print(f"    - {s} ({slug_title.get(s, '?')})")

    print(f"\n  Section books (treated as sequential chapters):")
    for _, slug in SECTION_PREFIX_TO_SLUG.items():
        n = len(all_chapters.get(slug, {}))
        print(f"    - {slug}: {n} chapters")

    print(f"\n  Chapter count changes vs original books.json:")
    any_diff = False
    for slug, count in sorted(chapter_counts.items()):
        o = orig_counts.get(slug, 0)
        if o != count:
            print(f"    {slug}: {o} → {count}")
            any_diff = True
    if not any_diff:
        print("    (none — all counts matched)")

    # Verification checks
    print(f"\n  === VERIFICATIONS ===")

    # image004 on jehovih.1.1
    jch1 = BOOKS_DIR / "jehovih" / "chapter-01.json"
    if jch1.exists():
        d = json.loads(jch1.read_text())
        v1_imgs = d["verses"][0].get("images", [])
        found004 = any("image004" in img["src"] for img in v1_imgs)
        print(f"  image004 on jehovih.1.1: {'YES ✓' if found004 else 'NO ✗'}")
        print(f"    jehovih.1.1 zh_hant non-null: {'YES ✓' if d['verses'][0].get('zh_hant') else 'NO ✗'}")

    # image002 on oahspe-intro.1.1
    oi_ch1 = BOOKS_DIR / "oahspe-intro" / "chapter-01.json"
    if oi_ch1.exists():
        d = json.loads(oi_ch1.read_text())
        v1_imgs = d["verses"][0].get("images", [])
        found002 = any("image002" in img["src"] for img in v1_imgs)
        print(f"  image002 on oahspe-intro.1.1: {'YES ✓' if found002 else 'NO ✗'}")

    # No verse with >6 images (pileup check)
    max_imgs = 0
    max_verse_id = ""
    for slug in sorted(all_chapters):
        if slug in SKIP_SLUGS:
            continue
        for chap_num, chap in sorted(all_chapters.get(slug, {}).items()):
            for v in chap["verses"]:
                n = len(v.get("images", []))
                if n > max_imgs:
                    max_imgs = n
                    max_verse_id = v["id"]
    print(f"  Max images on any verse: {max_imgs} (at {max_verse_id})")
    if max_imgs <= 9:
        print(f"  Pileup check: OK ✓ (no verse has improbable pile)")
    else:
        print(f"  Pileup check: WARNING — {max_verse_id} has {max_imgs} images")

    # image233 on jehovih-kingdom ch26
    jk_dir = BOOKS_DIR / "jehovih-kingdom"
    if jk_dir.exists():
        ch26 = jk_dir / "chapter-26.json"
        if ch26.exists():
            d = json.loads(ch26.read_text())
            last_v = d["verses"][-1]
            found233 = any("image233" in img["src"] for img in last_v.get("images", []))
            print(f"  image233 on jehovih-kingdom.26 last verse: {'YES ✓' if found233 else 'NO ✗'}")

    if DRY_RUN:
        print("\n  (DRY RUN — no files written)")


if __name__ == "__main__":
    main()
