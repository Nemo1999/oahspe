import React, { useEffect, useState, useCallback } from 'react';
import { useLocation } from '@docusaurus/router';
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

/**
 * Render a CJK verse string, injecting `譯名（English）` on EVERY occurrence of each
 * glossary term's transliteration in the text. English is never annotated (the
 * source already shows the term).
 */
function renderWithParenthetical(
  text: string,
  lang: Lang,
  terms: string[] | undefined,
  glossary: GlossaryMap,
): React.ReactNode {
  if (lang === 'en' || !terms || terms.length === 0) return text;

  // Build [translit, english, slug] triples present in this verse, longest translit first
  // so overlapping substrings match the most specific term.
  const pairs: Array<[string, string, string]> = [];
  for (const en of terms) {
    const entry = glossary[en];
    const tl = entry?.translit?.[lang as 'zh_hant' | 'zh_hans' | 'ja'];
    if (tl) pairs.push([tl, en, entry?.slug ?? '']);
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
            className="verse-term"
            href={slug ? `/oahspe/glossary#${slug}` : '/oahspe/glossary'}
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
}

const VerseRow = function VerseRow(props: VerseRowProps): React.ReactElement {
  const { verse, lang, displayMode, bookmarks, onBookmarkToggle, chapterPath, glossary } = props;
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
    ? renderWithParenthetical(getVerseText(verse, lang), lang, verse.glossary_terms, glossary)
    : null;
  const singleNode =
    lang === 'en'
      ? enText
      : renderWithParenthetical(getVerseText(verse, lang), lang, verse.glossary_terms, glossary);

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
              const capNode = lang === 'en'
                ? capText
                : renderWithParenthetical(capText, lang, verse.glossary_terms, glossary);
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
}

export default function VerseReader({ chapter, glossary = {} }: VerseReaderProps): React.ReactElement {
  const location = useLocation();

  const [lang, setLang] = useState<Lang>('en');
  const [displayMode, setDisplayMode] = useState<DisplayMode>('single');
  const [bookmarks, setBookmarks] = useState<Set<string>>(new Set());
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
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

      {getI18n(chapter.preamble, lang) && (
        <div className="chapter-preamble">{getI18n(chapter.preamble, lang)}</div>
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
          />
        ))}
      </div>
    </div>
  );
}
