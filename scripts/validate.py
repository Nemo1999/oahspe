#!/usr/bin/env python3
"""Validate all Oahspe JSON files against expected schemas. Exit 1 on any error."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content"
BOOKS_JSON = CONTENT_DIR / "meta" / "books.json"
PLATES_JSON = CONTENT_DIR / "meta" / "plates.json"
GLOSSARY_JSON = CONTENT_DIR / "glossary" / "terms.json"
LEXICON_JSON = CONTENT_DIR / "style-lexicon.json"
BOOKS_DIR = CONTENT_DIR / "books"

errors: list[str] = []


def err(msg: str):
    errors.append(msg)
    print(f"  ERROR: {msg}")


def check_books() -> list[dict]:
    if not BOOKS_JSON.exists():
        err(f"Missing {BOOKS_JSON}")
        return []
    data = json.loads(BOOKS_JSON.read_text())
    if not isinstance(data, list):
        err("books.json: expected array")
        return []
    required = {"slug", "title", "chapter_count"}
    for i, b in enumerate(data):
        missing = required - b.keys()
        if missing:
            err(f"books.json[{i}]: missing fields {missing}")
        if not isinstance(b.get("chapter_count", 0), int):
            err(f"books.json[{i}]: chapter_count must be int")
    print(f"  books.json: {len(data)} books OK")
    return data


def check_plates() -> list[dict]:
    if not PLATES_JSON.exists():
        err(f"Missing {PLATES_JSON}")
        return []
    data = json.loads(PLATES_JSON.read_text())
    if not isinstance(data, list):
        err("plates.json: expected array")
        return []
    if len(data) != 97:
        err(f"plates.json: expected 97 entries, got {len(data)}")
    required = {"id", "title"}
    for i, p in enumerate(data):
        missing = required - p.keys()
        if missing:
            err(f"plates.json[{i}]: missing fields {missing}")
    print(f"  plates.json: {len(data)} plates OK")
    return data


def check_glossary() -> list[dict]:
    if not GLOSSARY_JSON.exists():
        err(f"Missing {GLOSSARY_JSON}")
        return []
    data = json.loads(GLOSSARY_JSON.read_text())
    if not isinstance(data, list):
        err("terms.json: expected array")
        return []
    required = {"term", "slug", "category", "translit", "source_def",
                "source_def_literal", "editor_note", "appears_in", "cross_refs",
                "locked", "first_seen"}
    slugs = set()
    for i, t in enumerate(data):
        missing = required - t.keys()
        if missing:
            err(f"terms.json[{i}]: missing fields {missing}")
        if t.get("category") not in ("name", "term"):
            err(f"terms.json[{i}] ({t.get('term')!r}): bad category {t.get('category')!r}")
        s = t.get("slug")
        if s in slugs:
            err(f"terms.json: duplicate slug {s!r}")
        slugs.add(s)
    print(f"  terms.json: {len(data)} glossary terms OK")
    return data


def check_lexicon() -> list[dict]:
    """style-lexicon.json is internal (verbs/phrases). Optional until first translation."""
    if not LEXICON_JSON.exists():
        print("  style-lexicon.json: not present yet (OK — populated during translation)")
        return []
    data = json.loads(LEXICON_JSON.read_text())
    if not isinstance(data, list):
        err("style-lexicon.json: expected array")
        return []
    required = {"en", "category", "zh_hant", "zh_hans", "ja"}
    for i, e in enumerate(data):
        missing = required - e.keys()
        if missing:
            err(f"style-lexicon.json[{i}]: missing fields {missing}")
        if e.get("category") not in ("verb", "phrase"):
            err(f"style-lexicon.json[{i}] ({e.get('en')!r}): bad category {e.get('category')!r}")
    print(f"  style-lexicon.json: {len(data)} entries OK")
    return data


VERSE_ID_RE = re.compile(r"^[a-z0-9-]+\.\d+\.\d+$")
CHAPTER_ID_RE = re.compile(r"^[a-z0-9-]+\.\d+$")


def check_chapter(path: Path) -> tuple[int, int]:
    """Returns (verse_count, error_count_added)."""
    before = len(errors)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        err(f"{path}: invalid JSON: {e}")
        return 0, len(errors) - before

    required_chapter = {"id", "book", "chapter", "title", "preamble", "verses"}
    missing = required_chapter - data.keys()
    if missing:
        err(f"{path}: missing chapter fields {missing}")

    cid = data.get("id", "")
    if not CHAPTER_ID_RE.match(cid):
        err(f"{path}: invalid chapter id {cid!r}")

    verses = data.get("verses", [])
    if not isinstance(verses, list):
        err(f"{path}: verses must be array")
        return 0, len(errors) - before

    # Preamble must be an i18n object with all four language keys — new schema.
    I18N_KEYS = {"en", "zh_hant", "zh_hans", "ja"}
    pre = data.get("preamble")
    if pre is not None:
        if not isinstance(pre, dict):
            err(f"{path}: preamble must be an i18n object, got {type(pre).__name__}")
        elif not I18N_KEYS.issubset(pre.keys()):
            err(f"{path}: preamble missing i18n keys {I18N_KEYS - pre.keys()}")
    # Provenance tag must be present and in the allowed enum.
    ps = data.get("preamble_source", "__missing__")
    if ps == "__missing__":
        err(f"{path}: missing preamble_source")
    elif ps not in ("word-1882", "sacred-texts", None):
        err(f"{path}: bad preamble_source {ps!r}")

    PLATES_DIR = ROOT / "site" / "static" / "plates" / "edition1882"
    for v in verses:
        vid = v.get("id", "")
        if not VERSE_ID_RE.match(vid):
            err(f"{path}: invalid verse id {vid!r}")
        if v.get("en") is None or v.get("en") == "":
            err(f"{path}: verse {vid} has null/empty 'en' field")
        # Image entries: caption must be i18n object (or absent); src file must exist.
        for im in (v.get("images") or []):
            cap = im.get("caption")
            if cap is not None and not isinstance(cap, dict):
                err(f"{path}: verse {vid} image caption must be i18n object")
            src = im.get("src", "")
            fname = src.split("/")[-1]
            if fname and not (PLATES_DIR / fname).exists():
                err(f"{path}: verse {vid} image {fname} missing from static/plates/edition1882")

    return len(verses), len(errors) - before


def main():
    print("\n=== Validating Oahspe JSON corpus ===\n")

    books = check_books()
    plates = check_plates()
    glossary = check_glossary()
    lexicon = check_lexicon()

    total_chapters = 0
    total_verses = 0

    if BOOKS_DIR.exists():
        chapter_files = sorted(BOOKS_DIR.rglob("chapter-*.json"))
        print(f"\n  Checking {len(chapter_files)} chapter files …")
        for path in chapter_files:
            verses, _ = check_chapter(path)
            total_chapters += 1
            total_verses += verses
    else:
        print(f"  WARNING: {BOOKS_DIR} does not exist; no chapters to validate")

    # Translation-coverage health report (non-failing) — tracks progress per language.
    tw = cn = ja = pre_en = pre_tr = 0
    if BOOKS_DIR.exists():
        for path in BOOKS_DIR.rglob("chapter-*.json"):
            d = json.loads(path.read_text())
            for v in d.get("verses", []):
                if v.get("zh_hant"): tw += 1
                if v.get("zh_hans"): cn += 1
                if v.get("ja"): ja += 1
            p = d.get("preamble") or {}
            if isinstance(p, dict) and (p.get("en") or "").strip():
                pre_en += 1
                if p.get("zh_hant"): pre_tr += 1

    def pct(n): return f"{n}/{total_verses} ({100*n//total_verses if total_verses else 0}%)"
    print("\n=== Summary ===")
    print(f"  Books:          {len(books)}")
    print(f"  Chapters:       {total_chapters}")
    print(f"  Verses:         {total_verses}")
    print(f"  Glossary terms: {len(glossary)}")
    print(f"  Plates:         {len(plates)}")
    print(f"  Style lexicon:  {len(lexicon)}")
    print("\n=== Translation coverage ===")
    print(f"  zh_hant verses: {pct(tw)}")
    print(f"  zh_hans verses: {pct(cn)}")
    print(f"  ja verses:      {pct(ja)}")
    print(f"  preambles:      {pre_en} chapters ({pre_tr} translated)")

    if errors:
        print(f"\n  {len(errors)} validation error(s) found.\n")
        sys.exit(1)
    else:
        print("\n  All files valid.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
