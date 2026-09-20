#!/usr/bin/env python3
"""
Terminology-first, parallel-per-book translation workflow.

Design (locked via two independent reviews, 2026-09-20):
  1. Build an immutable BOOK MANIFEST from source: chapter ids, ordered verse ids,
     per-verse English sha256, preamble/caption records. Refuse non-source-complete input.
  2. Run ONE terminology pass over the whole book's English -> a glossary/lexicon delta
     covering every book-relevant term: canonical headword, slug, category, all three
     transliterations, source_forms (surface spellings as they occur), and occurrences
     (verse ids). Names by sound, deity-ban, ja katakana.
  3. Independently REVIEW that terminology snapshot; cycle until no major issue. Publish an
     immutable snapshot with a content hash (version).
  4. Dispatch chapters IN PARALLEL using only that snapshot. Chapter workers translate text;
     they may NOT coin/fill/alter the dictionary. An unknown term is a hard failure.
  5. Structurally VALIDATE each result against the manifest+snapshot: exact verse coverage,
     nonempty 3 langs, locked translit present for every source occurrence, glossary_terms
     drawn only from snapshot headwords, snapshot/source hashes match.
  6. Independently REVIEW each chapter result; major issue -> revise+re-review; no merge until clean.
  7. FILL-ONLY merge each chapter (never overwrite a non-null translation), re-checking the
     source hash + snapshot version immediately before writing. After all chapters pass, merge
     the reviewed terminology snapshot into the global dictionaries ONCE with a CAS/conflict check.

This module is import-driven (an eval loop or task batch is the engine); there is no CLI.
Shares schema + guide with scripts/translate_orchestrator.py and docs/TRANSLATION_GUIDE.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content" / "books"
TERMS_JSON = ROOT / "content" / "glossary" / "terms.json"
LEXICON_JSON = ROOT / "content" / "style-lexicon.json"
GUIDE_MD = ROOT / "docs" / "TRANSLATION_GUIDE.md"
TRANS_DIR = ROOT / "content" / "books" / ".trans"
SNAPSHOT_DIR = TRANS_DIR / "snapshots"

LANG_KEYS = ("zh_hant", "zh_hans", "ja")


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def chapter_path(book: str, chapter: int) -> Path:
    return CONTENT_DIR / book / f"chapter-{chapter:02d}.json"


def book_chapters(book: str) -> list[int]:
    return sorted(
        int(p.name.split("chapter-")[1].split(".")[0])
        for p in (CONTENT_DIR / book).glob("chapter-*.json")
    )


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Whole-token source matching (the ONLY safe way to select terms; never substring/stem)
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Unicode-normalize + casefold + unify apostrophes so 'Es'enaur' == 'es’enaur'."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\u2019", "'").replace("\u02bc", "'")
    return text.casefold()


# A token is an alphabetic run that MAY contain internal apostrophes/hyphens, so Oahspe
# words like es'enaurs and c'v'wark'um are single tokens (not split on the apostrophe).
_TOKEN_RE = re.compile(r"[a-z]+(?:['-][a-z]+)*")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(_normalize(text))


def phrase_forms(term_entry: dict) -> list[list[str]]:
    """Reviewed surface forms for a term, each as a token sequence. Falls back to the
    canonical term ONLY (whole-token) when no source_forms are declared — never inflects."""
    forms = term_entry.get("source_forms") or [term_entry["term"]]
    return [tokenize(f) for f in forms if tokenize(f)]


def _contains_seq(toks: list[str], seq: list[str]) -> bool:
    """True if `seq` appears as a CONTIGUOUS run in `toks` (order + adjacency, not just membership)."""
    n = len(seq)
    if n == 0 or n > len(toks):
        return False
    return any(toks[i : i + n] == seq for i in range(len(toks) - n + 1))


def term_in_text(term_entry: dict, text: str) -> bool:
    """True if any reviewed source form of the term occurs as a contiguous token run in `text`."""
    toks = tokenize(text)
    return any(_contains_seq(toks, seq) for seq in phrase_forms(term_entry))


def select_terms(source_text: str, terms: list[dict], tagged_slugs: set[str] | None = None) -> list[dict]:
    """Return the subset of `terms` relevant to `source_text` by WHOLE-TOKEN match of each
    term's reviewed source_forms, unioned with any slugs already tagged on the source verses.
    Whole-token-sequence match only: 'Ben' never matches inside 'been'; 'Orian' never matches
    from the compound 'Orian Chiefs' unless 'orian' is itself a declared form."""
    toks = tokenize(source_text)
    # Build a set of contiguous token-sequences present, up to the longest form length.
    max_len = 1
    for t in terms:
        for seq in phrase_forms(t):
            max_len = max(max_len, len(seq))
    present: set[tuple[str, ...]] = set()
    for n in range(1, max_len + 1):
        for i in range(len(toks) - n + 1):
            present.add(tuple(toks[i : i + n]))
    tagged_slugs = tagged_slugs or set()
    out = []
    for t in terms:
        if t["slug"] in tagged_slugs or any(tuple(seq) in present for seq in phrase_forms(t)):
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Book manifest — immutable source fingerprint
# ---------------------------------------------------------------------------

def _chapter_src_sha(mch: dict) -> str:
    """Deterministic fingerprint of ALL mergeable English in a chapter manifest record —
    verses, preamble, and every caption (by stable index) — so the CAS covers everything
    that will be translated, not just verses."""
    parts = [f"v:{v['id']}:{v['en_sha']}" for v in mch["verses"]]
    parts.append(f"p:{_sha(mch.get('preamble_en'))}")
    parts += [f"c:{c['cap_idx']}:{_sha(c['en'])}" for c in mch["captions"]]
    return _sha("|".join(parts))


def build_manifest(book: str) -> dict:
    """Fingerprint the source book: ordered verse ids + English sha per chapter, preamble sha,
    and each caption keyed by a STABLE per-image index (English text is not unique — a verse
    can carry many identical captions). Every mergeable English record is fingerprinted so the
    merge-time CAS covers verses, preamble, AND captions."""
    chapters = book_chapters(book)
    if not chapters:
        raise FileNotFoundError(f"no chapters for book {book!r}")
    man = {"book": book, "chapters": {}}
    for ch in chapters:
        chap = load_json(chapter_path(book, ch), None)
        verses = [
            {"id": v["id"], "verse_number": v["verse_number"], "en_sha": _sha(v.get("en"))}
            for v in chap["verses"]
        ]
        # Caption identity = (verse_id, image_index_within_verse) — stable and unique even
        # when several images on one verse share caption English.
        caps = []
        for v in chap["verses"]:
            for img_i, im in enumerate(v.get("images") or []):
                en = (im.get("caption") or {}).get("en")
                if en:
                    caps.append({"cap_idx": f"{v['id']}#{img_i}", "verse_id": v["id"],
                                 "img_i": img_i, "en": en})
        mch = {
            "chapter_id": chap["id"],
            "verses": verses,
            "preamble_en": (chap.get("preamble") or {}).get("en"),
            "captions": caps,
        }
        mch["src_sha"] = _chapter_src_sha(mch)
        man["chapters"][str(ch)] = mch
    man["book_en_sha"] = _sha("".join(c["src_sha"] for c in man["chapters"].values()))
    return man


def book_source_text(book: str) -> str:
    """All English in a book (verses + preambles + captions) for the terminology pass."""
    parts = []
    for ch in book_chapters(book):
        chap = load_json(chapter_path(book, ch), None)
        pre = (chap.get("preamble") or {}).get("en")
        if pre:
            parts.append(pre)
        for v in chap["verses"]:
            parts.append(v.get("en") or "")
            for im in (v.get("images") or []):
                cap = (im.get("caption") or {}).get("en")
                if cap:
                    parts.append(cap)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Terminology pass — coin/fill EVERY book-relevant term up front
# ---------------------------------------------------------------------------

def _locked_block(terms: list[dict], lexicon: list[dict]) -> str:
    rows = []
    for t in terms:
        tl = t.get("translit") or {}
        if any(tl.get(l) for l in LANG_KEYS):
            rows.append(f"  {t['term']}  →  zh_hant={tl.get('zh_hant')}  zh_hans={tl.get('zh_hans')}  ja={tl.get('ja')}")
    for e in lexicon:
        rows.append(f"  \"{e['en']}\"  →  zh_hant={e.get('zh_hant')}  zh_hans={e.get('zh_hans')}  ja={e.get('ja')}")
    return "\n".join(rows) if rows else "  (none yet)"


def build_terminology_prompt(book: str) -> str:
    """Instruct an agent to produce the COMPLETE terminology delta for a whole book:
    every name/coined term that occurs, with all three transliterations, source_forms
    (the surface spellings as they literally appear), and occurrences (verse ids)."""
    guide = GUIDE_MD.read_text(encoding="utf-8")
    terms = load_json(TERMS_JSON, [])
    lexicon = load_json(LEXICON_JSON, [])
    src = book_source_text(book)
    # existing slugs so the agent FILLs vs COINs correctly
    digest = "\n".join(
        f"  {t['slug']} | {t['term']} | {t.get('category','')} | "
        f"translit={'complete' if all((t.get('translit') or {}).get(l) for l in LANG_KEYS) else 'NULL'}"
        for t in terms
    ) or "  (none yet)"
    return f"""You are the TERMINOLOGY LEAD for one whole book of the Oahspe Bible. Before any
