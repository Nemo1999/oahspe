#!/usr/bin/env python3
"""Build and link a glossary from Oahspe chapter content."""

import argparse
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

ROOT = Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content" / "books"
GLOSSARY_JSON = ROOT / "content" / "glossary" / "terms.json"
GLOSSARY_URL = "https://archive.sacred-texts.com/oah/oah/oah03.htm"

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "oahspe-scraper/1.0 (+https://github.com/Nemo1999/oahspe)"


def slugify(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def load_all_chapters() -> list[tuple[Path, dict]]:
    chapters = []
    for d in sorted(CONTENT_DIR.iterdir()):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("chapter-*.json")):
            chapters.append((p, json.loads(p.read_text())))
    return chapters


def extract_glossary() -> list[dict]:
    """Fetch and parse the Sacred Texts glossary page."""
    resp = SESSION.get(GLOSSARY_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    body = soup.find("body") or soup

    terms = []
    seen = set()

    # The glossary is typically formatted as <b>Term</b> — definition.
    # Try several heuristics.

    # Strategy 1: bold terms followed by definition text in same paragraph
    for tag in body.find_all(["p", "dt"]):
        text = tag.get_text(" ", strip=True)
        bold = tag.find("b")
        if bold:
            term_text = bold.get_text(strip=True).rstrip(".,:;")
            rest = text[len(term_text):].lstrip(" .—-–:").strip()
            if term_text and len(term_text) < 80 and rest:
                slug = slugify(term_text)
                if slug not in seen:
                    seen.add(slug)
                    terms.append({
                        "term": term_text,
                        "slug": slug,
                        "en": rest,
                        "zh_hant": None,
                        "zh_hans": None,
                        "ja": None,
                        "appears_in": [],
                        "cross_refs": [],
                        "notes": [],
                    })

    # Strategy 2: definition list <dt>/<dd> pattern
    for dt in body.find_all("dt"):
        term_text = dt.get_text(strip=True).rstrip(".,:;")
        dd = dt.find_next_sibling("dd")
        definition = dd.get_text(" ", strip=True) if dd else ""
        if term_text and len(term_text) < 80:
            slug = slugify(term_text)
            if slug not in seen:
                seen.add(slug)
                terms.append({
                    "term": term_text,
                    "slug": slug,
                    "en": definition,
                    "zh_hant": None,
                    "zh_hans": None,
                    "ja": None,
                    "appears_in": [],
                    "cross_refs": [],
                    "notes": [],
                })

    if not terms:
        print("WARNING: No glossary terms extracted from Sacred Texts. "
              "The page format may have changed. Returning empty list.")

    return terms


def mode_extract():
    print("Extracting glossary from Sacred Texts …")
    terms = extract_glossary()
    GLOSSARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    GLOSSARY_JSON.write_text(json.dumps(terms, indent=2, ensure_ascii=False))
    print(f"Wrote {len(terms)} terms to {GLOSSARY_JSON}")


def mode_link():
    if not GLOSSARY_JSON.exists():
        print(f"ERROR: {GLOSSARY_JSON} not found. Run --extract first.")
        sys.exit(1)

    terms = json.loads(GLOSSARY_JSON.read_text())
    if not terms:
        print("No terms to link.")
        return

    # Build case-insensitive whole-word regexes
    patterns = []
    for t in terms:
        pat = re.compile(r"\b" + re.escape(t["term"]) + r"\b", re.IGNORECASE)
        patterns.append((t["slug"], pat))

    # Reset appears_in before relinking (idempotent)
    slug_to_term = {t["slug"]: t for t in terms}
    for t in terms:
        t["appears_in"] = []

    chapters = load_all_chapters()
    for path, chapter in tqdm(chapters, desc="Linking", unit="ch"):
        changed = False
        for verse in chapter["verses"]:
            en = verse.get("en") or ""
            matched_slugs = []
            for slug, pat in patterns:
                if pat.search(en):
                    matched_slugs.append(slug)
                    vid = verse["id"]
                    if vid not in slug_to_term[slug]["appears_in"]:
                        slug_to_term[slug]["appears_in"].append(vid)

            if set(matched_slugs) != set(verse.get("glossary_terms", [])):
                verse["glossary_terms"] = matched_slugs
                changed = True

        if changed:
            path.write_text(json.dumps(chapter, indent=2, ensure_ascii=False))

    GLOSSARY_JSON.write_text(json.dumps(terms, indent=2, ensure_ascii=False))
    total_links = sum(len(t["appears_in"]) for t in terms)
    print(f"Linked {total_links} verse references across {len(terms)} terms.")


def main():
    parser = argparse.ArgumentParser(description="Build or link the Oahspe glossary")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--extract", action="store_true", help="Scrape glossary from Sacred Texts")
    group.add_argument("--link", action="store_true", help="Cross-reference terms with verses")
    args = parser.parse_args()

    if args.extract:
        mode_extract()
    else:
        mode_link()


if __name__ == "__main__":
    main()
