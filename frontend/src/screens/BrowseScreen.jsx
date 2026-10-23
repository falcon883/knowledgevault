import { useEffect, useMemo, useState } from 'react';
import { deleteDocument, getDocument, listDocuments } from '../api.js';
import {
  IconAlertCircle,
  IconCheckCircle,
  IconClock,
  IconFile,
  IconFileText,
  IconFilter,
  IconFolder,
  IconSearch,
  IconTrash,
} from '../icons.jsx';

/**
 * KV-17 — Browse screen, wired to the live document list (GET /documents).
 *
 * Shows everything uploaded with a type filter, tag chips, newest-first
 * ordering, and a detail pane per document.
 *
 * KV-30 — Browse-view filters, completed: tag chips carry per-tag counts,
 * the sort is a real control (newest / oldest / name), the detail pane
 * loads the document's full record (GET /documents/{id}) and shows its
 * real source excerpt, and the pane closes when a filter change hides
 * the selected document.
 *
 * Layout — master-detail: the list sits on the left and the detail pane
 * lives in a sticky right-hand column (a vault overview sits there while
 * nothing is selected), so the excerpt is never buried at the bottom of
 * a long list.
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

/**
 * Pull the source excerpt out of a full document record. The detail
 * endpoint's text field name has varied across backend iterations, so
 * accept the known candidates and use the first non-empty string.
 */
function excerptOf(record) {
  if (!record) return '';
  let raw = [
    record.excerpt,
    record.text_preview,
    record.preview,
    record.snippet,
    record.text,
    record.content,
    record.extracted_text,
    record.raw_text,
    record.text_content,
    record.page_content,
    record.body,
    record.first_chunk,
    record.first_chunk_text,
  ].find((v) => typeof v === 'string' && v.trim());
  // Some backend shapes embed the chunks in the document record instead
  // of exposing a flat text field; fall back to the first chunk's text.
  if (!raw && Array.isArray(record.chunks) && record.chunks.length > 0) {
    const first = record.chunks[0];
    if (typeof first === 'string') {
      raw = first;
    } else if (first && typeof first === 'object') {
      raw = [first.text, first.content, first.snippet, first.page_content].find(
        (v) => typeof v === 'string' && v.trim(),
      );
    }
  }
  if (!raw) return '';
  const clean = raw.replace(/\s+/g, ' ').trim();
  return clean.length > 600 ? `${clean.slice(0, 600).trimEnd()}…` : clean;
}

