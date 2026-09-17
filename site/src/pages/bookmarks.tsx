import React, { useEffect, useState } from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import clsx from 'clsx';
import styles from './bookmarks.module.css';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Bookmark {
  verseId: string;
  addedAt: string; // ISO string
  note?: string;
}

type BookmarkStore = Record<string, Omit<Bookmark, 'verseId'>>;

const STORAGE_KEY = 'oahspe-bookmarks';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function loadBookmarks(): Bookmark[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const store: BookmarkStore = JSON.parse(raw);
    return Object.entries(store).map(([verseId, rest]) => ({ verseId, ...rest }));
  } catch {
    return [];
  }
}

function clearBookmarks(): void {
  localStorage.removeItem(STORAGE_KEY);
}

function downloadJSON(data: BookmarkStore, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Convert a verseId like "book-of-jehovih.1.3" into a readable doc path */
function verseIdToPath(verseId: string): string {
  // Format expected: <book-slug>.<chapter>.<verse>
  const parts = verseId.split('.');
  if (parts.length < 2) return `/${verseId}`;
  const [bookSlug, chapter] = parts;
  const anchor = parts.length >= 3 ? `#v${parts[2]}` : '';
  return `/${bookSlug}/${chapter}${anchor}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function BookmarksPage(): JSX.Element {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [mounted, setMounted] = useState(false);

  // SSR guard — localStorage only available in browser
  useEffect(() => {
    setMounted(true);
    setBookmarks(loadBookmarks());
  }, []);

  function handleClear(): void {
    if (window.confirm('Remove all bookmarks? This cannot be undone.')) {
      clearBookmarks();
      setBookmarks([]);
    }
  }

  function handleExport(): void {
    const raw = localStorage.getItem(STORAGE_KEY);
    const store: BookmarkStore = raw ? JSON.parse(raw) : {};
    downloadJSON(store, 'oahspe-bookmarks.json');
  }

  function handleRemove(verseId: string): void {
    const raw = localStorage.getItem(STORAGE_KEY);
    const store: BookmarkStore = raw ? JSON.parse(raw) : {};
    delete store[verseId];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    setBookmarks((prev) => prev.filter((b) => b.verseId !== verseId));
  }

  return (
    <Layout title="Bookmarks" description="Your saved verse bookmarks">
      <main className={clsx('container', 'margin-vert--lg', styles.page)}>
        <div className="row">
          <div className={clsx('col col--8 col--offset-2')}>
            <h1>Bookmarks</h1>

            {!mounted ? (
              <p>Loading bookmarks…</p>
            ) : bookmarks.length === 0 ? (
              <p className={styles.empty}>
                No bookmarks yet. Click a verse number while reading to save it here.
              </p>
            ) : (
              <>
                <p>
                  {bookmarks.length} bookmark{bookmarks.length !== 1 ? 's' : ''} saved.
                </p>

                <ul className={styles.list}>
                  {bookmarks
                    .slice()
                    .sort((a, b) => b.addedAt.localeCompare(a.addedAt))
                    .map((bm) => (
                      <li key={bm.verseId} className={styles.item}>
                        <div className={styles.itemMain}>
                          <Link to={verseIdToPath(bm.verseId)} className={styles.verseLink}>
                            {bm.verseId}
                          </Link>
                          {bm.note && <span className={styles.note}>{bm.note}</span>}
                        </div>
                        <div className={styles.itemMeta}>
                          <time dateTime={bm.addedAt} className={styles.date}>
                            {formatDate(bm.addedAt)}
                          </time>
                          <button
                            type="button"
                            className={clsx('button', 'button--sm', 'button--outline', 'button--danger')}
                            onClick={() => handleRemove(bm.verseId)}
                            aria-label={`Remove bookmark ${bm.verseId}`}
                          >
                            Remove
                          </button>
                        </div>
                      </li>
                    ))}
                </ul>

                <div className={styles.actions}>
                  <button
                    type="button"
                    className="button button--secondary"
                    onClick={handleExport}
                  >
                    Export JSON
                  </button>
                  <button
                    type="button"
                    className="button button--danger"
                    onClick={handleClear}
                  >
                    Clear All
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </Layout>
  );
}
