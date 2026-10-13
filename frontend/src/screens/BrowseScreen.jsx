import { useEffect, useMemo, useState } from 'react';
import { deleteDocument, listDocuments } from '../api.js';

/**
 * KV-17 — Browse screen, wired to the live document list (GET /documents).
 *
 * Shows everything uploaded with a type filter, tag chips, newest-first
 * ordering, and a detail pane per document.
 */

function kindOf(doc) {
  return doc.content_type === 'application/pdf' ? 'PDF' : 'Text';
}

function parseTags(doc) {
  return (doc.tags || '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
}

function formatBytes(n) {
  if (n == null) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export default function BrowseScreen() {
  const [docs, setDocs] = useState([]);
  const [state, setState] = useState('loading'); // loading | ready | error
  const [error, setError] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [tagFilter, setTagFilter] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState('');
  const [deleteError, setDeleteError] = useState('');

  useEffect(() => {
    let cancelled = false;
    listDocuments()
      .then((data) => {
        if (cancelled) return;
        setDocs(Array.isArray(data) ? data : []);
        setState('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Could not load documents.');
        setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const allTags = useMemo(() => {
    const set = new Set();
    docs.forEach((d) => parseTags(d).forEach((t) => set.add(t)));
    return [...set].sort();
  }, [docs]);

  const visible = useMemo(
    () =>
      docs.filter((d) => {
        if (typeFilter !== 'all' && kindOf(d) !== typeFilter) return false;
        if (tagFilter && !parseTags(d).includes(tagFilter)) return false;
        return true;
      }),
    [docs, typeFilter, tagFilter],
  );

  const selected = docs.find((d) => d.id === selectedId) || null;

  async function handleDelete() {
    if (!selected || deleting) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await deleteDocument(selected.id);
      setDocs((prev) => prev.filter((d) => d.id !== selected.id));
      setNotice(`Deleted "${selected.filename}".`);
      setSelectedId(null);
      setConfirmingDelete(false);
    } catch (err) {
      setDeleteError(err.message || 'Could not delete the document.');
    } finally {
      setDeleting(false);
    }
  }

  function selectDoc(id) {
    setSelectedId(selectedId === id ? null : id);
    setConfirmingDelete(false);
    setDeleteError('');
    setNotice('');
  }

  return (
    <section className="kv-card" aria-labelledby="browse-heading">
      <h2 id="browse-heading">Your documents</h2>
      <p className="kv-lede">
        {state === 'ready'
          ? `${docs.length} saved item${docs.length === 1 ? '' : 's'}`
          : 'Everything you have uploaded to your knowledge base.'}
      </p>

      {state === 'loading' && (
        <p className="kv-meta" aria-live="polite">
          <span className="kv-spinner" aria-hidden="true" />
          Loading your documents…
        </p>
      )}

      {state === 'error' && (
        <div className="kv-status error" role="alert">
          <strong>Could not load documents.</strong> {error} Is the backend
          running?
        </div>
      )}

      {state === 'ready' && (
        <>
          <div className="kv-row">
            <label className="kv-meta" htmlFor="kv-type-filter">
              Filter
            </label>
            <select
              id="kv-type-filter"
              className="kv-select"
              style={{ width: 'auto' }}
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              aria-label="Filter document type"
            >
              <option value="all">All types</option>
              <option value="PDF">PDF</option>
              <option value="Text">Text</option>
            </select>
            <span className="kv-meta">Newest first</span>
          </div>

          {allTags.length > 0 && (
            <div style={{ marginTop: '0.75rem' }} aria-label="Filter by tag">
              {allTags.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`kv-chip clickable${tagFilter === t ? ' active' : ''}`}
                  aria-pressed={tagFilter === t}
                  onClick={() => setTagFilter(tagFilter === t ? null : t)}
                >
                  {t}
                </button>
              ))}
            </div>
          )}

          {visible.length === 0 ? (
            <div className="kv-empty">
              {docs.length === 0 ? (
                <>
                  No documents yet.
                  <br />
                  Head to the Capture tab to upload your first item.
                </>
              ) : (
                'No documents match the current filters.'
              )}
            </div>
          ) : (
            <div className="kv-doc-list">
              {visible.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  className={`kv-doc${selectedId === d.id ? ' selected' : ''}`}
                  onClick={() => selectDoc(d.id)}
                  aria-expanded={selectedId === d.id}
                >
                  <span className="kv-kind-badge">{kindOf(d)}</span>
                  <span className="kv-doc-title">{d.filename}</span>
                  {d.summary && (
                    <p className="kv-doc-summary">{d.summary}</p>
                  )}
                  <div>
                    {parseTags(d).map((t) => (
                      <span key={t} className="kv-chip">
                        {t}
                      </span>
                    ))}
                  </div>
                  <span className="kv-meta">{formatDate(d.uploaded_at)}</span>
                </button>
              ))}
            </div>
          )}

          {selected && (
            <div className="kv-detail" aria-live="polite">
              <h3>{selected.filename}</h3>
              <div className="kv-detail-grid">
                <div className="kv-detail-item">
                  <div className="k">Type</div>
                  <div className="v">{kindOf(selected)}</div>
                </div>
                <div className="kv-detail-item">
                  <div className="k">Uploaded</div>
                  <div className="v">{formatDate(selected.uploaded_at)}</div>
                </div>
                <div className="kv-detail-item">
                  <div className="k">Size</div>
                  <div className="v">{formatBytes(selected.size_bytes)}</div>
                </div>
                <div className="kv-detail-item">
                  <div className="k">Chunks</div>
                  <div className="v">{selected.chunk_count ?? '—'}</div>
                </div>
              </div>
              {parseTags(selected).length > 0 && (
                <div style={{ marginBottom: '0.75rem' }}>
                  {parseTags(selected).map((t) => (
                    <span key={t} className="kv-chip">
                      {t}
                    </span>
                  ))}
                </div>
              )}
              {selected.summary && <p>{selected.summary}</p>}
              <span className="kv-meta">Source excerpt preview</span>

              <div style={{ marginTop: '1rem' }}>
                {!confirmingDelete ? (
                  <button
                    type="button"
                    className="kv-btn kv-btn-danger"
                    style={{ marginTop: 0 }}
                    onClick={() => {
                      setConfirmingDelete(true);
                      setDeleteError('');
                    }}
                  >
                    Delete document
                  </button>
                ) : (
                  <div role="alert">
                    <p className="kv-meta" style={{ marginBottom: '0.5rem' }}>
                      Delete "{selected.filename}"? This removes it and its
                      indexed content permanently.
                    </p>
                    <div className="kv-row">
                      <button
                        type="button"
                        className="kv-btn kv-btn-danger"
                        style={{ marginTop: 0 }}
                        disabled={deleting}
                        onClick={handleDelete}
                      >
                        {deleting ? 'Deleting…' : 'Yes, delete'}
                      </button>
                      <button
                        type="button"
                        className="kv-btn kv-btn-secondary"
                        style={{ marginTop: 0 }}
                        disabled={deleting}
                        onClick={() => setConfirmingDelete(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
                {deleteError && (
                  <div
                    className="kv-status error"
                    role="alert"
                    style={{ marginTop: '0.75rem' }}
                  >
                    <strong>Could not delete.</strong> {deleteError}
                  </div>
                )}
              </div>
            </div>
          )}

          {notice && (
            <div
              className="kv-status ok"
              role="status"
              style={{ marginTop: '1rem' }}
            >
              {notice}
            </div>
          )}
        </>
      )}
    </section>
  );
}
