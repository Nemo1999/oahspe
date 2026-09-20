import React, { useEffect, useMemo, useRef, useState } from 'react';
import Layout from '@theme/Layout';
import { useLocation } from '@docusaurus/router';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import books from '@site/../content/meta/books.json';

interface PagefindResultData {
  url: string;
  content: string;
  locations: number[];
  anchors: Array<{ id: string; location: number }>;
}

interface PagefindResult {
  id: string;
  data: () => Promise<PagefindResultData>;
}

interface PagefindModule {
  init: () => Promise<void>;
  options: (options: { highlightParam: string }) => Promise<void>;
  search: (query: string) => Promise<{ results: PagefindResult[] }>;
}

interface VerseResult {
  id: string;
  url: string;
  text: string;
  previous?: string;
  next?: string;
}

const BOOK_TITLES = new Map(books.map((book) => [book.slug, book.title]));
const VERSE_ID = /^(.+)\.(\d+)\.(\d+)$/;

function verseIds(data: PagefindResultData): string[] {
  const anchors = data.anchors.filter((anchor) => VERSE_ID.test(anchor.id)).sort((a, b) => a.location - b.location);
  return [...new Set(data.locations.map((location) => anchors.filter((anchor) => anchor.location <= location).at(-1)?.id).filter((id): id is string => Boolean(id)))];
}

async function versePreview(url: string, id: string): Promise<VerseResult> {
  const page = new DOMParser().parseFromString(await fetch(url).then((response) => response.text()), 'text/html');
  const row = page.getElementById(id);
  if (!row) throw new Error(`Verse ${id} was not found`);
  const text = (element: Element | null) => element?.textContent?.replace(/\s+/g, ' ').trim() || '';
  return {
    id,
    url: `${url}#${id}`,
    text: text(row),
    previous: text(row.previousElementSibling?.matches('.verse-row') ? row.previousElementSibling : null),
    next: text(row.nextElementSibling?.matches('.verse-row') ? row.nextElementSibling : null),
  };
}

export default function SearchPage(): React.ReactElement {
  const location = useLocation();
  const { i18n, siteConfig } = useDocusaurusContext();
  const query = useMemo(() => new URLSearchParams(location.search).get('q')?.trim() || '', [location.search]);
  const baseUrl = siteConfig.baseUrl.endsWith(`/${i18n.currentLocale}/`) ? siteConfig.baseUrl.slice(0, -i18n.currentLocale.length - 1) : siteConfig.baseUrl;
  const pagefindPath = `${baseUrl}${i18n.currentLocale === i18n.defaultLocale ? '' : `${i18n.currentLocale}/`}pagefind/pagefind.js`;
  const pagefind = useRef<PagefindModule | null>(null);
  const [results, setResults] = useState<VerseResult[]>([]);
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [page, setPage] = useState(0);
  const perPage = 10;

  useEffect(() => {
    let cancelled = false;
    setPage(0);
    if (!query) { setResults([]); setStatus('idle'); return; }
    void (async () => {
      try {
        setStatus('loading');
        // Pagefind is emitted after the Docusaurus build, so its locale-specific URL is runtime-selected.
        pagefind.current ??= (await import(/* webpackIgnore: true */ pagefindPath)) as PagefindModule;
        await pagefind.current.init();
        await pagefind.current.options({ highlightParam: 'pagefind-highlight' });
        const search = await pagefind.current.search(query);
        const previews = await Promise.all((await Promise.all(search.results.map(async (result) => {
          const data = await result.data();
          const url = new URL(data.url, window.location.href).href.split('#')[0];
          return Promise.all(verseIds(data).map((id) => versePreview(url, id)));
        }))).flat());
        if (!cancelled) { setResults(previews); setStatus('done'); }
      } catch {
        if (!cancelled) setStatus('error');
      }
    })();
    return () => { cancelled = true; };
  }, [pagefindPath, query]);

  const visible = results.slice(page * perPage, (page + 1) * perPage);
  const pageCount = Math.ceil(results.length / perPage);
  return <Layout title={query ? `Search: ${query}` : 'Search'}>
    <main className="container margin-vert--lg search-page">
      <h1>Search scripture</h1>
      {!query && <p>Enter a search term in the navigation search box.</p>}
      {query && <p aria-live="polite">{status === 'loading' ? 'Searching…' : `${results.length} matching verse${results.length === 1 ? '' : 's'} for “${query}”`}</p>}
      <div className="search-page-results">
        {visible.map((result) => {
          const [, book, chapter, verse] = result.id.match(VERSE_ID) || [];
          return <article key={result.url} className="search-page-result">
            <a href={`${result.url.split('#')[0]}?pagefind-highlight=${encodeURIComponent(query)}#${result.id}`} className="search-page-result-meta">{BOOK_TITLES.get(book) ?? book} · Chapter {chapter} · Verse {verse}</a>
            {result.previous && <p className="search-page-neighbor">Previous: {result.previous}</p>}
            <p className="search-page-verse">{result.text}</p>
            {result.next && <p className="search-page-neighbor">Next: {result.next}</p>}
          </article>;
        })}
      </div>
      {pageCount > 1 && <nav className="search-page-pagination" aria-label="Search result pages">
        <button disabled={page === 0} onClick={() => setPage((current) => current - 1)}>Previous</button>
        <span>Page {page + 1} of {pageCount}</span>
        <button disabled={page + 1 === pageCount} onClick={() => setPage((current) => current + 1)}>Next</button>
      </nav>}
    </main>
  </Layout>;
}
