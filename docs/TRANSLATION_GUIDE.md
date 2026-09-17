# Oahspe Translation Guideline & Rules

> Status: Locked via grilling session, 2026-09-17
> Languages: `zh_hant` (Traditional Chinese), `zh_hans` (Simplified Chinese), `ja` (Japanese)
> This document is the **verbatim instruction** given to every per-chapter translation subagent.
> Companion: `docs/DESIGN.md` (site architecture), `content/style-lexicon.json` (internal), `content/glossary/terms.json` (reader-facing).

---

## 0. Execution Model (how translation runs)

- **One chapter = one subagent. Strictly sequential, ONE agent at a time, from chapter 1 to the end. NEVER parallel.** This is the consistency guarantee: no two agents may coin dictionary entries at the same time.
- Each agent receives, as read-only context: this guideline, the **current** `terms.json`, the **current** `style-lexicon.json`, and the chapter's English verses.
- Each agent returns: (a) the translated verses in all 3 languages, (b) the per-verse `glossary_terms` list, (c) any **new** dictionary proposals (glossary + style-lexicon).
- The orchestrator merges proposals, validates, commits+pushes+deploys that chapter, THEN spawns the next agent so it sees the updated dictionary.
- **Checkpoint:** after **chapter 1** the run PAUSES for human approval/edit of the seed dictionary. After approval, chapters 2..N auto-run.

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

## 3. The (English) Parenthetical — DATA ONLY, not baked text

- Coined/transliterated terms (names + Oahspe-specific coined words like `Corpor`, `Es`, `Ethe`, `I'hin`, `Se'muan`) are shown to the reader as `譯名（English）` on **first occurrence per chapter**, rendered by `VerseReader` from `terms.json`.
- **Your job:** store the clean translation, and list the canonical English headword in that verse's `glossary_terms`. **Do NOT** write the parenthesis yourself, and do NOT apply first-occurrence logic — the component does that.
- Ordinary translated vocabulary gets **no** parenthetical (handled by dictionary consistency + glossary tooltip).

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

## 6. Consistency Protocol (per agent)

1. Read `terms.json` + `style-lexicon.json` fully before translating.
2. For every verse: translate into all 3 languages honoring **every** locked entry verbatim.
3. Populate `glossary_terms` with the canonical English headwords present in the verse.
4. Collect **new** proposals (terms + lexicon) with full entry data.
5. Return verses + proposals. Do NOT edit existing entries; if you believe one is wrong, add a `conflict_note` in your output — the orchestrator surfaces it, but the locked value stands unless a human changes it.

---

## 7. Output Contract (what the agent returns)

A single JSON object:
```json
{
  "chapter_id": "jehovih.1",
  "verses": [
    { "id": "jehovih.1.1", "zh_hant": "...", "zh_hans": "...", "ja": "...", "glossary_terms": ["Jehovih"] }
  ],
  "new_glossary": [ { ...terms.json entry... } ],
  "new_lexicon":  [ { ...style-lexicon.json entry... } ],
  "conflict_notes": []
}
```
- `verses` MUST cover every input verse, same ids, same order.
- Strings are clean (no baked parenthetical).
- Return ONLY the JSON object, no markdown fences, no commentary.
