import React, { useState, useEffect, useCallback } from 'react';
import { useHistory } from '@docusaurus/router';

const BOOKMARK_STORAGE_KEY = 'oahspe-bookmarks';

function readBookmarks(): string[] {
  try {
    const raw = localStorage.getItem(BOOKMARK_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function removeBookmark(id: string): string[] {
  try {
    const raw = localStorage.getItem(BOOKMARK_STORAGE_KEY);
    const list: string[] = raw ? (JSON.parse(raw) as string[]) : [];
    const next = list.filter((b) => b !== id);
    localStorage.setItem(BOOKMARK_STORAGE_KEY, JSON.stringify(next));
    return next;
  } catch {
    return [];
  }
}

export default function BookmarkBar(): React.ReactElement | null {
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [open, setOpen]           = useState(false);
  const [hydrated, setHydrated]   = useState(false);
  const history = useHistory();

  useEffect(() => {
    setBookmarks(readBookmarks());
    setHydrated(true);

    // Sync across tabs
    const onStorage = (e: StorageEvent) => {
      if (e.key === BOOKMARK_STORAGE_KEY) {
        setBookmarks(readBookmarks());
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const handleRemove = useCallback((id: string) => {
    setBookmarks(removeBookmark(id));
  }, []);

  // Don't render anything during SSR or before hydration
  if (!hydrated) return null;
  if (bookmarks.length === 0) return null;

  return (
    <div className="bookmark-bar" suppressHydrationWarning>
      <button
        className="bookmark-bar-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="bookmark-drawer"
      >
        🔖 {bookmarks.length} bookmark{bookmarks.length !== 1 ? 's' : ''}
      </button>

      {open && (
        <div
          id="bookmark-drawer"
          className="bookmark-drawer"
          role="region"
          aria-label="Bookmarks"
        >
          <div className="bookmark-drawer-header">
            <span>Bookmarks</span>
            <button
              className="bookmark-drawer-close"
              onClick={() => setOpen(false)}
              aria-label="Close bookmarks"
            >
              ✕
            </button>
          </div>

          <ul className="bookmark-list">
            {bookmarks.map((id) => (
              <li key={id} className="bookmark-item">
                <a
                  href={`#${id}`}
                  className="bookmark-link"
                  onClick={(e) => {
                    e.preventDefault();
                    setOpen(false);
                    // Navigate then scroll — works for both same-page and cross-page bookmarks
                    const [path, anchor] = id.startsWith('v') ? [undefined, id] : id.split('#');
                    if (path) {
                      history.push(`/${path}#${anchor}`);
                    } else {
                      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
                    }
                  }}
                >
                  {id}
                </a>
                <button
                  className="bookmark-remove"
                  onClick={() => handleRemove(id)}
                  aria-label={`Remove bookmark ${id}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>

          <a href="/oahspe/bookmarks" className="bookmark-all-link">
            View all bookmarks →
          </a>
        </div>
      )}
    </div>
  );
}
