#!/usr/bin/env python3
"""Generate Docusaurus MDX pages from chapter JSON files."""

import json
import sys
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content" / "books"
BOOKS_JSON = ROOT / "content" / "meta" / "books.json"
DOCS_DIR = ROOT / "site" / "docs"

# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

GLOSSARY_JSON = ROOT / "content" / "glossary" / "terms.json"


def load_glossary() -> dict:
    """Return {term: {translit, slug}} for parenthetical injection. Empty if none yet."""
    if not GLOSSARY_JSON.exists():
        return {}
    out = {}
    for t in json.loads(GLOSSARY_JSON.read_text()):
        out[t["term"]] = {"translit": t.get("translit", {}), "slug": t.get("slug", "")}
    return out


def chapter_mdx(chapter: dict, glossary: dict) -> str:
    cid = chapter["id"]
    title = chapter["title"]
    sidebar_label = f"Chapter {chapter['chapter']}"

    # Only ship glossary entries whose term actually appears in this chapter.
    used = set()
    for v in chapter["verses"]:
        used.update(v.get("glossary_terms") or [])
    chapter_gloss = {k: glossary[k] for k in used if k in glossary}

    return f"""---
id: {cid}
title: "{title}"
sidebar_label: "{sidebar_label}"
custom_edit_url: null
---

import VerseReader from '@site/src/components/VerseReader';

<VerseReader chapter={{{JS_PROP(chapter)}}} glossary={{{JS_PROP(chapter_gloss)}}} />
"""

def JS_PROP(obj) -> str:
    """Emit obj as a JSX backtick-template-literal JSON.parse() expression."""
    # Correct escape order: backslashes first, then backticks, then bare ${ that would
    # start a JS template expression.
    s = json.dumps(obj, ensure_ascii=False)
    s = s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    return "JSON.parse(`" + s + "`)"


def book_index_mdx(book_slug: str, book_title: str, chapter_files: list[Path]) -> str:
    chapters = [json.loads(p.read_text()) for p in chapter_files]
    chapter_links = "\n".join(
        f"- [Chapter {c['chapter']}](/{book_slug}/{c['id']})" for c in chapters
    )
    return f"""---
id: {book_slug}
title: "{book_title}"
sidebar_label: "{book_title}"
custom_edit_url: null
---

# {book_title}

{chapter_links}
"""


def top_index_mdx(books: list[dict]) -> str:
    book_links = "\n".join(
        f"- [{b['title']}](./{b['slug']}/)" for b in books
    )
    return f"""---
id: index
title: "Oahspe — A Kosmon Bible"
sidebar_label: "All Books"
custom_edit_url: null
---

# Oahspe

A Kosmon Bible in the Words of Jehovih and his Angel Embassadors (1882)

## Books

{book_links}
"""


def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    books_data: list[dict] = []
    if BOOKS_JSON.exists():
        books_data = json.loads(BOOKS_JSON.read_text())

    if not CONTENT_DIR.exists() or not any(
        list(d.glob("chapter-*.json")) for d in CONTENT_DIR.iterdir() if d.is_dir()
    ) if CONTENT_DIR.exists() else True:
        # No content yet — write a placeholder index so the build doesn't fail
        placeholder = DOCS_DIR / "index.md"
        if not placeholder.exists():
            placeholder.write_text(
                "# Oahspe\n\nContent is being prepared. "
                "Run `npm run scrape` to populate the book content.\n",
                encoding="utf-8",
            )
        print("No chapter content found — placeholder index written. Run scrape-sacred-texts.py first.")
        sys.exit(0)

    generated = 0
    slug_to_title = {b["slug"]: b["title"] for b in books_data}
    glossary = load_glossary()

    book_dirs = sorted(d for d in CONTENT_DIR.iterdir() if d.is_dir())

    for book_dir in tqdm(book_dirs, desc="Books", unit="book"):
        slug = book_dir.name
        title = slug_to_title.get(slug, slug.replace("-", " ").title())
        chapter_files = sorted(book_dir.glob("chapter-*.json"))
        if not chapter_files:
            continue

        out_book_dir = DOCS_DIR / slug
        out_book_dir.mkdir(parents=True, exist_ok=True)

        # Per-chapter MDX
        for ch_path in tqdm(chapter_files, desc=slug, unit="ch", leave=False):
            chapter = json.loads(ch_path.read_text())
            num = chapter["chapter"]
            out_path = out_book_dir / f"{num:02d}.mdx"
            out_path.write_text(chapter_mdx(chapter, glossary), encoding="utf-8")
            generated += 1

        # Book index
        idx_path = out_book_dir / "index.mdx"
        idx_path.write_text(book_index_mdx(slug, title, chapter_files), encoding="utf-8")
        generated += 1

    # Top-level index
    top_idx = DOCS_DIR / "index.mdx"
    # Build book list from actual dirs present
    present_books = [
        b for b in books_data
        if (CONTENT_DIR / b["slug"]).is_dir() and sorted((CONTENT_DIR / b["slug"]).glob("chapter-*.json"))
    ]
    if not present_books:
        present_books = [
            {"slug": d.name, "title": d.name.replace("-", " ").title()}
            for d in book_dirs
            if sorted(d.glob("chapter-*.json"))
        ]
    top_idx.write_text(top_index_mdx(present_books), encoding="utf-8")
    generated += 1

    print(f"\nGenerated {generated} MDX files under {DOCS_DIR}")


if __name__ == "__main__":
    main()
