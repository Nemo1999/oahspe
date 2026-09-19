import React, { useEffect, useState, useCallback } from 'react';
import { useLocation } from '@docusaurus/router';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import ImagePlate from './ImagePlate';

// ---- types ------------------------------------------------------------------

export interface VerseData {
  id: string;               // e.g. "jehovih.1.3" (book-slug.chapter.verse)
  verse_number: number;
  en: string;
  zh_hant?: string | null;
  zh_hans?: string | null;
  ja?: string | null;
  plate_ref?: number | null; // integer plate id when verse references a plate
  images?: { src: string; edition?: string; caption?: I18nText | null }[]; // 1882-edition images at this verse
  glossary_terms?: string[]; // canonical English headwords appearing in this verse
}

// Per-language text: English + the three translations (null until translated).
export interface I18nText {
  en?: string | null;
  zh_hant?: string | null;
  zh_hans?: string | null;
  ja?: string | null;
}

export interface ChapterData {
  id: string;
  book: string;
  chapter: number;
  title?: string;
  preamble?: I18nText | string | null; // chapter epigraph (i18n object; legacy string tolerated)
  verses: VerseData[];
}

// Per-chapter glossary slice injected by json-to-mdx: { "Jehovih": { translit: {...}, slug } }
export interface GlossaryEntry {
  translit: { zh_hant?: string | null; zh_hans?: string | null; ja?: string | null };
  slug: string;
}
export type GlossaryMap = Record<string, GlossaryEntry>;

// ---- constants --------------------------------------------------------------

type Lang = 'en' | 'zh_hant' | 'zh_hans' | 'ja';
type DisplayMode = 'single' | 'parallel';

const LANG_LABELS: Record<Lang, string> = {
  en: 'EN',
  zh_hant: '繁中',
  zh_hans: '简中',
  ja: '日',
};

const LANG_KEYS: Lang[] = ['en', 'zh_hant', 'zh_hans', 'ja'];

const LANG_STORAGE_KEY = 'oahspe-lang';
const DISPLAY_STORAGE_KEY = 'oahspe-display-mode';
const BOOKMARK_STORAGE_KEY = 'oahspe-bookmarks';

// ---- helpers ----------------------------------------------------------------

function getVerseText(verse: VerseData, lang: Lang): string {
  const v = verse[lang];
  return v != null && v !== '' ? v : verse.en;
}

// Resolve an i18n text object (or legacy string) for the active language, English fallback.
function getI18n(text: I18nText | string | null | undefined, lang: Lang): string {
  if (text == null) return '';
  if (typeof text === 'string') return text;
  const v = text[lang];
  return v != null && v !== '' ? v : (text.en ?? '');
}