verse is translated, you fix EVERY name and coined term the book uses, so parallel chapter
translators can reuse your renderings verbatim. Follow the guideline EXACTLY.

=== TRANSLATION GUIDELINE (authoritative) ===
{guide}

=== ALREADY-LOCKED TRANSLITERATIONS (reuse verbatim; never re-coin) ===
{_locked_block(terms, lexicon)}

=== EXISTING GLOSSARY SLUGS (FILL by slug; do NOT duplicate) ===
{digest}

=== ENTIRE BOOK SOURCE TEXT: {book} ===
{src}

=== YOUR TASK ===
Scan the whole book. For EVERY name/coined term that occurs (gods, angels, people, places,
Oahspe-coined words like Corpor/Es/I'hin/es'yan), ensure a COMPLETE glossary entry exists:
 - If it already exists with a full translit, do nothing (it is locked).
 - If it exists but a translit/def/note field is null, FILL it (keyed by slug).
 - If it does not exist, COIN a full new entry (sound-based names, deity-ban, ja katakana).
For EACH term you FILL or COIN, you MUST provide:
 - translit for all three languages,
 - "source_forms": the exact surface spellings as they appear in THIS book's English
   (include singular/plural/possessive and spelling variants — e.g. ["es'enaur","es'enaurs"],
   ["waga","wagga"], ["lord","lords","lord's","lords'"]). Lowercase them.
 - "occurrences": verse ids where the term appears (best effort; used for chapter routing).
