import React, { useMemo, useState } from 'react';
import Layout from '@theme/Layout';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import terms from '@site/../content/glossary/terms.json';

// terms.json schema (see docs/TRANSLATION_GUIDE.md §4a)
type LangKey = 'zh_hant' | 'zh_hans' | 'ja';
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

// Docusaurus locale → terms.json language key. 'en' has no transliteration column.
const LOCALE_TO_KEY: Record<string, LangKey | null> = {
  en: null,
  'zh-hant': 'zh_hant',
  'zh-hans': 'zh_hans',
  ja: 'ja',
};

const LABELS: Record<string, { translit: string; note: string; source: string; literal: string }> = {
  en:        { translit: 'Transliteration', note: "Editor's note", source: 'From the text (1882)', literal: 'Literal translation' },
  'zh-hant': { translit: '譯名',            note: '編者註',        source: '原文（1882）',            literal: '直譯' },
  'zh-hans': { translit: '译名',            note: '编者注',        source: '原文（1882）',            literal: '直译' },
  ja:        { translit: '訳名',            note: '訳者註',        source: '原典より（1882）',        literal: '逐語訳' },
};

function TermCard({ t, langKey, locale }: { t: Term; langKey: LangKey | null; locale: string }): React.ReactElement {
  const L = LABELS[locale] ?? LABELS.en;
  const tl = t.translit || {};
  const note = t.editor_note || {};
  const lit = t.source_def_literal || {};

  // Active-language values only (English page shows headword + English note).
  const translit = langKey ? tl[langKey] : null;
  const noteText = langKey ? note[langKey] : note.en;
  const litText = langKey ? (lit as Translit)[langKey] : null;

  return (
    <div id={t.slug} className="glossary-card">
      <div className="glossary-card-head">
        <span className="glossary-term">{t.term}</span>
        {translit && <span className="glossary-translit"><span>{translit}</span></span>}
        <span className={`glossary-cat glossary-cat-${t.category}`}>{t.category}</span>
      </div>

      {t.source_def && (
        <div className="glossary-source">
          <span className="glossary-label">{L.source}</span>
          <p>{t.source_def}</p>
          {litText && (
            <p className="glossary-source-lit"><em>{L.literal}:</em> {litText}</p>
          )}
        </div>
      )}

      {noteText && (
        <div className="glossary-note">
          <span className="glossary-label">{L.note}</span>
          <p>{noteText}</p>
        </div>
      )}

      {t.appears_in && t.appears_in.length > 0 && (
        <div className="glossary-appears">
          {t.appears_in.slice(0, 12).join(', ')}
          {t.appears_in.length > 12 ? ` … (+${t.appears_in.length - 12})` : ''}
        </div>
      )}
    </div>
  );
}

export default function GlossaryPage(): React.ReactElement {
  const { i18n } = useDocusaurusContext();
  const locale = i18n.currentLocale;
  const langKey = LOCALE_TO_KEY[locale] ?? null;

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
      // Search the headword + the ACTIVE language's fields only.
      const tl = t.translit || {};
      const note = t.editor_note || {};
      const hay = [
        t.term,
        langKey ? tl[langKey] : null,
        t.source_def,
        langKey ? note[langKey] : note.en,
      ].filter(Boolean).join(' ').toLowerCase();
      return hay.includes(needle);
    });
  }, [q, cat, sorted, langKey]);

  return (
    <Layout title="Glossary" description="Oahspe glossary — terms, names, and transliterations">
      <main className="container margin-vert--lg">
        <h1>Glossary</h1>
        <p>{ALL.length} terms from Oahspe — the book's own definitions, editor notes, and sound-based transliterations.</p>

        <div className="glossary-controls">
          <input
            type="search"
            placeholder="Search…"
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
            <TermCard key={t.slug} t={t} langKey={langKey} locale={locale} />
          ))}
        </div>
      </main>
    </Layout>
  );
}
