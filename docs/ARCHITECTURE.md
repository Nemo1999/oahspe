# Oahspe Project Architecture

> The single reference for how source material becomes the deployed multilingual reader.
> Companions: `docs/TRANSLATION_GUIDE.md` (translation SOP), `sources/1882-word-html/STRUCTURE.md`
> (HTML source schema + dual-source merge), `docs/DESIGN.md` (product/site design).

---

## 1. Pipeline — three stages, JSON is the source of truth

```
  SOURCES                         JSON (source of truth)                 PUBLISH
 ┌──────────────────┐           ┌────────────────────────────┐        ┌─────────────┐
 │ 1882 Word-HTML   │──parse──▶ │ content/books/<slug>/       │        │ Docusaurus  │
 │  (+233 images)   │  (base)   │   chapter-NN.json           │──gen──▶│  MDX pages  │──build──▶ GitHub Pages
 │                  │           │ content/glossary/terms.json │  MDX   │             │
 │ Sacred Texts     │──merge──▶ │ content/style-lexicon.json  │        └─────────────┘
 │  (epigraph/front │ (overlay) │ content/meta/*.json         │
 │   matter overlay)│           └────────────────────────────┘
 └──────────────────┘                    ▲
        translation orchestrator ─────────┘ (writes zh_hant/zh_hans/ja into the SAME JSON)
```

**Invariant: the JSON under `content/` is the single source of truth.** Everything downstream
(MDX, HTML, site) is regenerable from it. Translations live ONLY in the JSON (never in MDX/HTML).
Two inputs converge on the JSON — the source parsers (English + images) and the translation
orchestrator (translations) — so every write path MUST preserve the other's data.

### Stage 1 — Sources → JSON
- **`scripts/html-to-json.py`** (BASE): parses `sources/1882-word-html/OAHSPE-1882-Edition.html`
  into `content/books/<slug>/chapter-NN.json` — verse text (`en`), images with captions, and
  preambles the Word edition contains. See `sources/1882-word-html/STRUCTURE.md` for the full
  anchor/plate/caption schema. Copies referenced images into `site/static/plates/edition1882/`.
- **`scripts/merge-sacred-texts.py`** (OVERLAY): fills chapter `preamble.en` from the Sacred Texts
  edition where the Word edition lacks an epigraph, tagging `preamble_source`. Precedence:
  `word-1882` > `sacred-texts` > none. NEVER overwrites translations. (Dual-source rationale +
  precedence documented in STRUCTURE.md.)
- **`scripts/scrape-sacred-texts.py`**: the Sacred Texts scraper (cache-first from
  `scripts/.htmlcache/`, browser-prefetched past Cloudflare). Source of the `.htmlcache` the merge reads.
- **Provenance**: chapters carry `preamble_source` (`word-1882` | `sacred-texts` | null) so no
  field's origin is silent/lucky.

### Stage 2 — JSON → MDX
- **`scripts/json-to-mdx.py`**: emits `site/docs/**/*.mdx`. One page per chapter (multi-chapter
  books) or one standalone page (single-chapter books / front matter). Injects the per-chapter
  glossary slice used for the parenthetical + glossary links. Orders books by `books.json` via
  `sidebar_position`.

### Stage 3 — MDX → site
- **Docusaurus v3** build → 4 locales (`en`, `zh-hant`, `zh-hans`, `ja`) → GitHub Pages.
- `VerseReader.tsx` renders verses, preamble, images/captions, the coined-term parenthetical
  (every occurrence, linked to `/glossary#slug`), language toggle, parallel mode.
- `src/pages/glossary.tsx` renders the glossary per-locale with source/editor separation,
  expand/collapse, in-page language switch, and backlinks to verse anchors (`appears_in`).

---

## 2. Content JSON schema (authoritative)

