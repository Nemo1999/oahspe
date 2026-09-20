/**
 * Swizzled SearchBar — uses Pagefind instead of Docusaurus default search.
 *
 * Pagefind is injected by `pagefind --site build` post-build.
 * In dev mode the index doesn't exist; we show a graceful fallback.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';

// ---- Pagefind type stubs (no @types/pagefind package) ----------------------

interface PagefindResultData {
  url: string;
  meta: { title?: string };
  excerpt: string;
}

interface PagefindResult {
  id: string;
  data: () => Promise<PagefindResultData>;
}

interface PagefindSearchResponse {
  results: PagefindResult[];
}

interface PagefindModule {
  init: () => Promise<void>;
  search: (
    query: string,
    options?: { filters?: Record<string, string> },
  ) => Promise<PagefindSearchResponse>;
}

// ---- helpers ----------------------------------------------------------------

// ponytail: simple debounce via useRef — no library needed
function useDebounce<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

// ---- component --------------------------------------------------------------

interface SearchResult {
  id: string;
  url: string;
  title: string;
  excerpt: string;
}

type SearchState = 'idle' | 'unavailable' | 'loading' | 'done' | 'error';

export default function SearchBar(): React.ReactElement {
  const { i18n } = useDocusaurusContext();
  const currentLocale = i18n.currentLocale;

  const [query, setQuery]         = useState('');
  const [results, setResults]     = useState<SearchResult[]>([]);
  const [status, setStatus]       = useState<SearchState>('idle');
  const [open, setOpen]           = useState(false);

  const pagefindRef = useRef<PagefindModule | null>(null);
  const inputRef    = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const debouncedQuery = useDebounce(query, 300);

  // Lazy-load Pagefind once, on first keystroke (SSR-safe: runs in useEffect)
  const loadPagefind = useCallback(async (): Promise<PagefindModule | null> => {
    if (pagefindRef.current) return pagefindRef.current;
    try {
      // Dynamic import — only runs in browser, path is relative to origin
      const pf = (await import(
        /* webpackIgnore: true */ '/oahspe/pagefind/pagefind.js' as string
      )) as PagefindModule;
      await pf.init();
      pagefindRef.current = pf;
      return pf;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([]);
      setStatus('idle');
      return;
    }

    let cancelled = false;

    (async () => {
      setStatus('loading');
      const pf = await loadPagefind();
      if (!pf) {
        if (!cancelled) setStatus('unavailable');
        return;
      }

      try {
        // Pagefind is zero-config multilingual: it auto-loads the index matching the
        // page's <html lang>, so each locale build searches only its own language.
        // (No `language` filter — that filter was never indexed and returned zero hits.)
        const response = await pf.search(debouncedQuery);
        if (cancelled) return;

        // Resolve first 8 results (data() is per-result async)
        const slice = response.results.slice(0, 8);
        const resolved = await Promise.all(
          slice.map(async (r) => {
            const d = await r.data();
            return {
              id:      r.id,
              url:     d.url,
              title:   d.meta?.title ?? 'Untitled',
              excerpt: d.excerpt,
            } satisfies SearchResult;
          }),
        );
        if (!cancelled) {
          setResults(resolved);
          setStatus('done');
          setOpen(true);
        }
      } catch {
        if (!cancelled) setStatus('error');
      }
    })();

    return () => { cancelled = true; };
  }, [debouncedQuery, currentLocale, loadPagefind]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const onPointer = (e: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('pointerdown', onPointer);
    return () => document.removeEventListener('pointerdown', onPointer);
  }, []);

  const handleClear = useCallback(() => {
    setQuery('');
    setResults([]);
    setStatus('idle');
    setOpen(false);
    inputRef.current?.focus();
  }, []);

  const showDropdown = open && query.trim().length > 0;

  return (
    <div ref={containerRef} className="pagefind-searchbar" role="search">
      <div className="pagefind-searchbar-input-wrap">
        <input
          ref={inputRef}
          type="search"
          className="pagefind-searchbar-input"
          placeholder="Search…"
          value={query}
          aria-label="Search"
          aria-autocomplete="list"
          aria-expanded={showDropdown}
          aria-controls="pagefind-results"
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (results.length > 0) setOpen(true); }}
        />
        {query && (
          <button
            className="pagefind-searchbar-clear"
            onClick={handleClear}
            aria-label="Clear search"
            tabIndex={-1}
          >
            ✕
          </button>
        )}
      </div>

      {showDropdown && (
        <div
          id="pagefind-results"
          className="pagefind-results-dropdown"
          role="listbox"
          aria-label="Search results"
        >
          {status === 'unavailable' && (
            <div className="pagefind-results-notice">
              Search available after build
            </div>
          )}
          {status === 'loading' && (
            <div className="pagefind-results-notice" aria-live="polite">
              Searching…
            </div>
          )}
          {status === 'error' && (
            <div className="pagefind-results-notice pagefind-results-notice--error">
              Search error. Try again.
            </div>
          )}
          {status === 'done' && results.length === 0 && (
            <div className="pagefind-results-notice">
              No results for "{query}"
            </div>
          )}
          {results.map((result) => (
            <a
              key={result.id}
              href={result.url}
              className="pagefind-result-item"
              role="option"
              aria-selected="false"
              onClick={() => setOpen(false)}
            >
              <div className="pagefind-result-title">{result.title}</div>
              <div
                className="pagefind-result-excerpt"
                /* Pagefind marks matched terms with <mark> tags */
                dangerouslySetInnerHTML={{ __html: result.excerpt }}
              />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
