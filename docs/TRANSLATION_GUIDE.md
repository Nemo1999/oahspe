# Oahspe Translation Guideline & Rules

> Status: Locked via grilling session, 2026-09-17
> Languages: `zh_hant` (Traditional Chinese), `zh_hans` (Simplified Chinese), `ja` (Japanese)
> This document is the **verbatim instruction** given to every per-chapter translation subagent.
> Companion: `docs/DESIGN.md` (site architecture), `content/style-lexicon.json` (internal), `content/glossary/terms.json` (reader-facing).

---

## 0. Execution Model (how translation runs)

> **Updated 2026-09-20 — terminology-first, parallel-per-book.** Superseded the old strictly-
> sequential model after two independent design reviews + a safety audit. Engine:
> `scripts/translate_book.py` (import-driven; an eval loop or task batch is the driver).
> The older `scripts/translate_orchestrator.py` (sequential, per-chapter coining) still works but
> is NOT how the body run proceeds.

**Per book, in this order (books run one at a time; glossary grows monotonically across books):**
1. **Manifest** — `build_manifest(book)` fingerprints the immutable source: ordered verse ids +
   per-verse English sha, preamble sha, and every caption keyed by a STABLE `cap_idx`
   (`verse_id#image_index` — caption English is NOT unique). `book_en_sha` covers all of it.
2. **Terminology pass** — ONE agent (`build_terminology_prompt`) scans the WHOLE book and fixes
   EVERY name/coined term up front: all three transliterations, `source_forms` (surface spellings
   as they literally occur — plural/possessive/variant, lowercased), and occurrences. This is the
   only step that coins/fills the dictionary.
3. **Terminology review** — an independent reviewer (`build_terminology_review_prompt`, run via
   `completion(model="slow", schema=…)`) gates on MAJOR defects (missing translit, deity-name,
   non-katakana ja, duplicate/conflicting rendering). Cycle until clean.
4. **Publish snapshot** — `publish_snapshot` freezes the reviewed terms + lexicon + delta into an
   IMMUTABLE, content-hashed, version-addressed file. Chapter workers bind to `snapshot.version`.
5. **Parallel chapters** — chapters translate concurrently (`build_chapter_prompt`), each seeing
   ONLY the frozen snapshot. Workers may NOT coin/fill/alter the dictionary; an unknown term is a
   hard failure (`unknown_terms`), fixed upstream in the terminology pass, not merged opportunistically.
6. **Per-chapter validate + review** — `validate_chapter_result` proves exact verse+preamble+caption
   coverage, nonempty 3 langs, no kana in Chinese fields, `glossary_terms` ⊆ snapshot, and every
   contiguous source occurrence of a locked term carries its exact translit. Then an independent
   chapter reviewer. MAJOR issue → revise that one chapter → re-review. No merge until clean.
7. **Fill-only merge** — `merge_chapter` self-validates, re-checks the full chapter source fingerprint
   (CAS), and NEVER overwrites a non-null translation. Captions keyed by `cap_idx`.
8. **Global commit (once/book)** — `commit_snapshot_to_global` applies the reviewed delta to the
   global glossary/lexicon under a filesystem lock, re-reading inside the lock. **Translit** mismatch
   with an existing non-null value = hard conflict; prose fields (`source_def_literal`/`editor_note`)
   and already-locked translits = existing wins silently.
9. **Deploy** — validate.py → json-to-mdx.py → commit + push (per book).

**Why parallel is safe here (was "NEVER parallel"):** consistency no longer depends on serialization
because terminology is fixed and reviewed BEFORE any verse is translated, then frozen in an immutable
snapshot. Chapters can't race the dictionary because they can't touch it. See the audit-driven
invariants in `scripts/translate_book.py` docstring.

---

## 1. Golden Rules (never violate)

