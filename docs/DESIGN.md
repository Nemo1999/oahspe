# Oahspe Reader — Design Document
> Status: Decisions confirmed via grilling session, 2026-09-17  
> Owner: Nemo1999 (tiny.nemo.fish@gmail.com)  
> Host: GitHub Pages — `nemo1999.github.io/<repo>`

---

## 1. Goals

A multilingual, mobile-first, offline-capable reader for the Oahspe Bible (1882, public domain) with:

- Sentence/verse-by-sentence display in 4 languages
- Rich glossary with bidirectional hyperlinks
- Original illustration plates
- Full-text search (offline-capable)
- PWA install on iPhone and Android
- Personal annotation and blog layer (author-only, static)
- Reader bookmarks/notes (localStorage, no login)
- Sharable permanent links per verse, chapter, glossary term, note

---

## 2. Content Scale

| Metric | Value |
|---|---|
| Words (English) | ~632,000 |
| Characters | ~3.5M |
| Pages | 2,117 |
| Verses | ~13,900 |
| Avg words/verse | ~47.5 |
| Estimated chapters | ~500 |
| Glossary candidate terms | ~539 |
| Original illustration plates | 97 (Sacred Texts manifest) |

---

## 3. Content Sources (Hybrid)

### 3a. Canonical Text
**Source:** Sacred Texts archived HTML  
`https://archive.sacred-texts.com/oah/oah/index.htm`

- Clean, hand-structured HTML
- Conformed to 1912 third edition
- 659 navigable chapters, stable URLs
- Programmatically extractable DOM
- Plate manifest at `oah04.htm` (plates 1–97 indexed with page mapping)
- Public domain

### 3b. Image Masters (High-Resolution)
**Source:** Internet Archive — *The Words of Jehovih* (1942)  
`https://archive.org/details/thewordsofjehovih`

- 600 ppi full-page scan, 930 pages
- PDM 1.0 (explicit public domain)
- 722.9 MB image PDF; 1.117 GB JP2 ZIP for extraction
- Use Sacred Texts' 97-plate manifest to map plates → IA page numbers

### 3c. 1882 Original Fallback
**Source:** IA Berserker upload  
`https://archive.org/details/oahspe-a-new-bible-in-the-words-of-jehovih-1882-edition-john-newbrough-berserker-books`

- PDM 1.0, 1,135 pages, 514.8 MB JP2
- Cross-validate plate completeness against Sacred Texts' 97-plate list before use

### 3d. Sources to Avoid
| Source | Reason |
|---|---|
| IA `oahspe0001john` | Only Vol 1 of 7 (Forgotten Books reprint) |
| Oahspe Standard Edition | Modernized/rewritten text; no reuse license on restored images |
| GlobalGrey PDF | Only 2 images (already downloaded as backup text) |
| IA restricted 1942/1955/1960 scans | Not freely downloadable |

---

## 4. Content Data Model

### 4a. Format
**JSON per chapter** — engine-agnostic, verse-level granularity, git-diffable.

### 4b. Verse Schema
```json
{
  "id": "jehovih.1.3",
  "en": "...",
  "zh_hant": "...",
  "zh_hans": "...",
  "ja": "...",
  "glossary_terms": ["Jehovih", "Corpor"],
  "image_ref": null,
  "notes": []
}
```

### 4c. Chapter Schema
```json
{
  "book": "jehovih",
  "chapter": 1,
  "title": "Book of Jehovih — Chapter 1",
  "preamble": "...",
  "verses": [ ...verse objects... ]
}
```

### 4d. ID Scheme
**Hierarchical dotted slugs:** `{book-slug}.{chapter}.{verse}`

Examples:
- `jehovih.1.3` → Book of Jehovih, Ch.1, v.3
- `sethantes.14.7` → Book of Sethantes, Ch.14, v.7
- `saphah.semoin.12` → Book of Saphah, Se'moin section, entry 12

Maps directly to:
- Filesystem: `content/books/jehovih/chapter-01.json`
- URL: `/en/jehovih/1#v3`
- Sharable link: `nemo1999.github.io/oahspe/en/jehovih/1#v3`