export default function BrowseScreen() {
  const [docs, setDocs] = useState([]);
  const [state, setState] = useState('loading'); // loading | ready | error
  const [error, setError] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [tagFilter, setTagFilter] = useState(null);
  const [sortOrder, setSortOrder] = useState('newest');
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailState, setDetailState] = useState('idle'); // idle | loading | ready | error
  const [rowConfirmId, setRowConfirmId] = useState(null);
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

  const tagCounts = useMemo(() => {
    const counts = new Map();
    docs.forEach((d) =>
      parseTags(d).forEach((t) => counts.set(t, (counts.get(t) || 0) + 1)),
    );
    return counts;
  }, [docs]);

  const visible = useMemo(() => {
    const filtered = docs.filter((d) => {
      if (typeFilter !== 'all' && kindOf(d) !== typeFilter) return false;
      if (tagFilter && !parseTags(d).includes(tagFilter)) return false;
      return true;
    });
    return filtered.sort((a, b) => {
      if (sortOrder === 'name') {
        return (a.filename || '').localeCompare(b.filename || '');
      }
      const ta = a.uploaded_at ? Date.parse(a.uploaded_at) : 0;
      const tb = b.uploaded_at ? Date.parse(b.uploaded_at) : 0;
      return sortOrder === 'oldest' ? ta - tb : tb - ta;
    });
  }, [docs, typeFilter, tagFilter, sortOrder]);

  // Derived from the *visible* list on purpose: when a filter change
  // hides the selected document, the detail pane closes with it.
  const selected = visible.find((d) => d.id === selectedId) || null;
  const selectedKey = selected ? selected.id : null;

  useEffect(() => {
    if (selectedKey == null) {
      setDetail(null);
      setDetailState('idle');
      return;
    }
    let cancelled = false;
    setDetail(null);
    setDetailState('loading');
    getDocument(selectedKey)
      .then((data) => {
        if (cancelled) return;
        setDetail(data && typeof data === 'object' ? data : null);
        setDetailState('ready');
      })
      .catch(() => {
        if (cancelled) return;
        setDetailState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [selectedKey]);

  const excerpt = useMemo(() => excerptOf(detail), [detail]);

  // Vault totals for the overview panel shown while nothing is selected.
  const stats = useMemo(
    () => ({
      pdfs: docs.filter((d) => kindOf(d) === 'PDF').length,
      texts: docs.filter((d) => kindOf(d) === 'Text').length,
      chunks: docs.reduce((sum, d) => sum + (d.chunk_count || 0), 0),
      size: docs.reduce((sum, d) => sum + (d.size_bytes || 0), 0),
    }),
    [docs],
  );

  async function handleDelete(doc) {
    if (!doc || deleting) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await deleteDocument(doc.id);
      setDocs((prev) => prev.filter((d) => d.id !== doc.id));
      if (selectedId === doc.id) setSelectedId(null);
      setNotice(`Deleted "${doc.filename}".`);
      setRowConfirmId(null);
    } catch (err) {
      setDeleteError(err.message || 'Could not delete the document.');
    } finally {
      setDeleting(false);
    }
  }

  function selectDoc(id) {
    setSelectedId(selectedId === id ? null : id);
    setRowConfirmId(null);
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
          <IconAlertCircle size={17} />
          <strong>Could not load documents.</strong> {error} Is the backend
          running?
        </div>
      )}

      {state === 'ready' && (
        <>
          <div className="kv-row">
            <label className="kv-meta" htmlFor="kv-type-filter">
              <IconFilter size={14} /> Filter
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
            <label className="kv-meta" htmlFor="kv-sort">
              Sort
            </label>
            <select
              id="kv-sort"
              className="kv-select"
              style={{ width: 'auto' }}
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              aria-label="Sort documents"
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="name">Name (A–Z)</option>
            </select>
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
                  {t} <span className="kv-chip-count">{tagCounts.get(t)}</span>
                </button>
              ))}
            </div>
          )}

          <div className="kv-browse-layout">
            <div className="kv-browse-main">
          {visible.length === 0 ? (
            <div className="kv-empty">
              {docs.length === 0 ? (
                <>
                  <span className="kv-empty-icon">
                    <IconFolder size={34} />
                  </span>
                  <br />
                  No documents yet.
                  <br />
                  Head to the Capture tab to upload your first item.
                </>
              ) : (
                <>
                  <span className="kv-empty-icon">
                    <IconSearch size={34} />
                  </span>
                  <br />
                  No documents match the current filters.
                </>
              )}
            </div>
          ) : (
            <div className="kv-doc-list">
              {visible.map((d) => (
                <div
                  key={d.id}
                  className={`kv-doc${selectedId === d.id ? ' selected' : ''}`}
                >
                  <button
                    type="button"
                    className="kv-doc-main"
                    onClick={() => selectDoc(d.id)}
                    aria-expanded={selectedId === d.id}
                  >
                    <span
                      className={`kv-doc-icon ${kindOf(d) === 'PDF' ? 'pdf' : 'text'}`}
                    >
                      {kindOf(d) === 'PDF' ? (
                        <IconFile size={20} />
                      ) : (
                        <IconFileText size={20} />
                      )}
                    </span>
                    <span className="kv-doc-body">
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
                      <span className="kv-meta">
                        <IconClock size={13} /> {formatDate(d.uploaded_at)}
                      </span>
                    </span>
                  </button>
                  {rowConfirmId === d.id ? (
                    <div className="kv-doc-confirm" role="alert">
                      <span>Delete "{d.filename}"?</span>
                      <button
                        type="button"
                        className="kv-btn kv-btn-danger kv-btn-small"
                        disabled={deleting}
                        onClick={() => handleDelete(d)}
                      >
                        {deleting ? 'Deleting…' : 'Yes, delete'}
                      </button>
                      <button
                        type="button"
                        className="kv-btn kv-btn-secondary kv-btn-small"
                        disabled={deleting}
                        onClick={() => setRowConfirmId(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="kv-doc-delete"
                      aria-label={`Delete ${d.filename}`}
                      title={`Delete ${d.filename}`}
                      onClick={() => {
                        setRowConfirmId(d.id);
                        setDeleteError('');
                        setNotice('');
                      }}
                    >
                      <IconTrash size={16} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {deleteError && (
            <div
              className="kv-status error"
              role="alert"
              style={{ marginTop: '1rem' }}
            >
              <IconAlertCircle size={17} />
              <strong>Could not delete.</strong> {deleteError}
            </div>
          )}

          {notice && (
            <div
              className="kv-status ok"
              role="status"
              style={{ marginTop: '1rem' }}
            >
              <IconCheckCircle size={17} />
              {notice}
            </div>
          )}
            </div>

            <aside className="kv-detail-col">
          {selected ? (
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
              <div className="kv-excerpt">
                <span className="kv-meta">Source excerpt</span>
                {detailState === 'loading' && (
                  <p className="kv-meta" aria-live="polite">
                    Loading excerpt…
                  </p>
                )}
                {detailState === 'error' && (
                  <p className="kv-meta">
                    Could not load the excerpt for this document.
                  </p>
                )}
                {detailState === 'ready' &&
                  (excerpt ? (
                    <p className="kv-excerpt-text">{excerpt}</p>
                  ) : (
                    <p className="kv-meta">
                      No excerpt available for this document yet.
                    </p>
                  ))}
              </div>
            </div>
          ) : (
            <div className="kv-detail kv-overview">
              <h3>Vault overview</h3>
              <div className="kv-detail-grid">
                <div className="kv-detail-item">
                  <div className="k">Documents</div>
                  <div className="v">{docs.length}</div>
                </div>
                <div className="kv-detail-item">
                  <div className="k">PDFs</div>
                  <div className="v">{stats.pdfs}</div>
                </div>
                <div className="kv-detail-item">
                  <div className="k">Text files</div>
                  <div className="v">{stats.texts}</div>
                </div>
                <div className="kv-detail-item">
                  <div className="k">Chunks indexed</div>
                  <div className="v">{stats.chunks}</div>
                </div>
              </div>
              <p className="kv-meta">
                Select any document in the list and its details and source
                excerpt appear here. This panel stays in view while you
                scroll, however long the list gets.
              </p>
            </div>
          )}
            </aside>
          </div>
        </>
      )}
    </section>
  );
}
