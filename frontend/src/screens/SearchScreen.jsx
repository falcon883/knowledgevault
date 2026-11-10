import { useMemo, useState } from 'react';
import { getDocument, searchDocuments } from '../api.js';
import { excerptOf } from '../excerpt.js';
import {
  IconAlertCircle,
  IconArrowRight,
  IconFile,
  IconFileText,
  IconFolder,
  IconSearch,
} from '../icons.jsx';
import searchArt from '../assets/search-art.webp';

/**
 * KV-18 — Search screen, wired to the semantic search endpoint (POST /search).
 *
 * Plain-language query box returning ranked results with snippets, relevance
 * bars, tags, and an expandable preview per result.
 *
 * KV-31 — Search polish:
 *  - the tab no longer remounts (see App.jsx), so the query and results
 *    survive a trip to Capture or Browse;
 *  - the misleading "47% match" label is gone: each result shows a
 *    "Relevance" bar on a plain scale, normalised against the top result;
 *  - snippets render as-is instead of being force-wrapped in "…" — long
 *    ones are truncated at a word boundary with a single trailing "…";
 *  - expanding a result loads the document's real source excerpt
 *    (GET /documents/{id}), falling back to the summary when the record
 *    carries no text.
 */

const SNIPPET_MAX = 280;

// Nov 2026 theme — example queries and Browse shortcuts for the idle
// state. The category cards are real navigation, not decoration: each
// opens Browse with its type filter applied (see App's browseType).
// Browse distinguishes only PDF vs Text (kindOf in BrowseScreen), so
// notes and articles share one card rather than pretending they can
// be filtered apart.
const EXAMPLE_QUERIES = ['Project requirements', 'AI model notes', 'Cloud architecture'];

const CATEGORIES = [
  { type: 'all', title: 'All documents', sub: 'Everything in your vault', Icon: IconFolder, cls: 'all' },
  { type: 'PDF', title: 'PDFs', sub: 'Uploaded PDF files', Icon: IconFile, cls: 'pdf' },
  { type: 'Text', title: 'Notes & articles', sub: 'Saved text of both kinds', Icon: IconFileText, cls: 'text' },
];

