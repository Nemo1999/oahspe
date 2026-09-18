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
RESULT_DIR = ROOT / "content" / "books" / ".trans"

LANG_KEYS = ("zh_hant", "zh_hans", "ja")


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def chapter_path(book: str, chapter: int) -> Path:
    return CONTENT_DIR / book / f"chapter-{chapter:02d}.json"


def read_result(book: str, chapter: int) -> dict:
    """Read an agent-written result file (file handoff avoids output-token/IRC limits)."""
    p = RESULT_DIR / f"ch{chapter}.json"
    if not p.exists():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def build_prompt(book: str, chapter: int, vmin: int | None = None, vmax: int | None = None) -> str:
    """Assemble the full self-contained instruction for one chapter's subagent.
    Optional vmin/vmax (inclusive verse_number bounds) split a large chapter into
    smaller batches so the agent's Write payload stays within its output limit."""
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
        if (vmin is None or v["verse_number"] >= vmin) and (vmax is None or v["verse_number"] <= vmax)
    ]
    # Build an explicit LOCKED table — the single most-missed rule is reusing prior
    # transliterations verbatim in the verse TEXT (not just the dictionary).
    locked_rows = []
    for t in terms:
        tl = t.get("translit", {})
        if any(tl.get(l) for l in LANG_KEYS):
            locked_rows.append(
                f"  {t['term']}  →  zh_hant={tl.get('zh_hant')}  zh_hans={tl.get('zh_hans')}  ja={tl.get('ja')}"
            )
    for e in lexicon:
        locked_rows.append(
            f"  \"{e['en']}\"  →  zh_hant={e.get('zh_hant')}  zh_hans={e.get('zh_hans')}  ja={e.get('ja')}"
        )
    locked_block = "\n".join(locked_rows) if locked_rows else "  (none yet — this is the first chapter)"

    return f"""You are translating one chapter of the Oahspe Bible. Follow the guideline EXACTLY.

=== TRANSLATION GUIDELINE (authoritative) ===
{guide}

=== ⚠ LOCKED TRANSLITERATIONS — you MUST use these EXACT characters in the verse text ===
These names/terms were fixed by earlier chapters. Reproduce them CHARACTER-FOR-CHARACTER
wherever they occur. Do NOT re-coin, paraphrase, or pick different characters. Do NOT put
them in fill_glossary/new_glossary again (they are already complete).
{locked_block}

=== CURRENT GLOSSARY (terms.json) — reader-facing; fill only NULL fields ===
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

Write your result — a single JSON object — using your Write tool to this EXACT path:
  {RESULT_DIR}/ch{chapter}.json
Do NOT return the JSON in your chat reply (it is large and gets truncated). After writing,
reply only with the word "written". The JSON object must match:
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

def verify_locked(result: dict) -> list[str]:
    """Detect consistency drift BEFORE merge: for every verse term that has a locked
    transliteration, that exact string must appear in the verse text. Returns a list of
    human-readable violations (empty = clean). This catches an agent paraphrasing a
    locked name (e.g. 柯珀 → 珂珀) in the verse body."""
    terms = load_json(TERMS_JSON, [])
    locked = {}
    for t in terms:
        tl = t.get("translit", {})
        if any(tl.get(l) for l in LANG_KEYS):
            locked[t["term"]] = tl
    violations = []
    for v in result.get("verses", []):
        for term in v.get("glossary_terms", []) or []:
            tl = locked.get(term)
            if not tl:
                continue
            for lang in LANG_KEYS:
                want = tl.get(lang)
                if want and want not in (v.get(lang) or ""):
                    violations.append(
                        f"{v['id']} [{lang}]: term {term!r} locked as {want!r} not found in text"
                    )
    return violations


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
