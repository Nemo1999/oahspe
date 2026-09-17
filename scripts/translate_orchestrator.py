#!/usr/bin/env python3
"""
Sequential, one-chapter-at-a-time translation orchestrator.

Consistency model (locked via grilling 2026-09-17):
- STRICTLY sequential: one chapter (=one subagent) at a time, never parallel.
- Each chapter agent receives the full guideline + the CURRENT dictionary state.
- Existing dictionary entries are locked & reused verbatim; agents only FILL nulls
  or COIN brand-new entries. On conflict, existing wins.
- Merge order guarantees chapter N+1 sees everything chapter N coined.

This module is import-driven (call run_chapter / merge_result from an eval cell or
a thin CLI), because the translation engine is the harness subagent, not an API key.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content" / "books"
TERMS_JSON = ROOT / "content" / "glossary" / "terms.json"
LEXICON_JSON = ROOT / "content" / "style-lexicon.json"
GUIDE_MD = ROOT / "docs" / "TRANSLATION_GUIDE.md"

LANG_KEYS = ("zh_hant", "zh_hans", "ja")


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def chapter_path(book: str, chapter: int) -> Path:
    return CONTENT_DIR / book / f"chapter-{chapter:02d}.json"


def build_prompt(book: str, chapter: int) -> str:
    """Assemble the full self-contained instruction for one chapter's subagent."""
    guide = GUIDE_MD.read_text(encoding="utf-8")
    terms = load_json(TERMS_JSON, [])
    lexicon = load_json(LEXICON_JSON, [])
    chap = load_json(chapter_path(book, chapter), None)
    if chap is None:
        raise FileNotFoundError(chapter_path(book, chapter))

    # Ship only the source fields the agent needs (id, verse_number, en) — keep it lean.
    src_verses = [
        {"id": v["id"], "verse_number": v["verse_number"], "en": v["en"]}
        for v in chap["verses"]
    ]

    return f"""You are translating one chapter of the Oahspe Bible. Follow the guideline EXACTLY.

=== TRANSLATION GUIDELINE (authoritative) ===
{guide}

=== CURRENT GLOSSARY (terms.json) — reader-facing, LOCKED where non-null ===
{json.dumps(terms, ensure_ascii=False, indent=1)}

=== CURRENT STYLE-LEXICON (style-lexicon.json) — internal, LOCKED where present ===
{json.dumps(lexicon, ensure_ascii=False, indent=1)}

=== CHAPTER TO TRANSLATE: {book} chapter {chapter} (id={chap['id']}) ===
Preamble (context only, do NOT translate into the verses array):
{chap.get('preamble','')}

Verses ({len(src_verses)} total):
{json.dumps(src_verses, ensure_ascii=False, indent=1)}

=== YOUR TASK ===
Translate every verse into zh_hant, zh_hans, ja per the guideline (register: elevated
modern vernacular / である調; names transliterated by sound per §2; existing locked
entries reused verbatim; clean strings, NO baked parenthetical).

Distinguish FILL (fill null fields of an existing terms.json entry, keyed by slug) from
COIN (a brand-new entry). Collect distinctive verbs / formulaic phrases into new_lexicon.

Return ONLY a single JSON object, no markdown fences, no commentary, matching:
{{
  "chapter_id": "{chap['id']}",
  "verses": [{{"id": "...", "zh_hant": "...", "zh_hans": "...", "ja": "...", "glossary_terms": ["..."]}}],
  "fill_glossary": [{{"slug": "...", "translit": {{"zh_hant":"...","zh_hans":"...","ja":"..."}}, "source_def_literal": {{"zh_hant":"...","zh_hans":"...","ja":"..."}}, "editor_note": {{"en":"...","zh_hant":"...","zh_hans":"...","ja":"..."}}}}],
  "new_glossary": [{{"term":"...","slug":"...","category":"name|term","translit":{{...}},"source_def":null,"source_def_literal":{{...}},"editor_note":{{...}},"appears_in":[],"cross_refs":[],"locked":true,"first_seen":"{chap['id']}"}}],
  "new_lexicon": [{{"en":"...","category":"verb|phrase","zh_hant":"...","zh_hans":"...","ja":"...","note":"...","locked":true,"first_seen":"{chap['id']}"}}],
  "conflict_notes": []
}}
verses MUST cover all {len(src_verses)} input verses, same ids, same order."""