Ordinary prose words are NOT terms — do not coin them. Distinctive verbs/formulaic phrases
go in new_lexicon per guideline §4b.

Write your result — a single JSON object — with your Write tool to this EXACT path:
  {TRANS_DIR}/{book}.terms.json
Reply only with the word "written". Schema:
{{
  "book": "{book}",
  "fill_glossary": [{{"slug":"...","translit":{{...}},"source_def_literal":{{...}},"editor_note":{{...}},"source_forms":["..."],"occurrences":["..."]}}],
  "new_glossary": [{{"term":"...","slug":"...","category":"name|term","translit":{{...}},"source_def":null,"source_def_literal":{{...}},"editor_note":{{...}},"source_forms":["..."],"occurrences":["..."],"appears_in":[],"cross_refs":[],"locked":true,"first_seen":"{book}"}}],
  "new_lexicon": [{{"en":"...","category":"verb|phrase","zh_hant":"...","zh_hans":"...","ja":"...","note":"...","locked":true,"first_seen":"{book}"}}]
}}
⛔ Write ONLY that file. Do NOT run git/validate/build, do NOT edit any other file."""


def build_terminology_review_prompt(book: str) -> str:
    """Independent review of the terminology delta (completion-friendly: returns JSON)."""
    guide = GUIDE_MD.read_text(encoding="utf-8")
    delta = load_json(TRANS_DIR / f"{book}.terms.json", None)
    if delta is None:
        raise FileNotFoundError(TRANS_DIR / f"{book}.terms.json")
    proposed = (delta.get("fill_glossary") or []) + (delta.get("new_glossary") or [])
    rows = [
        {"slug": p.get("slug"), "term": p.get("term"), "translit": p.get("translit"),
         "source_forms": p.get("source_forms")}
        for p in proposed
    ]
    return f"""You are an INDEPENDENT reviewer of a whole-book terminology delta for the Oahspe
Bible. Judge strictly against the guideline. You did NOT produce this.

=== GUIDELINE ===
{guide}

=== PROPOSED TERMS (fill + new) ===
{json.dumps(rows, ensure_ascii=False, indent=1)}

