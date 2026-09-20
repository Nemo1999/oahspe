#!/usr/bin/env python3
"""
Sequential, one-chapter-at-a-time translation orchestrator.

Consistency model (locked via grilling 2026-09-17):
- STRICTLY sequential: one chapter (=one subagent) at a time, never parallel.
- Each chapter agent receives the full guideline + the CURRENT dictionary state.
- Existing dictionary entries are locked & reused verbatim; agents only FILL nulls
  or COIN brand-new entries. On conflict, existing wins.
- Merge order guarantees chapter N+1 sees everything chapter N coined.

This module is import-driven: a driver (an eval loop or a `task` subagent batch) calls
`build_prompt(book, ch)` → dispatches the prompt to a translation subagent → `parse_agent_json`
→ `verify_locked` (drift guard) → `merge_result` (writes translations, preamble, captions with
existing-wins locking + ja-leak sweep). There is no standalone `__main__`/CLI because the
translation engine is the harness subagent, not a Python-callable API. See docs/TRANSLATION_GUIDE.md.
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


def read_review(book: str, chapter: int) -> dict:
    """Read an independent reviewer's verdict file for this chapter."""
    p = RESULT_DIR / f"ch{chapter}.review.json"
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
Preamble to translate (chapter epigraph; translate its English into all 3 languages):
{(chap.get('preamble') or {{}}).get('en') or '(none)'}

Image captions to translate (verse_id → English caption):
{json.dumps([{{"verse_id": v["id"], "en": (im.get("caption") or {{}}).get("en")}} for v in chap["verses"] for im in (v.get("images") or []) if (im.get("caption") or {{}}).get("en")], ensure_ascii=False)}

Verses ({len(src_verses)} total):
{json.dumps(src_verses, ensure_ascii=False, indent=1)}
=== YOUR TASK ===
Translate every verse into zh_hant, zh_hans, ja per the guideline (register: elevated
modern vernacular / である調; names transliterated by sound per §2; existing locked
entries reused verbatim; clean strings, NO baked parenthetical). ALSO translate the
preamble (if any) and each image caption (if any) at the same register, reusing locked translits.

Distinguish FILL (fill null fields of an existing terms.json entry, keyed by slug) from
COIN (a brand-new entry). Collect distinctive verbs / formulaic phrases into new_lexicon.

Write your result — a single JSON object — using your Write tool to this EXACT path:
  {RESULT_DIR}/ch{chapter}.json

⛔ HARD SCOPE — DO EXACTLY THIS AND NOTHING ELSE. You are ONE step in a central pipeline.
  - Write ONLY the result file above. Do NOT run git (no add/commit/push), validate.py,
    json-to-mdx.py, or any build. Do NOT edit chapter JSON, terms.json, or any other file.
    Do NOT translate verses outside the set given below. Do NOT ask for approval or pause.
  - The driver (not you) validates, merges, and commits. Overstepping corrupts the run.
Do NOT return the JSON in your chat reply (it is large and gets truncated). After writing,
reply only with the word "written". The JSON object must match:
{{
  "chapter_id": "{chap['id']}",
  "preamble": {{"zh_hant": "...", "zh_hans": "...", "ja": "..."}},
  "captions": [{{"verse_id": "...", "en": "<echo the English caption you translated>", "zh_hant": "...", "zh_hans": "...", "ja": "..."}}],
  "verses": [{{"id": "...", "zh_hant": "...", "zh_hans": "...", "ja": "...", "glossary_terms": ["..."]}}],
  "fill_glossary": [{{"slug": "...", "translit": {{"zh_hant":"...","zh_hans":"...","ja":"..."}}, "source_def_literal": {{"zh_hant":"...","zh_hans":"...","ja":"..."}}, "editor_note": {{"en":"...","zh_hant":"...","zh_hans":"...","ja":"..."}}}}],
  "new_glossary": [{{"term":"...","slug":"...","category":"name|term","translit":{{...}},"source_def":null,"source_def_literal":{{...}},"editor_note":{{...}},"appears_in":[],"cross_refs":[],"locked":true,"first_seen":"{chap['id']}"}}],
  "new_lexicon": [{{"en":"...","category":"verb|phrase","zh_hant":"...","zh_hans":"...","ja":"...","note":"...","locked":true,"first_seen":"{chap['id']}"}}],
  "conflict_notes": []
}}
(omit preamble/captions keys if the chapter has none.) verses MUST cover all {len(src_verses)} input verses, same ids, same order."""


def build_review_prompt(book: str, chapter: int) -> str:
    """Assemble instructions for an INDEPENDENT reviewer of one chapter's translation.
    The reviewer sees the source English + the produced translation + the authoritative
    guideline and locked dictionary, and emits a verdict file listing concrete issues."""
    guide = GUIDE_MD.read_text(encoding="utf-8")
    terms = load_json(TERMS_JSON, [])
    chap = load_json(chapter_path(book, chapter), None)
    if chap is None:
        raise FileNotFoundError(chapter_path(book, chapter))
    result = read_result(book, chapter)

    locked_rows = []
    for t in terms:
        tl = t.get("translit", {})
        if any(tl.get(l) for l in LANG_KEYS):
            locked_rows.append(
                f"  {t['term']}  →  zh_hant={tl.get('zh_hant')}  zh_hans={tl.get('zh_hans')}  ja={tl.get('ja')}"
            )
    locked_block = "\n".join(locked_rows) if locked_rows else "  (none yet)"

    # Pair each translated verse with its English source so the reviewer can judge fidelity.
    by_id = {v["id"]: v for v in chap["verses"]}
    pairs = []
    for tv in result.get("verses", []):
        src = by_id.get(tv["id"], {})
        pairs.append({
            "id": tv["id"],
            "en": src.get("en"),
            "zh_hant": tv.get("zh_hant"),
            "zh_hans": tv.get("zh_hans"),
            "ja": tv.get("ja"),
            "glossary_terms": tv.get("glossary_terms"),
        })

    return f"""You are an INDEPENDENT reviewer of an Oahspe Bible translation. You did NOT