### 4e. Glossary Schema
```json
{
  "term": "Jehovih",
  "slug": "jehovih",
  "en": "The Creator; the All Person; the Ever Present...",
  "zh_hant": "...",
  "zh_hans": "...",
  "ja": "...",
  "appears_in": ["jehovih.1.1", "jehovih.1.7", ...],
  "cross_refs": ["ethe", "corpor", "atmospherea"],
  "notes": []
}
```

---

## 5. Repo Structure

**Single monorepo** — content, site, and pipeline scripts together.

```
oahspe/
├── content/
│   ├── books/
│   │   ├── jehovih/
│   │   │   ├── chapter-01.json
│   │   │   └── ...
│   │   ├── sethantes/
│   │   └── ... (~30 books)
│   ├── glossary/
│   │   └── terms.json
│   └── meta/
│       ├── books.json          # book slug → title, chapter count
│       └── plates.json         # plate manifest (97 entries)
├── static/
│   ├── plates/
│   │   ├── thumbs/             # low-res (~80px wide, ~5-10 MB total)
│   │   └── full/               # high-res (Git LFS, ~80-100 MB)
│   └── icons/                  # PWA icons
├── scripts/
│   ├── scrape-sacred-texts.py  # fetch + parse HTML → raw JSON
│   ├── extract-plates.py       # download + resize IA images
│   ├── translate.py            # LLM translation pipeline
│   ├── build-glossary.py       # index terms → bidirectional links
│   └── validate.py             # schema validation
├── blog/                       # author personal notes (Markdown)
│   └── 2026-09-17-welcome.md
├── site/                       # Docusaurus config + custom components
│   ├── docusaurus.config.ts
│   ├── src/
│   │   ├── components/
│   │   │   ├── VerseReader.tsx     # 4-lang parallel display
│   │   │   ├── GlossaryTooltip.tsx # inline term hover/click
│   │   │   ├── ImagePlate.tsx      # thumb → full-res on demand
│   │   │   └── BookmarkBar.tsx     # localStorage bookmarks
│   │   └── theme/
│   └── static/
├── .github/
│   └── workflows/
│       ├── build-deploy.yml    # push → build → gh-pages
│       └── translate.yml       # manual trigger → run translate.py
└── .gitattributes              # Git LFS for full-res plates
```

### Repo Size Estimate
| Component | Size |
|---|---|
| JSON content (all 4 languages) | ~44 MB |
| Plate thumbnails (97 × ~50KB) | ~5 MB |
| Full-res plates (Git LFS) | ~80-100 MB |
| Scripts + site config | ~2 MB |
| **Total (without LFS)** | **~51 MB** |
| **Total (with LFS)** | **~150 MB** |

---

## 6. Site Engine

**Docusaurus v3** (React)

| Feature | Implementation |
|---|---|
| i18n | Docusaurus built-in locale routing (`/en/`, `/zh-hant/`, `/zh-hans/`, `/ja/`) |
| Glossary + tooltips | `docusaurus-plugin-glossary` — auto-detects terms, inline tooltips, `/glossary` page, bidirectional links |
| PWA / offline | `@docusaurus/plugin-pwa` (official, Workbox-based) |
| Blog / author notes | Docusaurus built-in blog plugin |
| Search | Pagefind (primary, offline-capable, CJK-aware) + optional Algolia online layer |
| Deploy | GitHub Actions → `gh-pages` branch → `nemo1999.github.io/oahspe` |

---

## 7. PWA / Offline Strategy

**Text-first offline with low-res plate previews bundled.**

| Layer | Strategy | Cached size |
|---|---|---|
| All JSON content | Pre-cached at install | ~44 MB |
| Plate thumbnails (97 thumbs) | Pre-cached at install | ~5 MB |
| Full-res plates | On-demand cache (streamed, stored after first view) | ~80 MB (grows) |
| **Install footprint** | | **~50 MB** |

- Service worker via Workbox (Docusaurus plugin-pwa)
- "Download full plates" button for deliberate offline pre-fetch
- iOS 15.4+ storage limit no longer a blocker for ~50MB install

---

## 8. Translation Pipeline

### Model Strategy — Tiered

