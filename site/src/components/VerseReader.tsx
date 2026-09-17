import React, { useEffect, useState, useCallback } from 'react';
import { useLocation } from '@docusaurus/router';
import ImagePlate from './ImagePlate';

// ---- types ------------------------------------------------------------------

export interface VerseData {
  id: string;               // e.g. "jehovih.1.3" (book-slug.chapter.verse)
  verse_number: number;
  text: {
    en: string;
    zh_tw?: string;
    zh_cn?: string;
    ja?: string;
  };
  plate_ref?: number;        // integer plate id when verse references a plate
  glossary_terms?: string[]; // terms appearing in this verse
}

export interface ChapterData {
  book: string;
  book_slug: string;
  chapter: number;
  title?: string;
  verses: VerseData[];
}

// ---- constants --------------------------------------------------------------

type Lang = 'en' | 'zh-TW' | 'zh-CN' | 'ja';
type DisplayMode = 'single' | 'parallel';

const LANG_LABELS: Record<Lang, string> = {
  'en':    'EN',
  'zh-TW': '繁中',
  'zh-CN': '简中',
  'ja':    '日',
};

const LANG_KEYS: Lang[] = ['en', 'zh-TW', 'zh-CN', 'ja'];

const LANG_STORAGE_KEY    = 'oahspe-lang';
const DISPLAY_STORAGE_KEY = 'oahspe-display-mode';
const BOOKMARK_STORAGE_KEY = 'oahspe-bookmarks';

// ---- helpers ----------------------------------------------------------------

function getVerseText(verse: VerseData, lang: Lang): string {
  switch (lang) {
    case 'zh-TW': return verse.text.zh_tw ?? verse.text.en;
    case 'zh-CN': return verse.text.zh_cn ?? verse.text.en;
    case 'ja':    return verse.text.ja    ?? verse.text.en;
    default:      return verse.text.en;
  }
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

// ---- sub-components ---------------------------------------------------------

interface VerseRowProps {
  verse: VerseData;
  lang: Lang;
  displayMode: DisplayMode;
  bookmarks: Set<string>;
  onBookmarkToggle: (id: string) => void;
  chapterPath: string;
}

const VerseRow = React.memo(function VerseRow({
  verse,
  lang,
  displayMode,
  bookmarks,
  onBookmarkToggle,
  chapterPath,
}: VerseRowProps) {
  const anchorId = verse.id;
  const isBookmarked = bookmarks.has(anchorId);

  const handleShare = useCallback(() => {
    const url = `${window.location.origin}${chapterPath}#${anchorId}`;
    navigator.clipboard.writeText(url).catch(() => {
      // fallback for insecure contexts
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

  const enText  = verse.text.en;
  const cjkText = lang !== 'en' ? getVerseText(verse, lang) : null;

    <div id={anchorId} className="verse-row">
      <div className="verse-body">
        {displayMode === 'single' || lang === 'en' ? (
          <p className="verse-text">
            <sup className="verse-num">{verse.verse_number}</sup>
            {getVerseText(verse, lang)}
          </p>
        ) : (
          <div className="verse-parallel">
            <p className="verse-text verse-en">
              <sup className="verse-num">{verse.verse_number}</sup>
              {enText}
            </p>
            <p className="verse-text verse-cjk">
              <sup className="verse-num">{verse.verse_number}</sup>
              {cjkText}
            </p>
          </div>
        )}

        {verse.plate_ref !== undefined && (
          <ImagePlate plateId={verse.plate_ref} />
        )}

        {verse.glossary_terms && verse.glossary_terms.length > 0 && (
          <div className="verse-glossary-tags">
            {verse.glossary_terms.map((term) => (
              <span key={term} className="verse-glossary-tag">{term}</span>
            ))}
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
});

// ---- main component ---------------------------------------------------------

interface VerseReaderProps {
  chapter: ChapterData;
}

export default function VerseReader({ chapter }: VerseReaderProps): React.ReactElement {
  const location = useLocation();

  // SSR-safe state — initialised from localStorage in useEffect
  const [lang, setLang]               = useState<Lang>('en');
  const [displayMode, setDisplayMode] = useState<DisplayMode>('single');
  const [bookmarks, setBookmarks]     = useState<Set<string>>(new Set());
  const [hydrated, setHydrated]       = useState(false);

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
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      saveBookmarks(next);
      return next;
    });
  }, []);

  // Use SSR-stable suppressHydrationWarning on controls that differ
  return (
    <div className="verse-reader">
      {/* ---- toolbar ---- */}
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

      {/* ---- verses ---- */}
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
          />
        ))}
      </div>
    </div>
  );
}
