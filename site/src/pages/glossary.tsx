import React, { useMemo, useState } from 'react';
import Layout from '@theme/Layout';
import terms from '@site/../content/glossary/terms.json';

// terms.json schema (see docs/TRANSLATION_GUIDE.md §4a)
interface Translit { zh_hant?: string | null; zh_hans?: string | null; ja?: string | null; }
interface EditorNote { en?: string | null; zh_hant?: string | null; zh_hans?: string | null; ja?: string | null; }
interface Term {
  term: string;
  slug: string;
  category: 'name' | 'term';
  translit: Translit;
  source_def?: string | null;
  source_def_literal?: Translit | null;
  editor_note?: EditorNote | null;
  appears_in?: string[];
  cross_refs?: string[];
}

const ALL = terms as Term[];

function hasTranslit(t: Term): boolean {
  const tl = t.translit || {};
  return Boolean(tl.zh_hant || tl.zh_hans || tl.ja);
}

function TermCard({ t }: { t: Term }): React.ReactElement {
  const tl = t.translit || {};
  const note = t.editor_note || {};
  const lit = t.source_def_literal || {};
  return (
    <div id={t.slug} className="glossary-card">
      <div className="glossary-card-head">
        <span className="glossary-term">{t.term}</span>
        {hasTranslit(t) && (
          <span className="glossary-translit">
            {tl.zh_hant && <span>繁 {tl.zh_hant}</span>}
            {tl.zh_hans && <span>简 {tl.zh_hans}</span>}
            {tl.ja && <span>日 {tl.ja}</span>}
          </span>
        )}
        <span className={`glossary-cat glossary-cat-${t.category}`}>{t.category}</span>
      </div>

      {t.source_def && (
        <div className="glossary-source">
          <span className="glossary-label">From the text (1882)</span>
          <p>{t.source_def}</p>
          {(lit.zh_hant || lit.zh_hans || lit.ja) && (
            <p className="glossary-source-lit">
              {lit.zh_hant && <span>繁 {lit.zh_hant}</span>}
              {lit.zh_hans && <span>简 {lit.zh_hans}</span>}
              {lit.ja && <span>日 {lit.ja}</span>}
            </p>
          )}
        </div>
      )}

      {(note.en || note.zh_hant || note.zh_hans || note.ja) && (
        <div className="glossary-note">
          <span className="glossary-label">Editor's note / 編者註 / 訳者註</span>
          {note.en && <p><strong>EN</strong> {note.en}</p>}
          {note.zh_hant && <p><strong>繁</strong> {note.zh_hant}</p>}
          {note.zh_hans && <p><strong>简</strong> {note.zh_hans}</p>}
          {note.ja && <p><strong>日</strong> {note.ja}</p>}
        </div>
      )}

      {t.appears_in && t.appears_in.length > 0 && (
        <div className="glossary-appears">
          Appears in: {t.appears_in.slice(0, 12).join(', ')}
          {t.appears_in.length > 12 ? ` … (+${t.appears_in.length - 12})` : ''}
        </div>
      )}
    </div>
  );
}

export default function GlossaryPage(): React.ReactElement {
  const [q, setQ] = useState('');
  const [cat, setCat] = useState<'all' | 'name' | 'term'>('all');

  const sorted = useMemo(
    () => [...ALL].sort((a, b) => a.term.toLowerCase().localeCompare(b.term.toLowerCase())),
    [],
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return sorted.filter((t) => {
      if (cat !== 'all' && t.category !== cat) return false;
      if (!needle) return true;
      const hay = [
        t.term,
        t.translit?.zh_hant, t.translit?.zh_hans, t.translit?.ja,
        t.source_def,
        t.editor_note?.en, t.editor_note?.zh_hant, t.editor_note?.zh_hans, t.editor_note?.ja,
      ].filter(Boolean).join(' ').toLowerCase();
      return hay.includes(needle);
    });
  }, [q, cat, sorted]);

  return (
    <Layout title="Glossary" description="Oahspe glossary — terms, names, and transliterations in four languages">
      <main className="container margin-vert--lg">
        <h1>Glossary</h1>
        <p>
          {ALL.length} terms from Oahspe — the book's own definitions plus editor notes and
          sound-based transliterations in Traditional Chinese, Simplified Chinese, and Japanese.
        </p>

        <div className="glossary-controls">
          <input
            type="search"
            placeholder="Search terms, translations, definitions…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="glossary-search"
            aria-label="Search glossary"
          />
          <div className="glossary-filter">
            {(['all', 'name', 'term'] as const).map((c) => (
              <button
                key={c}
                className={`glossary-filter-btn ${cat === c ? 'active' : ''}`}
                onClick={() => setCat(c)}
              >
                {c === 'all' ? 'All' : c === 'name' ? 'Names' : 'Terms'}
              </button>
            ))}
          </div>
        </div>

        <p className="glossary-count">{filtered.length} shown</p>

        <div className="glossary-list">
          {filtered.map((t) => (
            <TermCard key={t.slug} t={t} />
          ))}
        </div>
      </main>
    </Layout>
  );
}