1. **Names of beings are transliterated by SOUND, never mapped to an existing entity.** `Jehovih` MUST NOT become `耶和華` / `エホバ` (that is Yahweh). Coin a distinct sound-based rendering.
2. **Existing entries are LOCKED.** If a term/name/phrase already exists in `terms.json` or `style-lexicon.json`, reuse its rendering **verbatim**. Never re-coin. On any conflict, the existing entry wins.
3. **You only propose entries that are NEW** (not already in the two files).
4. **Translations are stored CLEAN** — no inline `（English）` parenthetical baked into the verse text. The reader UI injects that at render time from the dictionary. (You DO populate each verse's `glossary_terms` list with the canonical English headwords present in that verse.)
5. **Register:** Chinese = elevated modern vernacular (書面語 / semi-formal 白話); Japanese = elevated modern literary (である調, formal). Reverent, dignified, readable. NOT classical/文言文/文語.
6. **Preserve the source structure:** one input verse → one output verse, same order, same count. Never merge or split verses.

---

## 2. Transliteration of Names (gods, angels, people)

### 2a. Chinese (`zh_hant` / `zh_hans`)
- Transliterate from the **English pronunciation**, syllable by syllable.
- **Character selection — phonetic-neutral + scriptural register:**
  - Prefer characters used in the Buddhist/Daoist scripture-transliteration tradition (譯經): 阿, 摩, 迦, 羅, 那, 提, 維, 陀, 曇, 訶, 耶, 霍, 薩, 尼, etc. Names should feel *scriptural*, not like brand names.
  - Prefer characters with **weak/neutral meaning** (旁, 維, 需, 嚕) over semantically loaded ones.
  - **BANNED:** any character string that names an existing deity/mythological figure — 耶和華, 上帝, 佛, 神 (as a name), 上天 (as a name), 天主, 真主, 玉皇, etc.
- Provide both `zh_hant` and `zh_hans` forms (usually the same characters in different script; convert faithfully).
- Example: `Jehovih` → `耶霍維` / `耶霍维` (illustrative — chapter-1 agent proposes, human approves).

### 2b. Japanese (`ja`)
- **Katakana**, transliterated from the **English sound**, independently of the Chinese choice.
- Katakana already reads as a foreign proper noun, so collision risk is low — but still **BAN the established `エホバ`** (= Yahweh) for Jehovih; coin a distinct form (e.g. `ジェホヴィ`).
- Never use kanji for coined names (avoids deity collision + keeps register consistent).

### 2c. Ordinary human names in the narrative
- Same rules: sound-based, dictionary-locked. If Oahspe's own glossary gives a pronunciation hint, honor it.

---

## 3. The (English) Parenthetical + Glossary Link — DATA ONLY, not baked text

- Coined/transliterated terms (names + Oahspe-specific coined words like `Corpor`, `Es`, `Ethe`, `I'hin`, `Se'muan`) are shown to the reader as `譯名（English）` on **EVERY occurrence** (updated 2026-09: was first-occurrence-per-chapter; now every occurrence so no mention is ambiguous). Rendered by `VerseReader` from `terms.json`.
- Each rendered term is also a **hyperlink to its glossary page** (`/glossary#slug`) — inherits text color, underlines on hover only. `VerseReader` builds this from the term's `slug`.
- **Your job:** store the clean translation, and list the canonical English headword in that verse's `glossary_terms`. **Do NOT** write the parenthesis or the link yourself — the component does that from `glossary_terms` + `terms.json`.
- Ordinary translated vocabulary gets **no** parenthetical (handled by dictionary consistency).
- This applies equally to **image captions** and **preambles**: any coined term appearing in a translated caption/preamble is auto-annotated + linked by the reader, as long as the verse's `glossary_terms` lists it.

---

## 4. Two Dictionaries

### 4a. `content/glossary/terms.json` — READER-FACING (names + coined terms)
Entry shape:
```json
{
  "term": "Jehovih",
  "slug": "jehovih",
  "category": "name",                 // "name" | "term"
  "translit": { "zh_hant": "耶霍維", "zh_hans": "耶霍维", "ja": "ジェホヴィ" },
  "source_def": "The Creator; the All Person; ...",   // Oahspe's own glossary, VERBATIM, never edited; null if book gives none
  "source_def_literal": { "zh_hant": "...", "zh_hans": "...", "ja": "..." },  // FAITHFUL literal translation of source_def — NOT interpretation
  "editor_note": { "en": "...", "zh_hant": "...", "zh_hans": "...", "ja": "..." },  // YOUR interpretation/summary — free, per-language, may differ per language
  "appears_in": ["jehovih.1.3"],
  "cross_refs": ["ethe", "corpor"],
  "source_forms": ["jehovih", "jehovih's"],  // surface spellings as they occur (lowercased); WHOLE-TOKEN matched for selection + locking
  "locked": true,
  "first_seen": "jehovih.1.3"
}
```
- **`source_def`**: pulled from Oahspe's "Glossary Of Strange Words," verbatim. **NEVER touch it with creativity.** `null` if the book doesn't define the term.
- **`source_def_literal`**: a faithful, *literal* translation of `source_def` (so CJK readers can read the authoritative definition). Faithful ≠ creative. Omit where `source_def` is null.
- **`editor_note`**: YOUR own summary/interpretation. Free, and **language-specific** — the `ja` note is the ja-translator's take, not a translation of the `en` note. Rendered as an obvious "Editor's note / 編者註 / 訳者註" callout so readers never mistake it for scripture.

### 4b. `content/style-lexicon.json` — INTERNAL (verbs + recurring phrases; reader never sees this)
Entry shape:
```json
{
  "en": "quickened",
  "category": "verb",                 // "verb" | "phrase"
  "zh_hant": "...", "zh_hans": "...", "ja": "...",
  "note": "spiritual awakening sense, not literal 'sped up'",
  "locked": true,
  "first_seen": "jehovih.1.9"
}
```
- **Only lock** entries that are: (a) distinctive to Oahspe's voice / theologically loaded — `quickened`, `corporeal man`, `All Light`, `the Father's kingdom`, `raised in spirit`; OR (b) recurring formulaic phrases — `Thus saith Jehovih`, `in the beginning`.
- **Do NOT lock** ordinary prose verbs (`walked`, `said`, `gave`) — translate those naturally.
- This file exists purely to keep the *voice* consistent across chapters. It is never rendered.

---

## 5. Reader Glossary Definitions (source of truth)

- `source_def` comes from **Oahspe's own "Glossary Of Strange Words"** — authoritative, verbatim, immutable.
- For coined terms the book does not define, `source_def` is `null` and you supply understanding via `editor_note` only.
- Never blend the two: source is the text's voice, editor_note is yours.

---

## 6. Consistency Protocol (two distinct roles)

The old "every agent coins as it goes" is retired. There are now two roles:

### 6a. Terminology-pass agent (once per book, BEFORE any verse)
1. Read `terms.json` + `style-lexicon.json` fully. Scan the WHOLE book's English.
2. For EVERY name/coined term that occurs:
   - **FILL** — term exists in `terms.json` but a `translit`/`source_def_literal`/`editor_note` is
     `null`: fill those nulls (coin translit per §2). Return under `fill_glossary`, keyed by `slug`.
   - **COIN** — term not in `terms.json` at all: create a full new entry under `new_glossary`.
   - **`source_forms` (REQUIRED)** — for each FILL/COIN, list the exact surface spellings as they
     literally appear in the book (lowercased: singular/plural/possessive/variant, e.g.
     `["es'enaur","es'enaurs"]`, `["lord","lords","lord's","lords'"]`, `["waga","wagga"]`).
     Selection + lock-checking are WHOLE-TOKEN against these forms — never substring/stem (the
     `Ben`→`本` trap). A missing/wrong `source_forms` means the term won't be selected or locked.
3. Never overwrite a non-null (locked) field. Existing always wins.
4. Collect distinctive verbs/formulaic phrases (§4b) as `new_lexicon`.

### 6b-worker. Chapter-translation agent (parallel, snapshot-only)
1. Reuse the frozen snapshot's transliterations VERBATIM. You may NOT coin, fill, or alter any
   dictionary entry — the terminology pass already fixed them.
2. Translate every verse into all 3 languages; populate `glossary_terms` with ONLY canonical
   snapshot headwords present in the verse.
3. Never put Japanese kana in a `zh_hant`/`zh_hans` field (validator rejects it).
4. Hit a name/coined term NOT in the snapshot? DO NOT invent one — list it in `unknown_terms`.
   The driver treats that as a hard failure to fix in the terminology pass, never an ad-hoc coin.

## 6b. Preambles & Image Captions (added 2026-09, HTML-era schema)

Beyond verses, two more fields are translatable and appear in the reader:

- **`preamble`** — a chapter epigraph (e.g. *"WHEREIN IS REVEALED THE THREE GREAT WORLDS…"*).
  Stored as an i18n object `{en, zh_hant, zh_hans, ja}` on the chapter. 119 chapters have one.
  Translate `preamble.en` into all 3 languages at the same register as verses. Reuse locked
  transliterations (Corpor→柯珀, etc.); the reader auto-annotates coined terms if the chapter's
  verses list them in `glossary_terms`.
- **Image `caption`** — plate names (e.g. *"Jehovih Speaks"*, *"Divine Seal"*). Also an i18n object
  on each `verse.images[]` entry. Translate `caption.en`; names transliterate per §2 (e.g.
  "Jehovih Speaks" → 耶霍維言說 / ジェホヴィ語りたもう).
- **Do NOT touch `preamble_source`** — that provenance tag (`word-1882` | `sacred-texts`) is set by
  the source pipeline, not the translator.
- **Never overwrite** a non-null preamble/caption translation; fill only where the target language is null.

---

## 7. Output Contract (what the agent returns)

A single JSON object:
```json
{
  "chapter_id": "jehovih.1",
  "preamble": { "zh_hant": "...", "zh_hans": "...", "ja": "..." },
  "captions": [ { "verse_id": "jehovih.1.1", "en": "<echo the English caption>", "zh_hant": "...", "zh_hans": "...", "ja": "..." } ],
  "verses": [
    { "id": "jehovih.1.1", "zh_hant": "...", "zh_hans": "...", "ja": "...", "glossary_terms": ["Jehovih"] }
  ],
  "fill_glossary": [ { "slug": "jehovih", "translit": {...}, "source_def_literal": {...}, "editor_note": {...} } ],
  "new_glossary": [ { ...full terms.json entry for a newly coined term... } ],
  "new_lexicon":  [ { ...style-lexicon.json entry... } ],
  "conflict_notes": []
}
```
- `verses` MUST cover every input verse, same ids, same order.
- Strings are clean (no baked parenthetical).
- Return ONLY the JSON object, no markdown fences, no commentary.