function parseTags(doc) {
  return (doc.tags || '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
}

/**
 * Render the backend snippet honestly: whitespace-collapsed, shown as-is.
 * Only a long snippet gets an ellipsis, and only at the cut point.
 */
function formatSnippet(snippet) {
  if (!snippet) return '';
  const clean = String(snippet).replace(/\s+/g, ' ').trim();
  if (clean.length <= SNIPPET_MAX) return clean;
  const cut = clean.lastIndexOf(' ', SNIPPET_MAX);
  return `${clean.slice(0, cut > 0 ? cut : SNIPPET_MAX).trimEnd()}…`;
}

export default function SearchScreen({ onBrowseType } = {}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [state, setState] = useState('idle'); // idle | searching | ready | error
  const [error, setError] = useState('');
  const [searchedQuery, setSearchedQuery] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  // document_id -> { state: 'loading' | 'ready' | 'error', text }
  const [excerpts, setExcerpts] = useState({});

  // The top hit anchors the relevance scale; bars show each result's score
  // relative to it instead of implying an absolute "match" percentage.
  const topScore = useMemo(
    () => results.reduce((m, r) => Math.max(m, r.score || 0), 0),
    [results],
  );

  async function runSearch(e, override) {
    e?.preventDefault();
    const q = (override ?? query).trim();
    if (!q || state === 'searching') return;
    if (override != null) setQuery(override);
    setState('searching');
    setError('');
    setSelectedId(null);
    try {
      const data = await searchDocuments(q, 10);
      setResults(Array.isArray(data.results) ? data.results : []);
      setSearchedQuery(data.query || q);
      setState('ready');
    } catch (err) {
      setError(err.message || 'Search failed.');
      setState('error');
    }
  }

  function toggleSelect(r) {
    const id = r.document_id;
    const opening = selectedId !== id;
    setSelectedId(opening ? id : null);
    if (opening && excerpts[id] === undefined) {
      setExcerpts((m) => ({ ...m, [id]: { state: 'loading', text: '' } }));
      getDocument(id).then(
        (record) =>
          setExcerpts((m) => ({
            ...m,
            [id]: { state: 'ready', text: excerptOf(record) },
          })),
        () =>
          setExcerpts((m) => ({ ...m, [id]: { state: 'error', text: '' } })),
      );
    }
  }

  function previewFor(r) {
    const ex = excerpts[r.document_id];
    if (!ex || ex.state === 'loading') return 'Loading excerpt…';
    if (ex.state === 'ready' && ex.text) return ex.text;
    // Honest fallback: the search summary when the record carries no text.
    return r.summary || 'No preview available for this document yet.';
  }

  return (
    <section className="kv-card kv-search2" aria-labelledby="search-heading">
      <div className="kv-search2-head">
        <div>
          <h2 id="search-heading">Search your knowledge</h2>
          <p className="kv-lede">
            Describe what you want to find in plain language — results are ranked
            by meaning, not keywords.
          </p>
        </div>
        <img className="kv-search2-art" src={searchArt} alt="" aria-hidden="true" />
      </div>

      <form onSubmit={runSearch}>
        <label className="kv-label" htmlFor="kv-query">
          Describe what you want to find
        </label>
        <div className="kv-search2-bar">
          <span className="kv-search2-bar-icon">
            <IconSearch size={19} />
          </span>
          <input
            id="kv-query"
            className="kv-input kv-search2-input"
            type="text"
            placeholder="e.g. how do I find documents by meaning?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={500}
          />
          <button
            type="submit"
            className="kv-btn kv-search2-btn"
            disabled={!query.trim() || state === 'searching'}
          >
            {state === 'searching' ? (
              <>
                <span className="kv-spinner" aria-hidden="true" />
                Searching…
              </>
            ) : (
              <>
                Search
                <IconArrowRight size={16} />
              </>
            )}
          </button>
        </div>
      </form>

      <div className="kv-search2-try">
        <span className="kv-search2-try-label" id="kv-try-label">
          Try searching for:
        </span>
        <div className="kv-search2-chips" role="group" aria-labelledby="kv-try-label">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              type="button"
              className="kv-search2-chip"
              disabled={state === 'searching'}
              onClick={() => runSearch(null, q)}
            >
              <IconSearch size={14} />
              {q}
            </button>
          ))}
        </div>
      </div>

      <div aria-live="polite" style={{ marginTop: '1.25rem' }}>
        {state === 'idle' &&
          (onBrowseType ? (
            <div className="kv-search2-cats">
              {CATEGORIES.map((c) => {
                const CatIcon = c.Icon;
                return (
                  <button
                    key={c.type}
                    type="button"
                    className="kv-search2-cat"
                    onClick={() => onBrowseType(c.type)}
                  >
                    <span className={`kv-search2-cat-icon ${c.cls}`}>
                      <CatIcon size={22} />
                    </span>
                    <span className="kv-search2-cat-text">
                      <strong>{c.title}</strong>
                      <span>{c.sub}</span>
                    </span>
                    <IconArrowRight size={16} />
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="kv-empty">
              <span className="kv-empty-icon">
                <IconSearch size={34} />
              </span>
              <br />
              Enter a query to search your vault.
            </div>
          ))}

        {state === 'error' && (
          <div className="kv-status error" role="alert">
            <IconAlertCircle size={17} />
            <strong>Search failed.</strong> {error} Is the backend running?
          </div>
        )}

        {state === 'ready' && (
          <>
            <p className="kv-meta">
              {results.length === 0
                ? `No matches for “${searchedQuery}”.`
                : `${results.length} result${results.length === 1 ? '' : 's'} for “${searchedQuery}” · ranked by relevance`}
            </p>
            <div className="kv-doc-list">
              {results.map((r) => {
                const rel = topScore > 0 ? (r.score || 0) / topScore : 0;
                const snippet = formatSnippet(r.snippet);
                const expanded = selectedId === r.document_id;
                return (
                  <button
                    key={r.document_id}
                    type="button"
                    className={`kv-doc${expanded ? ' selected' : ''}`}
                    onClick={() => toggleSelect(r)}
                    aria-expanded={expanded}
                  >
                    <div
                      className="kv-row"
                      style={{ justifyContent: 'space-between' }}
                    >
                      <span className="kv-result-head">
                        <span
                          className={`kv-doc-icon small ${r.filename?.toLowerCase().endsWith('.pdf') ? 'pdf' : 'text'}`}
                        >
                          {r.filename?.toLowerCase().endsWith('.pdf') ? (
                            <IconFile size={16} />
                          ) : (
                            <IconFileText size={16} />
                          )}
                        </span>
                        <span className="kv-doc-title">{r.filename}</span>
                      </span>
                      <span
                        className="kv-relevance"
                        title="Relevance is relative to the top result, not an absolute match percentage."
                        aria-label={`Relevance ${Math.round(rel * 100)} out of 100, relative to the top result`}
                      >
                        <span className="kv-relevance-bar" aria-hidden="true">
                          <i style={{ width: `${Math.round(rel * 100)}%` }} />
                        </span>
                        <span className="kv-relevance-label">Relevance</span>
                      </span>
                    </div>
                    {snippet && <div className="kv-snippet">{snippet}</div>}
                    <div>
                      {parseTags(r).map((t) => (
                        <span key={t} className="kv-chip">
                          {t}
                        </span>
                      ))}
                    </div>
                    {expanded && (
                      <p
                        className="kv-doc-summary"
                        style={{ marginTop: '0.6rem' }}
                      >
                        {previewFor(r)}
                      </p>
                    )}
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
