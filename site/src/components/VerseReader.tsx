import React, { useEffect, useState, useCallback, useMemo } from 'react';
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
  glossary_terms?: string[]; // canonical English headwords appearing in this verse
}

export interface ChapterData {
  id: string;
  book: string;
  chapter: number;
  title?: string;
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
 * Render a CJK verse string, injecting `譯名（English）` the FIRST time each
 * glossary term's transliteration appears in the chapter (Q4/Q5). `seen` is a
 * chapter-scoped set mutated as we walk verses in order. English is never
 * annotated (the source already shows the term).
 */
function renderWithParenthetical(
  text: string,
  lang: Lang,
  terms: string[] | undefined,
  glossary: GlossaryMap,
  seen: Set<string>,
): React.ReactNode {
  if (lang === 'en' || !terms || terms.length === 0) return text;

  // Build [translit, english] pairs present in this verse, longest translit first
  // so overlapping substrings match the most specific term.
  const pairs: Array<[string, string]> = [];
  for (const en of terms) {
    const entry = glossary[en];
    const tl = entry?.translit?.[lang as 'zh_hant' | 'zh_hans' | 'ja'];
    if (tl) pairs.push([tl, en]);
  }
  if (pairs.length === 0) return text;
  pairs.sort((a, b) => b[0].length - a[0].length);

  // Walk the string, splicing in <span>譯名（English）</span> on first hit per term.
  const nodes: React.ReactNode[] = [];
  let i = 0;
  let key = 0;
  outer: while (i < text.length) {
    for (const [tl, en] of pairs) {
      if (!seen.has(en) && text.startsWith(tl, i)) {
        seen.add(en);
        nodes.push(
          <span key={key++} className="verse-term">
            {tl}
            <span className="verse-term-en">（{en}）</span>
          </span>,
        );
        i += tl.length;
        continue outer;
      }
    }
    // accumulate a plain run until the next possible match
    let j = i + 1;
    while (j < text.length) {
      let hit = false;
      for (const [tl, en] of pairs) {
        if (!seen.has(en) && text.startsWith(tl, j)) { hit = true; break; }
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
  seenTW: Set<string>;
  seenCN: Set<string>;
  seenJA: Set<string>;
}

function seenFor(lang: Lang, p: VerseRowProps): Set<string> {
  if (lang === 'zh_hant') return p.seenTW;
  if (lang === 'zh_hans') return p.seenCN;
  return p.seenJA;
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
    ? renderWithParenthetical(getVerseText(verse, lang), lang, verse.glossary_terms, glossary, seenFor(lang, props))
    : null;
  const singleNode =
    lang === 'en'
      ? enText
      : renderWithParenthetical(getVerseText(verse, lang), lang, verse.glossary_terms, glossary, seenFor(lang, props));

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

  // Chapter-scoped "first occurrence" trackers, reset whenever lang/mode/chapter
  // changes so re-renders re-annotate deterministically from the top.
  const { seenTW, seenCN, seenJA } = useMemo(
    () => ({ seenTW: new Set<string>(), seenCN: new Set<string>(), seenJA: new Set<string>() }),
    [lang, displayMode, chapter.id],
  );

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
            seenTW={seenTW}
            seenCN={seenCN}
            seenJA={seenJA}
          />
        ))}
      </div>
    </div>
  );
}
