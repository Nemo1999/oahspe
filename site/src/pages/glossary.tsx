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

const LABELS: Record<string, {
  translit: string; sourceHdr: string; sourceSub: string; editorHdr: string; editorSub: string;
  literal: string; more: string; less: string; appears: string; search: string;
}> = {
  en:        { translit: 'Transliteration', sourceHdr: '📖 From the original text',  sourceSub: "Oahspe's own glossary (1882) — verbatim", editorHdr: '✎ Editor’s note',   editorSub: 'Added interpretation — not part of the original', literal: 'Literal translation', more: 'Show more', less: 'Show less', appears: 'Appears in', search: 'Search occurrences' },
  'zh-hant': { translit: '譯名',            sourceHdr: '📖 原書內容',                sourceSub: '奧阿斯佩原書詞彙表（1882）——原文照錄',   editorHdr: '✎ 編者註',        editorSub: '編者補充的詮釋——非原書內容',            literal: '直譯',              more: '展開',      less: '收合',      appears: '出現於', search: '搜尋經文' },
  'zh-hans': { translit: '译名',            sourceHdr: '📖 原书内容',                sourceSub: '奥阿斯佩原书词汇表（1882）——原文照录',   editorHdr: '✎ 编者注',        editorSub: '编者补充的诠释——非原书内容',            literal: '直译',              more: '展开',      less: '收合',      appears: '出现于', search: '搜索经文' },
  ja:        { translit: '訳名',            sourceHdr: '📖 原典より',                sourceSub: 'オアスペ原典の用語集（1882）——原文のまま', editorHdr: '✎ 訳者註',        editorSub: '編者による解釈——非原書内容',       literal: '逐語訳',            more: 'もっと見る', less: '閉じる',    appears: '出典', search: '経文を検索' },
};

const CLAMP_CHARS = 240; // collapse text longer than this

function ClampToggle({ text, more, less }: { text: string; more: string; less: string }): React.ReactElement {
  const [open, setOpen] = useState(false);
  if (text.length <= CLAMP_CHARS) return <p className="glossary-text">{text}</p>;
  return (
    <div>
      <p className={`glossary-text ${open ? '' : 'glossary-clamped'}`}>{text}</p>
      <button className="glossary-more-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? less : more}
      </button>
    </div>
  );
}

function TermCard({ t, langKey, locale }: { t: Term; langKey: LangKey | null; locale: string }): React.ReactElement {
  const L = LABELS[locale] ?? LABELS.en;
  const tl = t.translit || {};
  const note = t.editor_note || {};
  const lit = t.source_def_literal || {};

  const translit = langKey ? tl[langKey] : null;
  const noteText = langKey ? note[langKey] : note.en;
  const litText = langKey ? (lit as Translit)[langKey] : null;

  return (
    <div id={t.slug} className="glossary-card">
      <div className="glossary-card-head">
        <span className="glossary-term">{t.term}</span>
        {translit && <span className="glossary-translit">{translit}</span>}
        <span className={`glossary-cat glossary-cat-${t.category}`}>{t.category}</span>
      </div>
        <a className="glossary-search-occurrences" href={`${locale === 'en' ? '/oahspe' : `/oahspe/${locale}`}/search?q=${encodeURIComponent(translit || t.term)}`}>{L.search}</a>

      {t.source_def && (
        <section className="glossary-source">
          <div className="glossary-prov-hdr">
            <span className="glossary-prov-title">{L.sourceHdr}</span>
            <span className="glossary-prov-sub">{L.sourceSub}</span>
          </div>
          <ClampToggle text={t.source_def} more={L.more} less={L.less} />
          {litText && <p className="glossary-source-lit"><em>{L.literal}:</em> {litText}</p>}
        </section>
      )}

      {noteText && (
        <section className="glossary-note">
          <div className="glossary-prov-hdr">
            <span className="glossary-prov-title">{L.editorHdr}</span>
            <span className="glossary-prov-sub">{L.editorSub}</span>
          </div>
          <ClampToggle text={noteText} more={L.more} less={L.less} />
        </section>
      )}

      {t.appears_in && t.appears_in.length > 0 && (
        <div className="glossary-appears">
          <em>{L.appears}:</em>{' '}
          {t.appears_in.slice(0, 12).map((vid, idx) => {
            // verse id "jehovih.1.3" → /oahspe[/<locale>]/<book>/<book.chapter>#<verseid>
            const parts = vid.split('.');
            const book = parts[0];
            const chap = parts.slice(0, 2).join('.');
            const base = locale === 'en' ? '/oahspe' : `/oahspe/${locale}`;
            const href = `${base}/${book}/${chap}#${vid}`;
            return (
              <React.Fragment key={vid}>
                {idx > 0 && ', '}
                <a className="glossary-backlink" href={href}>{vid}</a>
              </React.Fragment>
            );
          })}
          {t.appears_in.length > 12 ? ` … (+${t.appears_in.length - 12})` : ''}
        </div>
      )}
    </div>
  );
}

export default function GlossaryPage(): React.ReactElement {
  const { i18n } = useDocusaurusContext();
  const locale = i18n.currentLocale;

  const [q, setQ] = useState('');
  const [cat, setCat] = useState<'all' | 'name' | 'term'>('all');
  // View language: defaults to the site locale, but the reader can switch it here
  // without changing the whole-site locale.
  const [viewLoc, setViewLoc] = useState<string>(locale);
  const langKey = LOCALE_TO_KEY[viewLoc] ?? null;

  const VIEW_LANGS: Array<{ code: string; label: string }> = [
    { code: 'en', label: 'EN' },
    { code: 'zh-hant', label: '繁中' },
    { code: 'zh-hans', label: '简中' },
    { code: 'ja', label: '日' },
  ];

  const sorted = useMemo(
    () => [...ALL].sort((a, b) => a.term.toLowerCase().localeCompare(b.term.toLowerCase())),
    [],
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return sorted.filter((t) => {
      if (cat !== 'all' && t.category !== cat) return false;
      if (!needle) return true;
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
          <div className="glossary-langswitch" role="group" aria-label="View language">
            {VIEW_LANGS.map((l) => (
              <button
                key={l.code}
                className={`glossary-lang-btn ${viewLoc === l.code ? 'active' : ''}`}
                onClick={() => setViewLoc(l.code)}
                aria-pressed={viewLoc === l.code}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>

        <p className="glossary-count">{filtered.length} shown</p>

        <div className="glossary-list">
          {filtered.map((t) => (
            <TermCard key={t.slug} t={t} langKey={langKey} locale={viewLoc} />
          ))}
        </div>
      </main>
    </Layout>
  );
}