=== CHECK (report only real defects) ===
MAJOR: a term missing any of the 3 translits; a name mapped to a real-world deity/figure
(Jehovih=耶霍維/ジェホヴィ not 耶和華; Moses not 摩西); a name not transliterated by sound; a ja
name not in katakana; a zh_hant/zh_hans pair that is not a faithful script conversion; a
missing/empty source_forms; a duplicate slug or conflicting rendering of the same name.
MINOR (max 3): register/character-choice slips a reader would notice as wrong.

Return ONLY JSON: {{"book":"{book}","pass":true,"issues":[
  {{"slug":"...","severity":"major|minor","problem":"...","suggestion":"..."}}]}}
"pass" is true iff there are NO major issues."""


# ---------------------------------------------------------------------------
# Snapshot publish (immutable, versioned) + read
# ---------------------------------------------------------------------------

def publish_snapshot(book: str, manifest: dict) -> dict:
    """Freeze the reviewed terminology delta + the terms it selects into an immutable,
    content-hashed snapshot. Chapter workers bind to snapshot['version']."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    delta = load_json(TRANS_DIR / f"{book}.terms.json", {})
    terms = load_json(TERMS_JSON, [])
    lexicon = load_json(LEXICON_JSON, [])
    # Apply the delta IN MEMORY (not to global files yet) to get the book's full term set.
    by_slug = {t["slug"]: dict(t) for t in terms}
    for fill in delta.get("fill_glossary", []):
        t = by_slug.get(fill.get("slug"))
        if t:
            for k in ("translit", "source_def_literal", "editor_note"):
                if isinstance(fill.get(k), dict):
                    cur = dict(t.get(k) or {})
                    for sub, val in fill[k].items():
                        if val and not cur.get(sub):
                            cur[sub] = val
                    t[k] = cur
            if fill.get("source_forms"):
                t["source_forms"] = sorted(set((t.get("source_forms") or []) + fill["source_forms"]))
    for coin in delta.get("new_glossary", []):
        if coin.get("slug") and coin["slug"] not in by_slug:
            by_slug[coin["slug"]] = dict(coin)
    merged_terms = list(by_slug.values())
    src = book_source_text(book)
    selected = select_terms(src, merged_terms)
    snap = {
        "book": book,
        "book_en_sha": manifest["book_en_sha"],
        "terms": selected,
        "lexicon": lexicon + [lx for lx in delta.get("new_lexicon", []) if lx.get("en") not in {e["en"] for e in lexicon}],
        "delta": delta,
    }
    # Version hashes ALL worker-visible content (terms + lexicon + delta + source fingerprint),
    # so any edit to what workers see invalidates the version.
    payload = json.dumps(
        {"terms": snap["terms"], "lexicon": snap["lexicon"], "delta": snap["delta"],
         "book_en_sha": manifest["book_en_sha"]},
        ensure_ascii=False, sort_keys=True,
    )
    snap["version"] = _sha(payload)
    # Store BOTH a version-addressed immutable file and a mutable pointer to the current version.
    (SNAPSHOT_DIR / f"{book}.{snap['version']}.snapshot.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (SNAPSHOT_DIR / f"{book}.current").write_text(snap["version"] + "\n", encoding="utf-8")
    return snap


def read_snapshot(book: str) -> dict | None:
    ptr = SNAPSHOT_DIR / f"{book}.current"
    if not ptr.exists():
        return None
    version = ptr.read_text(encoding="utf-8").strip()
    snap = load_json(SNAPSHOT_DIR / f"{book}.{version}.snapshot.json", None)
    if snap is None:
        return None
    # Re-verify the version matches the content (tamper/immutability check).
    payload = json.dumps(
        {"terms": snap["terms"], "lexicon": snap["lexicon"], "delta": snap["delta"],
         "book_en_sha": snap["book_en_sha"]},
        ensure_ascii=False, sort_keys=True,
    )
    if _sha(payload) != snap.get("version"):
        raise RuntimeError(f"{book}: snapshot content does not match its version hash (tampered)")
    return snap


# ---------------------------------------------------------------------------
# Chapter worker — snapshot-only, NO dictionary mutation
# ---------------------------------------------------------------------------

def _chapter_selected_terms(snap: dict, chap: dict, vmin: int | None, vmax: int | None) -> list[dict]:
    """Terms from the snapshot relevant to THIS chapter's dispatched verses (+preamble/captions)."""
    verses = [v for v in chap["verses"]
              if (vmin is None or v["verse_number"] >= vmin) and (vmax is None or v["verse_number"] <= vmax)]
    text_parts = [(chap.get("preamble") or {}).get("en") or ""]
    tagged = set()
    for v in verses:
        text_parts.append(v.get("en") or "")
        for g in (v.get("glossary_terms") or []):
            tagged.add(g)
        for im in (v.get("images") or []):
            text_parts.append((im.get("caption") or {}).get("en") or "")
    # map tagged headwords -> slugs within the snapshot (case-insensitive)
    ci = {t["term"].lower(): t["slug"] for t in snap["terms"]}
    tagged_slugs = {ci[g.lower()] for g in tagged if g.lower() in ci}
    return select_terms("\n".join(text_parts), snap["terms"], tagged_slugs)


def build_chapter_prompt(book: str, chapter: int, vmin: int | None = None, vmax: int | None = None) -> str:
    """Chapter translator prompt: reuses the FROZEN snapshot terms only. No coin/fill."""
    guide = GUIDE_MD.read_text(encoding="utf-8")
    snap = read_snapshot(book)
    if snap is None:
        raise FileNotFoundError(f"no snapshot for {book}; run the terminology pass first")
    chap = load_json(chapter_path(book, chapter), None)
    if chap is None:
        raise FileNotFoundError(chapter_path(book, chapter))
    src_verses = [
        {"id": v["id"], "verse_number": v["verse_number"], "en": v["en"]}
        for v in chap["verses"]
        if (vmin is None or v["verse_number"] >= vmin) and (vmax is None or v["verse_number"] <= vmax)
    ]
    sel = _chapter_selected_terms(snap, chap, vmin, vmax)
    locked_rows = [
        f"  {t['term']}  →  zh_hant={(t.get('translit') or {}).get('zh_hant')}  "
        f"zh_hans={(t.get('translit') or {}).get('zh_hans')}  ja={(t.get('translit') or {}).get('ja')}"
        for t in sel
    ]
    locked_block = "\n".join(locked_rows) if locked_rows else "  (no coined terms occur in this chapter)"
    lex_rows = [f"  \"{e['en']}\"  →  zh_hant={e.get('zh_hant')}  zh_hans={e.get('zh_hans')}  ja={e.get('ja')}"
                for e in snap.get("lexicon", [])]
    lex_block = "\n".join(lex_rows) if lex_rows else "  (none)"
    preamble_en = (chap.get("preamble") or {}).get("en") or "(none)"
    captions_json = json.dumps(
        [{"cap_idx": f"{v['id']}#{img_i}", "verse_id": v["id"], "en": (im.get("caption") or {}).get("en")}
         for v in chap["verses"]
         for img_i, im in enumerate(v.get("images") or [])
         if (im.get("caption") or {}).get("en")],
        ensure_ascii=False,
    )
    return f"""You are translating one chapter of the Oahspe Bible into zh_hant, zh_hans, ja.
Terminology is ALREADY FIXED by a reviewed book snapshot (version {snap['version']}). Reuse the
renderings below CHARACTER-FOR-CHARACTER. You may NOT invent, change, or add glossary terms.

=== TRANSLATION GUIDELINE (authoritative) ===
{guide}

=== ⚠ SNAPSHOT TRANSLITERATIONS — reuse EXACTLY where the English term occurs ===
{locked_block}

=== SNAPSHOT STYLE-LEXICON (reuse where applicable) ===
{lex_block}

=== CHAPTER {book} ch{chapter} (id={chap['id']}) ===
Preamble to translate (or "(none)"):
{preamble_en}

Image captions to translate (echo cap_idx + en, add 3 langs):
{captions_json}

Verses ({len(src_verses)} total):
{json.dumps(src_verses, ensure_ascii=False, indent=1)}

=== TASK ===
Translate every verse + preamble + captions at the guideline register. Reuse snapshot
transliterations verbatim. Populate each verse's glossary_terms with ONLY the canonical
snapshot headwords that occur in that verse. If you hit a name/coined term NOT in the snapshot,
DO NOT invent one — instead add its English to "unknown_terms" and still translate the verse
leaving the term transliterated as best you can; the driver will treat unknown_terms as a
hard failure to fix upstream.

Write your result — one JSON object — with your Write tool to this EXACT path:
  {TRANS_DIR}/{book}.ch{chapter}.json
Reply only "written". Schema:
{{
  "book": "{book}", "chapter_id": "{chap['id']}", "snapshot_version": "{snap['version']}",
  "book_en_sha": "{snap['book_en_sha']}",
  "preamble": {{"zh_hant":"...","zh_hans":"...","ja":"..."}},
  "captions": [{{"cap_idx":"<echo the cap_idx>","en":"<echo en>","zh_hant":"...","zh_hans":"...","ja":"..."}}],
  "verses": [{{"id":"...","zh_hant":"...","zh_hans":"...","ja":"...","glossary_terms":["..."]}}],
  "unknown_terms": []
}}
⛔ Write ONLY that file. No git/validate/build, no editing any other file. Cover all
{len(src_verses)} verses, same ids, same order."""


def read_chapter_result(book: str, chapter: int) -> dict:
    return load_json(TRANS_DIR / f"{book}.ch{chapter}.json", None)


# ---------------------------------------------------------------------------
# Structural validation (before review + before merge) — proves coverage + locks
# ---------------------------------------------------------------------------

def validate_chapter_result(book: str, chapter: int, manifest: dict) -> list[str]:
    """Prove a chapter result exactly covers the manifest and honors the snapshot. Returns
    a list of hard errors (empty = ok). This is the gate that makes parallelism safe."""
    errs: list[str] = []
    snap = read_snapshot(book)
    res = read_chapter_result(book, chapter)
    if snap is None:
        return [f"{book}.{chapter}: snapshot missing"]
    if res is None:
        return [f"{book}.{chapter}: result file missing"]
    if res.get("snapshot_version") != snap["version"]:
        errs.append(f"{book}.{chapter}: snapshot_version mismatch "
                    f"({res.get('snapshot_version')} != {snap['version']})")
    if snap.get("book_en_sha") != manifest["book_en_sha"]:
        errs.append(f"{book}.{chapter}: snapshot book_en_sha != manifest (stale snapshot)")
    if res.get("book_en_sha") != manifest["book_en_sha"]:
        errs.append(f"{book}.{chapter}: result book_en_sha binding missing/changed "
                    f"({res.get('book_en_sha')} != {manifest['book_en_sha']})")
    if res.get("unknown_terms"):
        errs.append(f"{book}.{chapter}: unknown_terms present (fix terminology upstream): {res['unknown_terms']}")
    mch = manifest["chapters"].get(str(chapter))
    if not mch:
        return errs + [f"{book}.{chapter}: chapter not in manifest"]
    if res.get("chapter_id") != mch["chapter_id"]:
        errs.append(f"{book}.{chapter}: chapter_id mismatch")

    # --- verse coverage: exact, no missing/extra/duplicate/reordered ---
    want_ids = [v["id"] for v in mch["verses"]]
    got = res.get("verses") or []
    got_ids = [v.get("id") for v in got]
    if got_ids != want_ids:
        miss = set(want_ids) - set(got_ids); extra = set(got_ids) - set(want_ids)
        dup = len(got_ids) != len(set(got_ids))
        errs.append(f"{book}.{chapter}: verse coverage mismatch "
                    f"(missing={sorted(miss)[:5]} extra={sorted(extra)[:5]} dup={dup})")
    for v in got:
        for lang in LANG_KEYS:
            if not (v.get(lang) or "").strip():
                errs.append(f"{book}.{chapter}: verse {v.get('id')} missing {lang}"); break
    # kana in a Chinese field is always wrong (Chinese uses no hiragana/katakana) — the
    # classic "wrote Japanese into zh_hant" worker failure. Cheap + certain, so structural.
    _KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")
    for v in got:
        for lang in ("zh_hant", "zh_hans"):
            if _KANA.search(v.get(lang) or ""):
                errs.append(f"{book}.{chapter}: verse {v.get('id')} [{lang}] contains Japanese kana (wrong language)")
                break

    # --- preamble coverage (only if the source has one) ---
    got_pre = res.get("preamble") or {}
    if mch.get("preamble_en"):
        for lang in LANG_KEYS:
            if not (got_pre.get(lang) or "").strip():
                errs.append(f"{book}.{chapter}: preamble missing {lang}")

    # --- caption coverage by stable cap_idx (exact set, 3 langs each) ---
    want_caps = {c["cap_idx"]: c for c in mch["captions"]}
    got_caps = {c.get("cap_idx"): c for c in (res.get("captions") or [])}
    miss_caps = set(want_caps) - set(got_caps); extra_caps = set(got_caps) - set(want_caps)
    if miss_caps or extra_caps:
        errs.append(f"{book}.{chapter}: caption coverage mismatch "
                    f"(missing={sorted(miss_caps)[:4]} extra={sorted(extra_caps)[:4]})")
    for cid, c in got_caps.items():
        if cid in want_caps:
            for lang in LANG_KEYS:
                if not (c.get(lang) or "").strip():
                    errs.append(f"{book}.{chapter}: caption {cid} missing {lang}")

    # --- glossary_terms only from snapshot headwords/slugs ---
    snap_terms_ci = {t["term"].lower() for t in snap["terms"]}
    snap_slugs = {t["slug"] for t in snap["terms"]}
    for v in got:
        for g in (v.get("glossary_terms") or []):
            if g.lower() not in snap_terms_ci and g not in snap_slugs:
                errs.append(f"{book}.{chapter}: verse {v.get('id')} tags unknown term {g!r}")

    # --- exact locks: for every source record, each term whose source_form occurs
    #     CONTIGUOUSLY must carry its locked translit in each language of the SAME record. ---
    chap = load_json(chapter_path(book, chapter), None)
    src_verse_en = {v["id"]: (v.get("en") or "") for v in chap["verses"]}
    def _check_locks(record_en: str, tr: dict, label: str):
        for t in snap["terms"]:
            if not term_in_text(t, record_en):
                continue
            tl = t.get("translit") or {}
            for lang in LANG_KEYS:
                want = tl.get(lang)
                if want and want not in (tr.get(lang) or ""):
                    errs.append(f"{book}.{chapter}: {label} [{lang}] missing locked {t['term']}→{want}")
    for v in got:
        _check_locks(src_verse_en.get(v["id"], ""), v, f"verse {v.get('id')}")
    if mch.get("preamble_en"):
        _check_locks(mch["preamble_en"], got_pre, "preamble")
    for cid, c in got_caps.items():
        if cid in want_caps:
            _check_locks(want_caps[cid]["en"], c, f"caption {cid}")
    return errs


# ---------------------------------------------------------------------------
# Fill-only merge (never overwrite) + global snapshot commit (CAS)
# ---------------------------------------------------------------------------

def merge_chapter(book: str, chapter: int, manifest: dict) -> dict:
    """FILL-ONLY apply a validated result. Self-validates first (refuses on any error), then
    re-checks the FULL chapter source fingerprint (verses+preamble+captions) as a CAS before
    writing. Never overwrites a non-null translation. Captions keyed by stable cap_idx."""
    errs = validate_chapter_result(book, chapter, manifest)
    if errs:
        raise RuntimeError(f"{book}.{chapter}: refusing merge, {len(errs)} validation error(s): {errs[:3]}")
    chap = load_json(chapter_path(book, chapter), None)
    # CAS over ALL mergeable English (verses + preamble + captions), same formula as manifest.
    live_caps = []
    for v in chap["verses"]:
        for img_i, im in enumerate(v.get("images") or []):
            en = (im.get("caption") or {}).get("en")
            if en:
                live_caps.append({"cap_idx": f"{v['id']}#{img_i}", "en": en})
    live_mch = {
        "verses": [{"id": v["id"], "en_sha": _sha(v.get("en"))} for v in chap["verses"]],
        "preamble_en": (chap.get("preamble") or {}).get("en"),
        "captions": live_caps,
    }
    if _chapter_src_sha(live_mch) != manifest["chapters"][str(chapter)]["src_sha"]:
        raise RuntimeError(f"{book}.{chapter}: source changed since manifest — refusing merge")
    res = read_chapter_result(book, chapter)
    by_id = {v["id"]: v for v in chap["verses"]}
    report = {"verses": 0, "skipped_nonnull": 0, "captions": 0}
    for tv in res.get("verses", []):
        v = by_id.get(tv["id"])
        if not v:
            raise ValueError(f"unknown verse id {tv['id']}")
        for lang in LANG_KEYS:
            if tv.get(lang):
                if v.get(lang):
                    report["skipped_nonnull"] += 1
                else:
                    v[lang] = tv[lang]
        if tv.get("glossary_terms") is not None and not v.get("glossary_terms"):
            v["glossary_terms"] = tv["glossary_terms"]
        report["verses"] += 1
    pre = res.get("preamble") or {}
    if isinstance(chap.get("preamble"), dict):
        for lang in LANG_KEYS:
            if pre.get(lang) and not chap["preamble"].get(lang):
                chap["preamble"][lang] = pre[lang]
    # captions: fill-only, keyed by STABLE cap_idx (verse_id#img_index) — never by English.
    cap_by_idx = {c.get("cap_idx"): c for c in (res.get("captions") or [])}
    for v in chap["verses"]:
        for img_i, im in enumerate(v.get("images") or []):
            cap = im.get("caption")
            if not isinstance(cap, dict):
                continue
            c = cap_by_idx.get(f"{v['id']}#{img_i}")
            if not c:
                continue
            for lang in LANG_KEYS:
                if c.get(lang) and not cap.get(lang):
                    cap[lang] = c[lang]
            report["captions"] += 1
    chapter_path(book, chapter).write_text(json.dumps(chap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def commit_snapshot_to_global(book: str) -> dict:
    """After all chapters merge, apply the reviewed terminology delta to the GLOBAL glossary +
    lexicon ONCE. Serialized by a filesystem lock so two concurrent book-commits cannot
    last-writer-wins; globals are re-read INSIDE the lock. Conflicting non-null renderings
    (glossary or lexicon) raise rather than silently drop."""
    import fcntl
    snap = read_snapshot(book)
    delta = snap["delta"]
    report = {"filled": [], "coined": [], "lexicon": [], "conflicts": []}
    lock_path = TRANS_DIR / ".global.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            terms = load_json(TERMS_JSON, [])          # re-read under lock
            by_slug = {t["slug"]: t for t in terms}
            for fill in delta.get("fill_glossary", []):
                t = by_slug.get(fill.get("slug"))
                if not t:
                    continue
                for k in ("translit", "source_def_literal", "editor_note"):
                    if isinstance(fill.get(k), dict):
                        cur = t.get(k) or {}
                        for sub, val in fill[k].items():
                            if val is None:
                                continue
                            if cur.get(sub) and cur[sub] != val:
                                # Existing non-null value is LOCKED and WINS (guide §1.2) — a fill
                                # proposing a different rendering for an already-complete field is
                                # spurious; keep existing, record it. (True cross-book divergence of
                                # NEW coins is caught in the new_glossary branch.)
                                report.setdefault("kept_existing", []).append(f"{t['slug']}.{k}.{sub}")
                            elif not cur.get(sub):
                                cur[sub] = val
                        t[k] = cur
                if fill.get("source_forms"):
                    t["source_forms"] = sorted(set((t.get("source_forms") or []) + fill["source_forms"]))
                if all((t.get("translit") or {}).get(l) for l in LANG_KEYS):
                    t["locked"] = True
                report["filled"].append(t["slug"])
            for coin in delta.get("new_glossary", []):
                if coin.get("slug") in by_slug:
                    # slug now exists (coined by a concurrent book) — downgrade to conflict-checked fill
                    ex = by_slug[coin["slug"]]
                    ex_tl = ex.get("translit") or {}
                    co_tl = coin.get("translit") or {}
                    for l in LANG_KEYS:
                        if ex_tl.get(l) and co_tl.get(l) and ex_tl[l] != co_tl[l]:
                            report["conflicts"].append(f"{coin['slug']}.translit.{l}: {ex_tl[l]!r} != {co_tl[l]!r}")
                    continue
                coin.setdefault("appears_in", [])
                coin.setdefault("cross_refs", [])
                coin["locked"] = True
                terms.append(coin)
                by_slug[coin["slug"]] = coin
                report["coined"].append(coin["slug"])
            lexicon = load_json(LEXICON_JSON, [])       # re-read under lock
            by_en = {e["en"]: e for e in lexicon}
            for lx in delta.get("new_lexicon", []):
                ex = by_en.get(lx.get("en"))
                if ex:
                    for l in LANG_KEYS:
                        if ex.get(l) and lx.get(l) and ex[l] != lx[l]:
                            report["conflicts"].append(f"lexicon {lx['en']!r}.{l}: {ex[l]!r} != {lx[l]!r}")
                    continue
                lexicon.append(lx)
                by_en[lx["en"]] = lx
                report["lexicon"].append(lx["en"])
            if report["conflicts"]:
                raise RuntimeError(f"{book}: snapshot conflicts with global dictionaries: {report['conflicts'][:5]}")
            TERMS_JSON.write_text(json.dumps(terms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            LEXICON_JSON.write_text(json.dumps(lexicon, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
    return report
