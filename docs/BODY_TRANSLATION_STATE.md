# Body Translation — Resumption State (2026-09-19)

Snapshot before the bulk body-translation run. Read this + `docs/TRANSLATION_GUIDE.md`
+ `docs/ARCHITECTURE.md` to resume.

## Done
- **Fully translated (275 verses, 3 langs)**: jehovih (8ch), general-statement, prophets,
  hints, oahspe-intro, voice-of-man.
- **Glossary**: 145 terms; 101 with translit+editor_note; **all 55 source_defs literally translated**.
- **Preambles**: 4 front-matter + jehovih ch1 translated. 160 preambles remain — they translate
  **with their chapters** (so terms coin in dictionary order).

## Pending body run — 32 books, ~13,437 verses, in canonical `books.json` order
Starting: **sethantes (23ch)** → first-lords → ahshong → second-lords → synopsis → aph → … →
discipline. (Full order in content/meta/books.json.)

## Process (STRICT — see TRANSLATION_GUIDE §0 + translate_orchestrator.py)
1. One chapter = one subagent, **sequential, never parallel** (dictionary consistency).
2. Per chapter: `build_prompt(book, ch)` → subagent writes result JSON to
   `content/books/.trans/ch<N>.json` → `parse_agent_json` → `verify_locked` (drift guard;
   retry with feedback if drift) → `merge_result` (writes verses + preamble + captions,
   existing-wins glossary lock, ja-leak sweep gated on glossary_terms).
3. Large chapters (>~18 verses): split into verse-range batches (vmin/vmax) to avoid write-truncation.
4. After each chapter: `validate.py` → `json-to-mdx.py` → commit+push+deploy (per-chapter).
5. Glossary grows monotonically: agents FILL nulls / COIN new; existing entries locked.

## Key rules that must hold
- Names sound-based, never existing deities (Jehovih=耶霍維/ジェホヴィ). Historical figures too (Moses≠摩西).
- ja uses katakana; never leak zh characters into ja (sweep catches tagged terms).
- Reuse locked translits verbatim; preamble/captions translated too (i18n objects).
- Preserve any existing translation; never overwrite non-null.