produce this translation. Judge it strictly and fairly against the guideline and the
locked dictionary. Your job is to catch real defects, not to rewrite to taste.

=== TRANSLATION GUIDELINE (authoritative) ===
{guide}

=== LOCKED TRANSLITERATIONS (must appear CHARACTER-FOR-CHARACTER where the English term occurs) ===
{locked_block}

=== CHAPTER: {book} chapter {chapter} (id={chap['id']}) ===
Translated preamble (English → 3 langs), captions, and verses to review:
preamble_en: {(chap.get('preamble') or {{}}).get('en') or '(none)'}
preamble_translation: {json.dumps(result.get('preamble') or {{}}, ensure_ascii=False)}
captions: {json.dumps(result.get('captions') or [], ensure_ascii=False)}

verses (source en paired with translation):
{json.dumps(pairs, ensure_ascii=False, indent=1)}

=== WHAT TO CHECK (report only real problems) ===
1. FIDELITY: does each translation convey the English meaning? Flag omissions, additions,
   reversed meaning, dropped clauses, mistranslated theology.
2. LOCKED TERMS: if the English verse contains a locked term (whole word), its exact locked
   transliteration MUST appear in that language's text. Flag drift (e.g. 柯珀 vs 珂珀).
3. NAMES: transliterated by SOUND per §2; never an existing real-world deity/figure name
   (e.g. Jehovih is 耶霍維/ジェホヴィ, NOT 耶和華; Moses is NOT 摩西). Flag violations.
4. JAPANESE PURITY: ja must not borrow Chinese-only transliterations; names in katakana.
   Flag zh characters leaking into ja names.
5. REGISTER: elevated modern scripture (書面語 / である調), consistent across verses.
6. COMPLETENESS: every verse present in all 3 langs; preamble & captions translated.

Write your verdict — a single JSON object — using your Write tool to this EXACT path:
  {RESULT_DIR}/ch{chapter}.review.json

⛔ HARD SCOPE — write ONLY the verdict file above. Do NOT run git, validate.py, json-to-mdx.py,
  or any build; do NOT edit the translation or any content file; do NOT fix it yourself. You
  only judge and report. The driver handles revision and merge.
Reply only with the word "reviewed". The JSON object MUST match:
{{
  "chapter_id": "{chap['id']}",
  "pass": true,
  "issues": [
    {{"id": "<verse_id | 'preamble' | 'caption:<verse_id>'>", "lang": "zh_hant|zh_hans|ja",
      "severity": "major|minor", "problem": "<what is wrong>", "suggestion": "<concrete fix>"}}
  ]
}}
Set "pass": true and "issues": [] ONLY if the translation is fully correct. List EVERY real
issue you find; be specific (quote the offending text). Do NOT invent issues to seem thorough."""


def build_revise_prompt(book: str, chapter: int, issues: list[dict], vmin: int | None = None, vmax: int | None = None) -> str:
    """Assemble instructions to REVISE a translation given a reviewer's issue list.
    Reuses the full translate prompt (guideline, locked table, schema) and appends the
    concrete defects plus the current (flawed) result so the agent produces a fixed file."""
    base = build_prompt(book, chapter, vmin, vmax)
    result = read_result(book, chapter)
    return f"""{base}

=== ⚠ THIS IS A REVISION PASS ===
An independent reviewer found problems in the PREVIOUS translation of this chapter. Your
PREVIOUS output was:
{json.dumps(result, ensure_ascii=False)}

The reviewer's issues (fix EVERY one; keep everything else that was already correct):
{json.dumps(issues, ensure_ascii=False, indent=1)}

