# Oahspe 1882 Word-HTML — Structural Analysis

**Source**: `sources/1882-word-html/OAHSPE-1882-Edition.html`
**Encoding**: Windows-1252 (Word 12 export)
**Images**: 233 files in `sources/1882-word-html/` (imageNNN.jpg/gif/png)
**Analysis date**: 2026-09-19

---

## 1. Document Shape

The HTML is **flat**: no `<h1>`–`<h6>` heading hierarchy. All structure is encoded via:

| Element | Count | Purpose |
|---------|-------|---------|
| `<p>` | 15,227 | Verse paragraphs, preamble text, headings as text |
| `<span>` | 22,635 | Word-generated style spans (small-caps, bold) |
| `<a name="…">` | 762 | ALL structure: book titles, chapter markers, plates, cross-refs |
| `<img>` | 119 | Inline images referenced from `_files/imageNNN.*` |
| `<table>` | 1 | 18-cell table within Book of Saphah |
| `<h2>` | 1 | One stray heading |

**Text extraction rule**: `p.get_text()` (no separator argument) then `re.sub(r'\s+', ' ', t).strip()`.
Word splits small-caps across `<span>` boundaries; the default BeautifulSoup concatenation correctly reconstructs them (e.g. `A</span>LL<span>` → `"ALL"`).

---

## 2. Anchor Taxonomy (762 total)

### 2.1 Chapter anchors — prefix+number (all schemes)

| Prefix | Slug | HTML chapters | books.json | Notes |
|--------|------|:---:|:---:|-------|
| `bj` | `jehovih` | 8 | 8 | ✓ |
| `seth` | `sethantes` | 23 | 23 | ✓ |
| `fbfl` | `first-lords` | 4 | 4 | ✓ |
| `ahshong` | `ahshong` | 9 | 9 | ✓ |
| `sbl` | `second-lords` | 2 | 2 | ✓ (books.json had 3 — CORRECTED) |
| `synopsis` | `synopsis` | 3 | 3 | ✓ |
| `aph` | `aph` | 17 | 17 | ✓ |
| `lfb` | `lords-first` | 3 | 3 | ✓ |
| `sue` | `sue` | 7 | 7 | ✓ |
| `lsb` | `lords-second` | 3 | 3 | ✓ |
| `apollo` | `apollo` | 15 | 15 | ✓ |
| `ltb` | `lords-third` | 3 | 3 | ✓ |
| `thor` | `thor` | 6 | 6 | ✓ |
| `l4thb` | `lords-fourth` | 4 | 4 | ✓ — prefix contains a digit |
| `osiris` | `osiris` | 13 | 13 | ✓ |
| `LFthB` | `lords-fifth` | 7 | 7 | ✓ — mixed-case prefix |
| `fragapatti` | `fragapatti` | 43 | 43 | ✓ |
| `BGW` | `gods-word` | 30 | 30 | ✓ — all-caps prefix |
| `bkdivinity` | `divinity` | 18 | 18 | ✓ — `bk`-prefixed chapter scheme |
| `cpentarmig` | `cpenta-armij` | 13 | 13 | ✓ |
| `firstbkgod` | `gods-first` | 28 | 28 | ✓ |
| `bkwars` | `wars` | 55 | 55 | ✓ — `bk`-prefixed chapter scheme |
| `lika` | `lika` | 26 | 26 | ✓ |
| `arcofbon` | `arc-of-bon` | 31 | 31 | ✓ |
| `godsbkben` | `gods-ben` | 10 | 10 | ✓ |
| `cosmogony` | `cosmology` | 11 | 11 | ✓ |
| `eskra` | `eskra` | 60 | 60 | ✓ |
| `es_` | `es` | 21 | 21 | ✓ — underscore scheme |
| `judgement_` | `judgement` | 39 | 39 | ✓ — underscore scheme |
| `inspiration` | `inspiration` | 18 | 18 | ✓ |
| `shalem` | `jehovih-kingdom` | 26 | 26 | ✓ |

**Matching regex**: `re.match(r'^(.+?)(\d+)$', name)` — prefix is everything before the trailing digit run; handles `l4thb1`, `LFthB7`, `BGW30` correctly.

### 2.2 Book-title anchors (bare, no trailing digit)

These mark the start of each book (title page). The chapter anchors for the same book follow immediately.

```
bkjehovih       sethantes       firstbookfirstlords  ahshong        secondbklords
synopsis        aph             lordsfirstbk         sue            lordssecondbk
apollo          lordfthirdbk    thor                 lordsforthbk   osiris
lordsfifthbk    fragapatti      bkgodsword           bkdivinity     cpentarmig
firstbkgod      bkwars          lika                 arcofbon       godsbkben
cosmogony       eskra           bkofes               judgement      inspiration
jkoe            saphah          bonsbkpraise
```