# ---------------------------------------------------------------------------
# Merge (existing-wins locking)
# ---------------------------------------------------------------------------

def _fill_nulls(dst: dict, src: dict, keys: list[str]):
    """Fill only currently-null/absent scalar-or-dict fields; never overwrite non-null."""
    filled = []
    for k in keys:
        incoming = src.get(k)
        if incoming is None:
            continue
        cur = dst.get(k)
        if cur is None:
            dst[k] = incoming
            filled.append(k)
        elif isinstance(cur, dict) and isinstance(incoming, dict):
            for sub, val in incoming.items():
                if val is not None and cur.get(sub) is None:
                    cur[sub] = val
                    filled.append(f"{k}.{sub}")
    return filled


def merge_result(book: str, chapter: int, result: dict) -> dict:
    """Apply one chapter agent's output to disk with existing-wins locking.
    Returns a summary dict. Idempotent-ish: re-running fills only remaining nulls."""
    report = {"verses": 0, "filled": [], "coined": [], "lexicon": [], "conflicts": result.get("conflict_notes", [])}

    # 1) Verses → merge translations back into the chapter file
    chap = load_json(chapter_path(book, chapter), None)
    by_id = {v["id"]: v for v in chap["verses"]}
    for tv in result.get("verses", []):
        v = by_id.get(tv["id"])
        if not v:
            raise ValueError(f"agent returned unknown verse id {tv['id']!r}")
        for lang in LANG_KEYS:
            if tv.get(lang):
                v[lang] = tv[lang]
        if tv.get("glossary_terms") is not None:
            v["glossary_terms"] = tv["glossary_terms"]
        report["verses"] += 1
    chapter_path(book, chapter).write_text(json.dumps(chap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 2) Glossary: FILL existing (by slug), COIN new
    terms = load_json(TERMS_JSON, [])
    by_slug = {t["slug"]: t for t in terms}
    cid = f"{book}.{chapter}"
    for fill in result.get("fill_glossary", []):
        t = by_slug.get(fill.get("slug"))
        if not t:
            continue  # unknown slug → ignore (agent may re-propose as new)
        got = _fill_nulls(t, fill, ["translit", "source_def_literal", "editor_note"])
        if got:
            if t.get("first_seen") is None:
                t["first_seen"] = cid
            if all(t.get("translit", {}).get(l) for l in LANG_KEYS):
                t["locked"] = True
            report["filled"].append({"slug": t["slug"], "fields": got})
    for coin in result.get("new_glossary", []):
        if coin.get("slug") in by_slug:
            # collides with existing → downgrade to a fill, existing wins
            got = _fill_nulls(by_slug[coin["slug"]], coin, ["translit", "source_def_literal", "editor_note"])
            if got:
                report["filled"].append({"slug": coin["slug"], "fields": got})
            continue
        coin.setdefault("appears_in", [])
        coin.setdefault("cross_refs", [])
        coin.setdefault("first_seen", cid)
        coin["locked"] = True
        terms.append(coin)
        by_slug[coin["slug"]] = coin
        report["coined"].append(coin["slug"])
    TERMS_JSON.write_text(json.dumps(terms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 3) Style-lexicon: append new only (existing wins by 'en' key)
    lexicon = load_json(LEXICON_JSON, [])
    have = {e["en"] for e in lexicon}
    for lx in result.get("new_lexicon", []):
        if lx.get("en") in have:
            continue
        lx.setdefault("first_seen", cid)
        lx["locked"] = True
        lexicon.append(lx)
        have.add(lx["en"])
        report["lexicon"].append(lx["en"])
    LEXICON_JSON.write_text(json.dumps(lexicon, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return report


def parse_agent_json(raw: str) -> dict:
    """Robustly extract the JSON object from an agent's text reply."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n", "", raw)
        raw = re.sub(r"\n```\s*$", "", raw)
    # Find outermost {...}
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in agent reply")
    return json.loads(raw[start : end + 1])