### Chapter (`content/books/<slug>/chapter-NN.json`)
```json
{
  "id": "<slug>.<chapter>",
  "book": "<slug>",
  "chapter": <int>,
  "title": "<Book Title> — Chapter <n>",
  "preamble": { "en": "…|null", "zh_hant": null, "zh_hans": null, "ja": null },
  "preamble_source": "word-1882 | sacred-texts | null",
  "verses": [ <verse>… ]
}
```

### Verse
```json
{
  "id": "<slug>.<ch>.<v>", "verse_number": <int>,
  "en": "…", "zh_hant": null, "zh_hans": null, "ja": null,
  "glossary_terms": ["Jehovih", …],          // canonical English headwords present in the verse
  "plate_ref": null,                          // legacy Sacred-Texts plate id (unused by 1882 images)
  "images": [                                  // 1882-edition images at this verse (optional)
    { "src": "/plates/edition1882/imageNNN.jpg", "edition": "1882",
      "caption": { "en": "…", "zh_hant": null, "zh_hans": null, "ja": null } }
  ],
  "notes": []
}
```

### Glossary term (`content/glossary/terms.json`) — reader-facing
```json
{ "term": "Jehovih", "slug": "jehovih", "category": "name|term",
  "translit": {"zh_hant":"…","zh_hans":"…","ja":"…"},
  "source_def": "…book's own glossary, verbatim|null",
  "source_def_literal": {"zh_hant":"…","zh_hans":"…","ja":"…"},   // faithful literal translation
  "editor_note": {"en":"…","zh_hant":"…","zh_hans":"…","ja":"…"}, // editor interpretation, per-language
  "appears_in": ["<verse id>…"],              // backlinks (built from verse.glossary_terms)
  "cross_refs": ["…slug…"], "locked": true, "first_seen": "<verse id>" }
```

### Style-lexicon (`content/style-lexicon.json`) — internal consistency, not reader-facing
`{ "en", "category": "verb|phrase", "zh_hant", "zh_hans", "ja", "note", "locked", "first_seen" }`

**i18n text objects**: `preamble` and image `caption` are `{en, zh_hant, zh_hans, ja}`. English is
the base; translations start null and fill via the orchestrator. Legacy bare strings are tolerated
by the reader but should be migrated.

---

## 3. Translatable surface (what the orchestrator must fill)
| Field | Where | Parenthetical / glossary link? |
|---|---|---|
| verse `en` → zh_hant/zh_hans/ja | every verse | yes (coined terms) |
| `preamble.en` → 3 langs | 165 chapters w/ epigraph (119 word-1882 + 46 sacred-texts) | yes |
| image `caption.en` → 3 langs | 116 captioned images | yes |
| glossary `translit` / `editor_note` / `source_def_literal` | terms.json | n/a (is the glossary) |

Coverage is reported by `scripts/validate.py` (`=== Translation coverage ===`).

---

## 4. Regeneration & safety rules
- **Re-running a source parser MUST preserve translations.** `html-to-json.py` skips books with
  non-null `zh_hant`; `merge-sacred-texts.py` only fills empty `preamble.en`. Never blank a
  translated field.
- **Regenerate MDX after any JSON change**: `python3 scripts/json-to-mdx.py`.
- **Validate before commit**: `python3 scripts/validate.py` (schema + image-file existence +
  i18n-shape + coverage report). Must print `All files valid.`
- **Deploy** is push→GitHub Actions→Pages; the Actions build runs validate + json-to-mdx + build.

---

## 5. Commands
```
python3 scripts/scrape-sacred-texts.py     # (re)build Sacred Texts cache (browser-prefetch first)
python3 scripts/html-to-json.py            # Word HTML → JSON (base)
python3 scripts/merge-sacred-texts.py      # Sacred Texts epigraph/front-matter overlay
python3 scripts/validate.py                # schema + health report
python3 scripts/json-to-mdx.py             # JSON → MDX
cd site && npx docusaurus build            # MDX → static site
# translation: driven by translate_orchestrator.py (see docs/TRANSLATION_GUIDE.md)
```
