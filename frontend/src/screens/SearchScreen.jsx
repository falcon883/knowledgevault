import { useState } from 'react';
import { searchDocuments } from '../api.js';

/**
 * KV-18 — Search screen, wired to the semantic search endpoint (POST /search).
 *
 * Plain-language query box returning ranked results with snippets, relevance
 * scores, tags, and an expandable detail per result.
 */

function parseTags(doc) {
  return (doc.tags || '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
}

export default function SearchScreen() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [state, setState] = useState('idle'); // idle | searching | ready | error
  const [error, setError] = useState('');
  const [searchedQuery, setSearchedQuery] = useState('');
  const [selectedId, setSelectedId] = useState(null);

  async function runSearch(e) {
    e?.preventDefault();
    const q = query.trim();
    if (!q || state === 'searching') return;
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

  return (
    <section className="kv-card" aria-labelledby="search-heading">
      <h2 id="search-heading">Search your knowledge</h2>
      <p className="kv-lede">
        Describe what you want to find in plain language — results are ranked
        by meaning, not keywords.
      </p>

      <form onSubmit={runSearch}>
        <label className="kv-label" htmlFor="kv-query">
          Describe what you want to find
        </label>
        <div className="kv-search-row">
          <input
            id="kv-query"
            className="kv-input"
            type="text"
            placeholder="e.g. how do I find documents by meaning?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={500}
          />
          <button
            type="submit"
            className="kv-btn"
            disabled={!query.trim() || state === 'searching'}
          >
            {state === 'searching' ? (
              <>
                <span className="kv-spinner" aria-hidden="true" />
                Searching…
              </>
            ) : (
              'Search'
            )}
          </button>
        </div>
      </form>

      <div aria-live="polite" style={{ marginTop: '1.25rem' }}>
        {state === 'idle' && (
          <div className="kv-empty">Enter a query to search your vault.</div>
        )}

        {state === 'error' && (
          <div className="kv-status error" role="alert">
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
              {results.map((r) => (
                <button
                  key={r.document_id}
                  type="button"
                  className={`kv-doc${selectedId === r.document_id ? ' selected' : ''}`}
                  onClick={() =>
                    setSelectedId(
                      selectedId === r.document_id ? null : r.document_id,
                    )
                  }
                  aria-expanded={selectedId === r.document_id}
                >
                  <div className="kv-row" style={{ justifyContent: 'space-between' }}>
                    <span className="kv-doc-title">{r.filename}</span>
                    <span className="kv-score">
                      {Math.round((r.score || 0) * 100)}% match
                    </span>
                  </div>
                  {r.snippet && <div className="kv-snippet">…{r.snippet}…</div>}
                  <div>
                    {parseTags(r).map((t) => (
                      <span key={t} className="kv-chip">
                        {t}
                      </span>
                    ))}
                  </div>
                  {selectedId === r.document_id && r.summary && (
                    <p className="kv-doc-summary" style={{ marginTop: '0.6rem' }}>
                      {r.summary}
                    </p>
                  )}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
