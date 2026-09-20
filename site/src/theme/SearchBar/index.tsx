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
  options: (options: { highlightParam: string }) => Promise<void>;
  search: (query: string) => Promise<PagefindSearchResponse>;
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
  const { i18n, siteConfig } = useDocusaurusContext();
  const { currentLocale, defaultLocale } = i18n;
  const siteBaseUrl = siteConfig.baseUrl.endsWith(`/${currentLocale}/`) ? siteConfig.baseUrl.slice(0, -currentLocale.length - 1) : siteConfig.baseUrl;
  const pagefindPath = `${siteBaseUrl}${currentLocale === defaultLocale ? '' : `${currentLocale}/`}pagefind/pagefind.js`;
  const searchPath = `${siteBaseUrl}${currentLocale === defaultLocale ? '' : `${currentLocale}/`}search`;

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [status, setStatus] = useState<SearchState>('idle');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const pagefindRef = useRef<PagefindModule | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debouncedQuery = useDebounce(query, 300);

  const loadPagefind = useCallback(async (): Promise<PagefindModule | null> => {
    if (pagefindRef.current) return pagefindRef.current;
    try {
      // Runtime selection is required: every Docusaurus locale emits its own Pagefind bundle.
      const pf = (await import(/* webpackIgnore: true */ pagefindPath)) as PagefindModule;
      await pf.init();
      await pf.options({ highlightParam: 'pagefind-highlight' });
      pagefindRef.current = pf;
      return pf;
    } catch {
      return null;
    }
  }, [pagefindPath]);

  useEffect(() => {
    pagefindRef.current = null;
  }, [pagefindPath]);

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([]);
      setStatus('idle');
      return;
    }
    let cancelled = false;
    void (async () => {
      setStatus('loading');
      const pf = await loadPagefind();
      if (!pf) {
        if (!cancelled) setStatus('unavailable');
        return;
      }
      try {
        const response = await pf.search(debouncedQuery);
        const resolved = await Promise.all(response.results.slice(0, 8).map(async (result) => {
          const data = await result.data();
          return {
            id: result.id,
            url: data.url,
            title: data.meta?.title ?? 'Untitled',
            excerpt: data.excerpt,
          } satisfies SearchResult;
        }));
        if (!cancelled) {
          setResults(resolved);
          setActiveIndex(0);
          setStatus('done');
          setOpen(true);
        }
      } catch {
        if (!cancelled) setStatus('error');
      }
    })();
    return () => { cancelled = true; };
  }, [debouncedQuery, loadPagefind]);

  useEffect(() => {
    const onPointer = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false);
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
  const activeResult = results[activeIndex];
  const resultUrl = (result: SearchResult) => {
    const url = new URL(result.url, window.location.href);
    url.searchParams.set('pagefind-highlight', query.trim());
    return url.href;
  };
  const allResultsUrl = `${searchPath}?q=${encodeURIComponent(query.trim())}`;

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
          aria-activedescendant={activeResult ? `pagefind-result-${activeResult.id}` : undefined}
          onChange={(event) => setQuery(event.target.value)}
          onFocus={() => { if (results.length > 0) setOpen(true); }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') { setOpen(false); return; }
            if (event.key === 'Enter' && query.trim()) {
              event.preventDefault(); window.location.assign(allResultsUrl);
            } else if (!results.length) return;
            else if (event.key === 'ArrowDown' || (event.ctrlKey && event.key === 'n')) {
              event.preventDefault(); setOpen(true); setActiveIndex((index) => (index + 1) % results.length);
            } else if (event.key === 'ArrowUp' || (event.ctrlKey && event.key === 'p')) {
              event.preventDefault(); setOpen(true); setActiveIndex((index) => (index - 1 + results.length) % results.length);
            }
          }}
        />
        {query && <button className="pagefind-searchbar-clear" onClick={handleClear} aria-label="Clear search" tabIndex={-1}>✕</button>}
      </div>
      {showDropdown && (
        <div id="pagefind-results" className="pagefind-results-dropdown" role="listbox" aria-label="Search results">
          {status === 'unavailable' && <div className="pagefind-results-notice">Search available after build</div>}
          {status === 'loading' && <div className="pagefind-results-notice" aria-live="polite">Searching…</div>}
          {status === 'error' && <div className="pagefind-results-notice pagefind-results-notice--error">Search error. Try again.</div>}
          {status === 'done' && results.length === 0 && <div className="pagefind-results-notice">No results for "{query}"</div>}
          {results.length > 0 && <>
            <div className="pagefind-results-list">
              {results.map((result, index) => <a key={result.id} id={`pagefind-result-${result.id}`} href={resultUrl(result)} className="pagefind-result-item" role="option" aria-selected={index === activeIndex} onMouseEnter={() => setActiveIndex(index)} onClick={() => setOpen(false)}>
                <div className="pagefind-result-title">{result.title}</div>
                <div className="pagefind-result-excerpt" dangerouslySetInnerHTML={{ __html: result.excerpt }} />
              </a>)}
            </div>
            {activeResult && <aside className="pagefind-result-preview" aria-live="polite"><div className="pagefind-result-title">{activeResult.title}</div><div className="pagefind-result-excerpt" dangerouslySetInnerHTML={{ __html: activeResult.excerpt }} /></aside>}
            <a className="pagefind-see-all" href={allResultsUrl}>See all results</a>
          </>}
        </div>
      )}
    </div>
  );
}
