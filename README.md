# Oahspe Digital Edition

A modern, multilingual, offline-capable reader for **Oahspe (1882)** — all 34 books, 627 chapters,
~14,900 verses, 119 illustrated plates, and a 145-term searchable glossary, translated into
Traditional Chinese, Simplified Chinese, and Japanese.

### 🌐 Live site: **https://nemo1999.github.io/oahspe**

- Book of Jehovih + all front matter: **https://nemo1999.github.io/oahspe/jehovih**
- Glossary: **https://nemo1999.github.io/oahspe/glossary**

---

## How this project was guided & created

This edition was built collaboratively, request by request. The tree below is the actual
development history — essentially the product spec as it emerged.

- **Foundation**
  - Download the Oahspe full text + images (public domain, 1882)
  - Create the GitHub repo (`Nemo1999/oahspe`), Docusaurus v3, GitHub Pages CI
  - Grill out design decisions → [`docs/DESIGN.md`](docs/DESIGN.md)
- **Translation system** (→ [`docs/TRANSLATION_GUIDE.md`](docs/TRANSLATION_GUIDE.md))
  - Grill out the translation SOP & rules
    - Names transliterated **by sound**, never mapped to an existing deity (Jehovih → 耶霍維 / ジェホヴィ, **not** 耶和華/エホバ)
    - Scriptural-register characters; katakana for Japanese
    - Show the original English in a parenthetical `譯名（English）`
  - Build a translation dictionary
    - Reader glossary (names + coined terms) → `content/glossary/terms.json`
    - Internal style-lexicon (verbs + recurring phrases) → `content/style-lexicon.json`
  - Translate one agent at a time, sequentially, to keep terminology consistent
    - Book of Jehovih (8 chapters) + a chapter-1 approval checkpoint
    - All 5 front-matter sections (General Statement, Prophets, Hints, Oahspe intro, Voice of Man)
- **Content completeness** (→ [`sources/1882-word-html/STRUCTURE.md`](sources/1882-word-html/STRUCTURE.md))
  - Ingest the official 1882 Word-HTML export + 233 images (from Google Drive / zip)
  - Parse the **complete** book from that HTML: 32 books, 627 chapters, ~14,900 verses
  - Attach images to exact positions via the HTML's named chapter/plate anchors (119 images, captioned)
    - Fix dropped frontispieces (image004 "Jehovih Speaks", title page, colophon)
    - Verify **every** HTML-referenced image is referenced by our data (119 = 119)
  - Preambles / chapter epigraphs
    - Render the chapter epigraph ("WHEREIN IS REVEALED THE THREE GREAT WORLDS…")
    - **Dual-source merge**: Word-HTML base + Sacred Texts epigraph overlay, with `preamble_source` provenance
- **Reader experience**
  - 4-language toggle + parallel (side-by-side) mode; verse permalinks, bookmarks
  - Coined terms → parenthetical on **every** occurrence, hyperlinked to the glossary (hover underline, no color change)
  - Glossary page: per-locale display, in-page language switch, source-text vs editor-note separation, expand/collapse for long entries, **backlinks** to every verse that mentions a term
  - Front matter ordered before Book of Jehovih; single-chapter sections collapse to one page
  - Untranslated chapters show a clear "showing original English" notice
- **Identity & polish**
  - Logo / favicon / PWA icons from the authentic Oahspe frontispiece emblem (light + dark variants)
- **Governance**
  - Architecture reference → [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
  - Validation health-checks + translation-coverage report (`scripts/validate.py`)
  - Independent review of the SOP & merge standards

---

## Architecture (3-stage pipeline)

`SOURCE (1882 Word-HTML + Sacred Texts overlay + images) → JSON (content/**, source of truth) → Docusaurus (MDX → static site)`

The JSON under `content/` is the **single source of truth** — translations live there; everything
downstream is regenerated from it. Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quick Start

```bash
git clone https://github.com/Nemo1999/oahspe.git
cd oahspe
pip install -r requirements.txt      # Python 3.10+ (parsers, validation)
python3 scripts/html-to-json.py      # 1882 Word-HTML → content JSON (base)
python3 scripts/merge-sacred-texts.py# Sacred Texts epigraph overlay
python3 scripts/validate.py          # schema + coverage health report
python3 scripts/json-to-mdx.py       # JSON → site/docs MDX
cd site && npm install && npx docusaurus build   # build the static site
```

## Scripts

| Command | Description |
|---|---|
| `python3 scripts/html-to-json.py` | Parse the 1882 Word-HTML → `content/books/**` (English + images) |
| `python3 scripts/merge-sacred-texts.py` | Overlay Sacred Texts chapter epigraphs onto preambles |
| `python3 scripts/scrape-sacred-texts.py` | (Re)build the Sacred Texts HTML cache (browser-prefetch) |
| `python3 scripts/validate.py` | Validate JSON schema + image files + translation-coverage report |
| `python3 scripts/json-to-mdx.py` | Generate Docusaurus MDX from the content JSON |
| `npm --prefix site run build` | Build the Docusaurus site |

Translation is driven by `scripts/translate_orchestrator.py` per [`docs/TRANSLATION_GUIDE.md`](docs/TRANSLATION_GUIDE.md).

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — pipeline, JSON schema, regeneration rules
- [`docs/TRANSLATION_GUIDE.md`](docs/TRANSLATION_GUIDE.md) — translation SOP & rules
- [`docs/DESIGN.md`](docs/DESIGN.md) — product/site design decisions
- [`sources/1882-word-html/STRUCTURE.md`](sources/1882-word-html/STRUCTURE.md) — source HTML schema + dual-source merge

## License

Oahspe (1882) text and plates are public domain. Site code and tooling are MIT.