Produce a COMPLETE corrected result JSON (same schema, all verses, preamble, captions) and
Write it to the SAME path {RESULT_DIR}/ch{chapter}.json, overwriting the previous file.
Reply only with the word "written"."""


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


def _sweep_ja_leaks(book: str, chapter: int) -> int:
    """Repair the failure where a verse's ja field borrows a term's Chinese transliteration
    instead of its locked katakana (e.g. 以太界 instead of エセ界).

    SAFETY: only rewrites a term's zh-form in a verse when that term is TAGGED in the verse's
    glossary_terms — never a blind substring sweep. This avoids corrupting incidental kanji
    (e.g. common characters like 本/波 that happen to be another term's translit). Returns
    the number of verses changed."""
    terms = load_json(TERMS_JSON, [])
    # English term → {zh_hant, zh_hans} → ja (only when ja is katakana and differs from zh).
    term_map = {}
    for t in terms:
        tl = t.get("translit") or {}
        jt = tl.get("ja")
        if not (jt and re.search(r"[\u30a0-\u30ff]", jt)):
            continue
        zforms = [tl.get("zh_hant"), tl.get("zh_hans")]
        zforms = [z for z in zforms if z and z != jt]
        if zforms:
            term_map[t["term"]] = (zforms, jt)
    if not term_map:
        return 0
    chap = load_json(chapter_path(book, chapter), None)
    fixed = 0
    for v in chap["verses"]:
        ja = v.get("ja")
        if not ja:
            continue
        new = ja
        for term in (v.get("glossary_terms") or []):
            entry = term_map.get(term)
            if not entry:
                continue
            zforms, jt = entry
            for zt in zforms:
                if zt in new:
                    new = new.replace(zt, jt)
        if new != ja:
            v["ja"] = new
            fixed += 1
    if fixed:
        chapter_path(book, chapter).write_text(json.dumps(chap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixed


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

    # 1b) Preamble translations (fill only null languages; never touch en/source)
    pre_tr = result.get("preamble") or {}
    if isinstance(chap.get("preamble"), dict):
        for lang in LANG_KEYS:
            if pre_tr.get(lang) and not chap["preamble"].get(lang):
                chap["preamble"][lang] = pre_tr[lang]

    # 1c) Caption translations. Key by (verse_id, en) so multi-image galleries (a verse with
    # several distinct captions) each match their own image — not one translation for all.
    cap_pairs = {}   # (verse_id, en) -> translations
    cap_by_vid = {}  # verse_id -> translations (fallback for single-caption verses w/o en)
    for c in (result.get("captions") or []):
        vid = c.get("verse_id")
        if c.get("en"):
            cap_pairs[(vid, c["en"])] = c
        cap_by_vid.setdefault(vid, c)
    for v in chap["verses"]:
        for im in (v.get("images") or []):
            cap = im.get("caption")
            if not isinstance(cap, dict):
                continue
            c = cap_pairs.get((v["id"], cap.get("en"))) or (
                cap_by_vid.get(v["id"]) if len([i for i in v["images"] if i.get("caption")]) == 1 else None
            )
            if not c:
                continue
            for lang in LANG_KEYS:
                if c.get(lang) and not cap.get(lang):
                    cap[lang] = c[lang]
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

    # 4) Auto-repair ja fields that leaked a term's zh transliteration (post-glossary,
    #    so newly-coined terms are covered).
    report["ja_fixed"] = _sweep_ja_leaks(book, chapter)

    return report

def verify_locked(result: dict, book: str | None = None, chapter: int | None = None) -> list[str]:
    """Detect consistency drift BEFORE merge: when a verse's ENGLISH source actually
    contains a locked term, that term's locked transliteration MUST appear in the
    translated text. Catches paraphrase drift (柯珀→珂珀) without false-flagging verses
    that merely reference a being obliquely (e.g. 'Thy Father' tagged as Jehovih)."""
    terms = load_json(TERMS_JSON, [])
    locked = {}
    for t in terms:
        tl = t.get("translit", {})
        if any(tl.get(l) for l in LANG_KEYS):
            locked[t["term"]] = tl
    # Map verse id → source English, to gate on actual term presence.
    src_en = {}
    if book and chapter is not None:
        chap = load_json(chapter_path(book, chapter), None)
        if chap:
            src_en = {v["id"]: (v.get("en") or "") for v in chap["verses"]}
    violations = []
    for v in result.get("verses", []):
        en_src = src_en.get(v["id"], "")
        for term in v.get("glossary_terms", []) or []:
            tl = locked.get(term)
            if not tl:
                continue
            # Only enforce when the term name really occurs in the source verse as a
            # whole word (so 'Corpor' is not matched inside 'corporeal').
            if src_en and not re.search(rf"\b{re.escape(term)}\b", en_src, re.I):
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