function loadBookmarks(): Set<string> {
  try {
    const raw = localStorage.getItem(BOOKMARK_STORAGE_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function saveBookmarks(bm: Set<string>): void {
  try {
    localStorage.setItem(BOOKMARK_STORAGE_KEY, JSON.stringify([...bm]));
  } catch {
    // storage blocked — silent fail
  }
}

/** True if `term` (or its 4+ char alpha stem) appears as a word in the English source —
 *  a bilingual cross-check so a translit is only annotated when its English headword is
 *  really present in the same unit (skips 本 in 本聖經 where no "Ben" exists; keeps
 *  柯珀 where "CORPER"/"corporeal" appears). */
function enPresent(term: string, enSource: string): boolean {
  if (!enSource) return true; // no English to check against → don't suppress
  const esc = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (new RegExp(`(?<![A-Za-z])${esc}(?![A-Za-z])`, 'i').test(enSource)) return true;
  const stem = term.replace(/[^A-Za-z]/g, '').slice(0, 4);
  if (stem.length >= 4 && new RegExp(`(?<![A-Za-z])${stem}[A-Za-z]*`, 'i').test(enSource)) return true;
  return false;
}

/**
 * Render a CJK verse string, injecting `譯名（English）` on EVERY occurrence of each
 * glossary term's transliteration — but only for terms whose English headword is present
 * in `enSource` (bilingual cross-check). English text is never annotated.
 */
function renderWithParenthetical(
  text: string,
  lang: Lang,
  terms: string[] | undefined,
  glossary: GlossaryMap,
  enSource: string,
  glossaryBase: string,
): React.ReactNode {
  if (lang === 'en' || !terms || terms.length === 0) return text;

  // Build [translit, english, slug] triples present in this verse, longest translit first
  // so overlapping substrings match the most specific term. Gate on bilingual cross-check.
  const pairs: Array<[string, string, string]> = [];
  for (const en of terms) {
    const entry = glossary[en];
    const tl = entry?.translit?.[lang as 'zh_hant' | 'zh_hans' | 'ja'];
    if (tl && enPresent(en, enSource)) pairs.push([tl, en, entry?.slug ?? '']);
  }
  if (pairs.length === 0) return text;
  pairs.sort((a, b) => b[0].length - a[0].length);

  // Walk the string, splicing in a glossary link 譯名（English）on EVERY hit.
  const nodes: React.ReactNode[] = [];
  let i = 0;
  let key = 0;
  outer: while (i < text.length) {
    for (const [tl, en, slug] of pairs) {
      if (text.startsWith(tl, i)) {
        nodes.push(
          <a
            key={key++}
            href={slug ? `${glossaryBase}#${slug}` : glossaryBase}
            title={`Glossary: ${en}`}
          >
            {tl}
            <span className="verse-term-en">（{en}）</span>
          </a>,
        );
        i += tl.length;
        continue outer;
      }
    }
    // accumulate a plain run until the next possible match
    let j = i + 1;
    while (j < text.length) {
      let hit = false;
      for (const [tl] of pairs) {
        if (text.startsWith(tl, j)) { hit = true; break; }
      }
      if (hit) break;
      j++;
    }
    nodes.push(text.slice(i, j));
    i = j;
  }
  return nodes;
}

// ---- sub-components ---------------------------------------------------------

interface VerseRowProps {
  verse: VerseData;
  lang: Lang;
  displayMode: DisplayMode;
  bookmarks: Set<string>;
  onBookmarkToggle: (id: string) => void;
  chapterPath: string;
  glossary: GlossaryMap;
  glossaryBase: string;
}

const VerseRow = function VerseRow(props: VerseRowProps): React.ReactElement {
  const { verse, lang, displayMode, bookmarks, onBookmarkToggle, chapterPath, glossary, glossaryBase } = props;
  const anchorId = verse.id;
  const isBookmarked = bookmarks.has(anchorId);

  const handleShare = useCallback(() => {
    const url = `${window.location.origin}${chapterPath}#${anchorId}`;
    navigator.clipboard.writeText(url).catch(() => {
      const el = document.createElement('textarea');
      el.value = url;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    });
  }, [chapterPath, anchorId]);

  const handleBookmark = useCallback(() => {
    onBookmarkToggle(anchorId);
  }, [onBookmarkToggle, anchorId]);

  const enText = verse.en;
  const showParallel = displayMode === 'parallel' && lang !== 'en';
  const cjkNode = showParallel
    ? renderWithParenthetical(getVerseText(verse, lang), lang, verse.glossary_terms, glossary, verse.en, glossaryBase)
    : null;
  const singleNode =
    lang === 'en'
      ? enText
      : renderWithParenthetical(getVerseText(verse, lang), lang, verse.glossary_terms, glossary, verse.en, glossaryBase);

  return (
    <div id={anchorId} className="verse-row">
      <div className="verse-body">
        {!showParallel ? (
          <p className="verse-text">
            <sup className="verse-num">{verse.verse_number}</sup>
            {singleNode}
          </p>
        ) : (
          <div className="verse-parallel">
            <p className="verse-text verse-en">
              <sup className="verse-num">{verse.verse_number}</sup>
              {enText}
            </p>
            <p className="verse-text verse-cjk">
              <sup className="verse-num">{verse.verse_number}</sup>
              {cjkNode}
            </p>
          </div>
        )}

        {verse.plate_ref != null && <ImagePlate plateId={verse.plate_ref} />}

        {verse.images && verse.images.length > 0 && (
          <div className="verse-images">
            {verse.images.map((img) => {
              const capText = getI18n(img.caption, lang);
              const capEn = getI18n(img.caption, 'en');
              const capNode = lang === 'en'
                ? capText
                : renderWithParenthetical(capText, lang, verse.glossary_terms, glossary, capEn, glossaryBase);
              return (
                <figure key={img.src} className="verse-image">
                  <img src={`/oahspe${img.src}`} alt={capText || `Oahspe ${img.edition ?? ''} illustration`} loading="lazy" />
                  {capText && <figcaption>{capNode}</figcaption>}
                </figure>
              );
            })}
          </div>
        )}
      </div>

      <div className="verse-actions">
        <button
          className="verse-action-btn"
          onClick={handleShare}
          title="Copy link to this verse"
          aria-label="Copy link to this verse"
        >
          🔗
        </button>
        <button
          className={`verse-action-btn ${isBookmarked ? 'bookmarked' : ''}`}
          onClick={handleBookmark}
          title={isBookmarked ? 'Remove bookmark' : 'Bookmark this verse'}
          aria-label={isBookmarked ? 'Remove bookmark' : 'Bookmark this verse'}
        >
          {isBookmarked ? '🔖' : '📑'}
        </button>
      </div>
    </div>
  );
};

// ---- main component ---------------------------------------------------------

interface VerseReaderProps {
  chapter: ChapterData;
  glossary?: GlossaryMap;
  hidePreamble?: boolean;   // preamble shown on the book-index page instead (e.g. chapter 1)
}

export default function VerseReader({ chapter, glossary = {}, hidePreamble = false }: VerseReaderProps): React.ReactElement {
  const location = useLocation();
  const { i18n } = useDocusaurusContext();
  // Docusaurus locale (en|zh-hant|zh-hans|ja) → our Lang key.
  const localeToLang: Record<string, Lang> = {
    en: 'en', 'zh-hant': 'zh_hant', 'zh-hans': 'zh_hans', ja: 'ja',
  };
  const localeLang: Lang = localeToLang[i18n.currentLocale] ?? 'en';
  // Locale-aware glossary base so clicking a term keeps the reader's language
  // (default locale served at /oahspe/, others under /oahspe/<locale>/).
  const glossaryBase = i18n.currentLocale === i18n.defaultLocale
    ? '/oahspe/glossary'
    : `/oahspe/${i18n.currentLocale}/glossary`;

  const [lang, setLang] = useState<Lang>(localeLang);
  const [displayMode, setDisplayMode] = useState<DisplayMode>('single');
  const [bookmarks, setBookmarks] = useState<Set<string>>(new Set());
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // Stored preference wins over the page locale; else keep the locale default.
    const storedLang = localStorage.getItem(LANG_STORAGE_KEY) as Lang | null;
    const storedMode = localStorage.getItem(DISPLAY_STORAGE_KEY) as DisplayMode | null;
    if (storedLang && LANG_KEYS.includes(storedLang)) setLang(storedLang);
    if (storedMode === 'single' || storedMode === 'parallel') setDisplayMode(storedMode);
    setBookmarks(loadBookmarks());
    setHydrated(true);
  }, []);

  const handleLangChange = useCallback((l: Lang) => {
    setLang(l);
    try { localStorage.setItem(LANG_STORAGE_KEY, l); } catch { /* ignore */ }
  }, []);

  const handleModeChange = useCallback((m: DisplayMode) => {
    setDisplayMode(m);
    try { localStorage.setItem(DISPLAY_STORAGE_KEY, m); } catch { /* ignore */ }
  }, []);

  const handleBookmarkToggle = useCallback((id: string) => {
    setBookmarks((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      saveBookmarks(next);
      return next;
    });
  }, []);

  return (
    <div className="verse-reader">
      <div className="verse-toolbar" suppressHydrationWarning>
        <div className="verse-lang-buttons">
          {LANG_KEYS.map((l) => (
            <button
              key={l}
              className={`verse-lang-btn ${hydrated && lang === l ? 'active' : ''}`}
              onClick={() => handleLangChange(l)}
              aria-pressed={hydrated && lang === l}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>

        <div className="verse-mode-buttons">
          {(['single', 'parallel'] as DisplayMode[]).map((m) => (
            <button
              key={m}
              className={`verse-mode-btn ${hydrated && displayMode === m ? 'active' : ''}`}
              onClick={() => handleModeChange(m)}
              aria-pressed={hydrated && displayMode === m}
            >
              {m === 'single' ? 'Single' : 'Parallel'}
            </button>
          ))}
        </div>
      </div>

      {hydrated && lang !== 'en' && !chapter.verses.some((v) => v[lang]) && (
        <div className="verse-untranslated-note" role="status">
          This chapter is not yet translated into {LANG_LABELS[lang]}. Showing the original English.
        </div>
      )}

      {!hidePreamble && getI18n(chapter.preamble, lang) && (
        <div className="chapter-preamble">
          {lang === 'en'
            ? getI18n(chapter.preamble, lang)
            : renderWithParenthetical(getI18n(chapter.preamble, lang), lang, Object.keys(glossary), glossary, getI18n(chapter.preamble, 'en'), glossaryBase)}
        </div>
      )}

      <div className="verse-list">
        {chapter.verses.map((verse) => (
          <VerseRow
            key={verse.id}
            verse={verse}
            lang={lang}
            displayMode={displayMode}
            bookmarks={bookmarks}
            onBookmarkToggle={handleBookmarkToggle}
            chapterPath={location.pathname}
            glossary={glossary}
            glossaryBase={glossaryBase}
          />
        ))}
      </div>
    </div>
  );
}