| Content | Model | Rationale |
|---|---|---|
| Glossary terms (539 entries) | Claude Sonnet | Dense theological vocabulary, archaic register, must be consistent |
| Book of Jehovih, Voice of Man, Book of Judgment (theologically dense) | Claude Sonnet | Sets the translation tone for the whole work |
| All remaining narrative chapters | Claude Haiku / GPT-4o-mini | Adequate for draft; author annotations can refine |
| Glossary cross-reference pass | Claude Sonnet | Term consistency check across all translations |

### Cost Estimate
| Pass | Tokens | Cost (est.) |
|---|---|---|
| JSON structuring (Sacred Texts HTML → schema) | ~2.4M | ~$5 |
| Sonnet translation (dense books + glossary, ~15% of content) | ~1.3M | ~$15 |
| Mini translation (remaining 85%) | ~7.2M | ~$7 |
| Glossary cross-reference pass | ~0.5M | ~$5 |
| **Total** | **~11.4M** | **~$30-40** |

### Pipeline Flow
```
1. scrape-sacred-texts.py   → raw chapter JSON (English only)
2. build-glossary.py        → terms.json (from glossary section)
3. translate.py             → add zh_hant, zh_hans, ja to each verse
4. build-glossary.py --link → add appears_in[] to each term
5. validate.py              → schema check, missing translations report
6. extract-plates.py        → fetch + resize 97 plates → thumbs/ + full/
7. Docusaurus build         → static site
8. GitHub Actions deploy    → gh-pages branch
```

---

## 9. Reader Features

### 9a. Verse Display
- 4-language toggle or side-by-side view (user preference, saved in localStorage)
- Each verse has permanent anchor (`#v3`)
- Share button → copy URL with verse anchor

### 9b. Glossary
- Inline terms auto-underlined with hover tooltip (English definition)
- Click → dedicated `/glossary/{term}` page with all 4 translations
- Glossary page shows `appears_in` → links back to every verse that uses it
- Bidirectional: verse page ↔ glossary page

### 9c. Images
- Plate thumbnails (low-res) shown inline at their canonical position
- Click → full-res loaded on demand, cached by service worker
- Alt text + caption in all 4 languages

### 9d. Search (Pagefind)
- Static index built at deploy time
- Searches all 4 languages independently (language toggle in search UI)
- Works fully offline
- Results link to verse anchors

### 9e. Author Annotations + Blog
- Markdown files in `blog/` directory
- Can reference specific verses (`jehovih.1.3`), chapters, or glossary terms
- Rendered by Docusaurus blog plugin
- Shown as a sidebar callout on the relevant verse/chapter page

### 9f. Reader Bookmarks (No Login)
- Stored in `localStorage` keyed by verse ID
- Bookmark list page at `/bookmarks`
- Export as JSON or share via URL-encoded hash

### 9g. Sharable Links
| Thing | URL pattern |
|---|---|
| Specific verse | `/en/jehovih/1#v3` |
| Chapter | `/en/jehovih/1` |
| Glossary term | `/en/glossary/jehovih` |
| Blog post | `/en/blog/2026-09-17-welcome` |
| Bookmark set | `/bookmarks#{"jehovih.1.3":true,...}` (URL-encoded) |

---

## 10. Build & Deploy

### GitHub Actions — `build-deploy.yml`
Trigger: push to `main`
1. Install Node + Python deps
2. Run `validate.py` (fail fast if JSON schema broken)
3. Run Docusaurus build (generates Pagefind index inline)
4. Deploy to `gh-pages` branch
5. GitHub Pages serves `nemo1999.github.io/oahspe`

### GitHub Actions — `translate.yml`
Trigger: manual dispatch (with `--book` and `--lang` params)
1. Run `translate.py` for specified book + language
2. Commit translated JSON back to `main`
3. Kicks off `build-deploy.yml`

---

## 11. Open Questions / Future

- **Comment system**: If multi-user annotations are ever needed, Giscus (GitHub Discussions-backed) is the zero-backend option — no database, no auth infrastructure.
- **Plate edition alignment**: 1912 text (Sacred Texts) vs 1942 plates (IA) — maintain explicit `edition_note` field per plate in `plates.json`.
- **Translation review workflow**: Mark each verse with `translation_status: draft | reviewed | approved`. Author can filter to review draft verses.
- **Audio**: Text-to-speech per verse is a natural extension once content is stable.
- **Custom domain**: Add when ready — one `CNAME` file in repo + DNS change.
