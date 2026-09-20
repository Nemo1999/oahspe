# Body Translation — Resumption State

> Updated 2026-09-20. Workflow is now **terminology-first, parallel-per-book** (see
> `docs/TRANSLATION_GUIDE.md §0`). Engine: `scripts/translate_book.py`.

## Done (8 books, ~835 verses)
general-statement, prophets, hints, oahspe-intro, voice-of-man, jehovih (8ch),
**sethantes (23ch)**, **first-lords (4ch)** — the last two via the new parallel workflow.
Glossary: 189 terms (grows monotonically as books complete).

## Pending — 30 books, ~12,877 verses, canonical `books.json` order
Next: ahshong (9ch) → second-lords → synopsis → aph → lords-first → sue → … → jehovih-kingdom.

## How to resume (per book, one book at a time)
The driver lives in the eval kernel (not the repo) — rebuild it from the functions described
in `TRANSLATION_GUIDE.md §0` calling into `scripts/translate_book.py`:
`build_manifest` → `run terminology agent` (`build_terminology_prompt`) → review via
`completion(build_terminology_review_prompt, model="slow", schema)` cycling on MAJOR →
`publish_snapshot` → **parallel** chapters (`build_chapter_prompt`, bounded waves) each:
translate → `validate_chapter_result` + independent `completion` review → revise on MAJOR →
`merge_chapter` (self-validates + CAS, fill-only) → `commit_snapshot_to_global` (once, flock) →
validate.py → json-to-mdx.py → commit+push.

## Hard-won lessons (baked into the harness/SOP — don't relearn)
- **Terminology BEFORE verses.** Only the terminology pass coins/fills; chapter workers are
  snapshot-only. This is what makes parallel safe.
- **`source_forms` are mandatory** and WHOLE-TOKEN matched (never substring/stem): the `Ben`→`本`
  trap. Include plural/possessive/spelling variants (`Wagga`/`Waga`, `Jah`→`Ha'jah`).
- **Kana in a Chinese field is a hard error** — workers sometimes dump ja text into `zh_hant`.
  The validator + reviewer both catch it.
- **Snapshot is immutable + version-hashed.** If you must change it mid-run (e.g. add an alias),
  results bound to the old version fail revalidation. If ONLY `source_forms` changed (no translit),
  it's safe to rebind passed results to the new version; otherwise re-translate.
- **Merge is fill-only + CAS** over verses+preamble+captions; captions keyed by stable
  `cap_idx` (`verse_id#img_index`), never by caption English (duplicates exist, e.g. gods-ben v1).
- **Global commit**: translit conflict with an existing non-null value = hard stop; prose
  (`editor_note`/`source_def_literal`) and already-locked translits = existing wins silently.
- **Agents overreach**: chapter/terminology workers must ONLY write their result file — never
  git/validate/build. The driver owns validate+commit+deploy.
- **Data hygiene done**: normalized `Lord` (was `Lord / Lords`), `es'enaur`/`c'vorkum`/`Jah`
  aliases, `su'is`/`Lord` translit (眾 not the Japanese 衆 for zh).