**Note**: Several prefixes share their name with the bare book-title anchor (e.g. `synopsis`, `aph`, `thor`) — the bare form (no digit) is the book title; the `prefix+N` forms are chapters.

**`jkoe`**: book-title anchor for `jehovih-kingdom`; chapter anchors use the `shalem` prefix (not `jkoe`).

### 2.3 Section-based books (named sections, not numbered chapters)

| Prefix | Slug | Section count |
|--------|------|:---:|
| `saphah_` | `saphah` | 31 |
| `bon_` | `bons-praise` | 41 |

Each named anchor (`saphah_PANIC`, `bon_ESK`, etc.) is one section. Sections with at least one verse are assigned sequential chapter numbers 1…N. The `semoim_tablet` and `tablet_empagatu` anchors appear within the saphah region but are skipped (non-content markers).

### 2.4 Plate anchors (89 total, prefix `plate_`)

89 named anchors with the `plate_` prefix mark illustration plates. 87 are directly followed by one or more `<img>` tags. Caption derived by stripping `plate_` and replacing `_` with spaces, then title-casing lowercase words. Examples:

| Anchor | Caption |
|--------|---------|
| `plate_jehovih_speaks` | Jehovih Speaks |
| `plate_divine_seal` | Divine Seal |
| `plate_cevorkum` | C'evorkum |
| `plate_HYARTI_NEBULA` | Hyarti Nebula |
| `plate_Bridge_Of_Chinvat` | Bridge of Chinvat |
| `plate_nine_entities` | Nine Entities |

### 2.5 Gallery anchors

Special anchors that introduce a standalone plate gallery (not part of any numbered chapter):

| Anchor | Position | Images | Correct target |
|--------|----------|--------|---------------|
| `godsbkbenpics` | After `godsbkben10` (last gods-ben chapter) | 26 (image076–image126) | Gods-ben ch10 last verse |
| `cosmogony_plates` | Between `cosmogony` book-title and `cosmogony1` | 16 (image128–image158, plus `plate_` anchors) | Cosmology ch1 verse 1 (frontispiece) |

### 2.6 Other anchors (non-chapter, non-plate)

```
index           plates_index    oahspe          voiceofman
symbol          aries           cosmogony_plates godsbkbenpics
Judgement_symbol shalem (bare, mid-sequence duplicate)
```

`shalem` appears a second time between `shalem4` and `shalem5` — it is a duplicate cross-reference target and does not affect chapter numbering.

---

## 3. Books Absent from the HTML

| Slug | Title |
|------|-------|
| `discipline` | Book of Discipline |
| `general-statement` | A General Statement … |
| `prophets` | List of the Principal Prophets … |
| `hints` | Hints to the Reader |
| `oahspe-intro` | Oahspe |
| `voice-of-man` | The Voice of Man |

The last five are front-matter books that exist in the corpus with completed translations (zh_hant/zh_hans/ja). `discipline` is simply absent from this edition.

---

## 4. Image Placement Model

### 4.1 The 119 HTML `<img>` elements

All images referenced via `<img src="…_files/imageNNN.*">`. Copied to `site/static/plates/edition1882/`.

### 4.2 Frontispiece pattern

```
<a name="bk<book>">    ← book-title anchor
<p>BOOK OF X.</p>
<a name="plate_…">     ← plate anchor (caption seed)
<img src="…imageNNN">  ← FRONTISPIECE image
<a name="<prefix>1">   ← chapter 1 anchor
```

Frontispiece images (between book-title anchor and chapter-1 anchor, with no verse yet) attach to **chapter 1, verse 1** via the `pending_images` mechanism.

Books with confirmed frontispieces:

| Book slug | Frontispiece image | Caption |
|-----------|-------------------|---------|
| `jehovih` | image004.jpg | Jehovih Speaks |
| `divinity` | image042.jpg | Divine Seal |
| `cpenta-armij` | image044.jpg | Ocgokuk |
| `gods-ben` | image060–image074.jpg (9 imgs) | Nine Entities |

### 4.3 Inline images (within chapters)

Images that appear between chapter anchor N and chapter anchor N+1, after at least one verse, attach to the **last verse seen** before the image.

Key inline image placements:

| Image | Location | Caption |
|-------|----------|---------|
| image006.gif | jehovih.1.7 | (none — symbol) |
| image008.jpg | jehovih.5, last verse | Semuan Firmament |
| image010.jpg | jehovih.8, last verse | XSARJIS |
| image012.jpg | sethantes.19, after v17 | Hosts Descending |
| image026.jpg | aph.1, after v3 | Bridge of Chinvat |
| image030.jpg | osiris.13, after v3 | Aries |
| image050–054.jpg | wars.47, after respective verses | Osiris; Isis; Tablet of Osiris |
| image076–126.jpg (26) | gods-ben.10 last verse | Cyclic Coil … Sun and Earth |
| image160.jpg | cosmology.7, last verse | Orachnebuahgalah |
| image224.jpg | eskra.41, after v33 | Loiask |
| image226.jpg | es.19, after v18 | Arc of Kosmon |
| image228.jpg | judgement.15, after v9 | Grades |
| image230.jpg | judgement.16, last verse | Rates |
| image232.jpg | judgement.39, after v24 | Judgement Symbol |

### 4.4 Special cases

| Image | Target | Caption | Method |
|-------|--------|---------|--------|
| image002.jpg | oahspe-intro.1.1 | Oahspe — Title Page | Targeted merge (translated) |
| image004.jpg | jehovih.1.1 | Jehovih Speaks | Targeted merge (translated) |
| image006.gif | jehovih.1.7 | (none) | Targeted merge (translated) |
| image233.jpg | jehovih-kingdom.26 last verse | End of Oahspe | Normal write path |

### 4.5 Cosmology frontispiece gallery (cosmogony_plates region)

Images image128–image158 (16 images) appear between the `cosmogony` book-title anchor and `cosmogony1`. They include `plate_cevorkum_roadway_solar_phalanx`, `plate_1_2_3rd_resurrection`, `plate_mathematical_problems`, `plate_travels_solar_phalanx`, `plate_light_illustrated`, `plate_lens_illustrated`, `plate_planets`. All attach to **cosmology ch1 v1** as frontispiece.

---

## 5. Known Bugs in Original Parser (Fixed)

### Bug 1: gods-ben.10 pileup (42 images)

**Cause**: The `godsbkbenpics` anchor is not a chapter anchor, so after `godsbkben10`'s last verse the parser never advanced its chapter context. The 26 `godsbkbenpics` images + 16 `cosmogony_plates` images (image076–image158) all piled on the last verse of gods-ben ch10 verse 20.

**Fix**: `godsbkbenpics` is treated as a gallery anchor that flushes gods-ben and attributes its 26 images to gods-ben ch10 last verse. `cosmogony_plates` is also a gallery anchor whose images are pending for cosmology ch1 v1.

### Bug 2: cosmology.11 pileup (32 images)

**Cause**: After `cosmogony11`, the chapter cursor stayed at `cosmology.11`. The `saphah_` section anchors don't fire `flush_chapter`, so all 32 saphah section images (image162–image222) piled onto the last verse of cosmology ch11.

**Fix**: The `saphah` book-title anchor now flushes the standard parser and disables it (`cur_slug = None`). Saphah images are handled entirely by the section parser.

### Bug 3: Jehovih frontispiece missing

**Cause**: `image004.jpg` appears in the region between `bkjehovih` (book-title anchor) and `bj1` (chapter-1 anchor). The parser required `cur_chap > 0` to accumulate images, so the frontispiece was dropped.

**Fix**: Images are accumulated into `pending_images` whenever `cur_slug` is set, even when `cur_chap=0` (frontispiece zone). `flush_chapter` preserves `pending_images` when there is no real chapter to flush.

---

## 6. Chapter JSON Schema

```json
{
  "id":       "<slug>.<chapter>",
  "book":     "<slug>",
  "chapter":  <int>,
  "title":    "<Book Title> — Chapter <N>",
  "preamble": "<text | empty string>",
  "verses": [
    {
      "id":             "<slug>.<chapter>.<verse>",
      "verse_number":   <int>,
      "en":             "<text>",
      "zh_hant":        null,
      "zh_hans":        null,
      "ja":             null,
      "glossary_terms": [],
      "plate_ref":      null,
      "images": [
        {
          "src":     "/plates/edition1882/imageNNN.jpg",
          "edition": "1882",
          "caption": "<Caption string>"   ← omitted when null
        }
      ],
      "notes": []
    }
  ]
}
```

The `images` array is **omitted entirely** when empty (not written as `[]`).
The `caption` field is **omitted** when null (no plate anchor preceded the image).

---

## 7. Verse Recognition

A `<p>` is a verse paragraph if its collapsed text matches:

```
^(\d+)\.\s+(.*)
```

The number is the `verse_number`; the rest is the English text.
Non-verse paragraphs before the first verse of a chapter accumulate as `preamble`.
`CHAPTER N.` heading paragraphs are excluded from the preamble.

---

## 8. Image Filename Reference

All 119 `<img>` tags in the HTML reference files of the form `imageNNN.{jpg,gif,png}`.
Source directory: `sources/1882-word-html/`.
Destination: `site/static/plates/edition1882/`.

The 233 files in the source directory include many unreferenced Word export artefacts.
Only the 119 that appear in `<img src="…">` tags are copied and referenced in JSON.
