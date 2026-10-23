/**
 * KnowledgeVault API client.
 *
 * Talks to the FastAPI backend (KV-13/14/15/16/21). The base URL defaults to
 * the local dev server and can be overridden with VITE_API_URL for deployed
 * environments.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function handleResponse(res, action) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail;
    const err = new Error(
      typeof detail === 'string'
        ? detail
        : `${action} failed (HTTP ${res.status})`,
    );
    // KV-29: carry the HTTP status and the raw detail (a string, or an
    // object such as the KV-25 duplicate payload with id/filename) so
    // screens can show a specific, readable message per failure case.
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return res.json();
}

/**
 * Upload a document (KV-19). Accepts a File/Blob; the backend supports
 * application/pdf and text/plain. Notes and article text are uploaded as
 * text/plain files. Returns the saved document record including tags and
 * summary once enrichment completes.
 */
export async function uploadDocument(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
  return handleResponse(res, 'Upload');
}

/**
 * List uploaded documents, most recent first (KV-17).
 */
export async function listDocuments() {
  const res = await fetch(`${API_BASE}/documents`);
  return handleResponse(res, 'Could not load documents');
}

/**
 * Fetch one document's full record (KV-30). The list endpoint returns
 * summary fields only, so the Browse detail pane loads the full record
 * on selection to show the real source excerpt.
 */
export async function getDocument(id) {
  const res = await fetch(`${API_BASE}/documents/${id}`);
  return handleResponse(res, 'Could not load document');
}

/**
 * Semantic search over the vault (KV-18). Returns ranked results, one per
 * document, each with its best-matching snippet, similarity score, tags and
 * summary.
 */
export async function searchDocuments(query, limit = 10) {
  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit }),
  });
  return handleResponse(res, 'Search');
}

/**
 * Delete a document and everything derived from it (KV-22). The backend
 * removes the document record plus its chunks and embeddings (cascade),
 * so it disappears from /documents and /search alike.
 */
export async function deleteDocument(id) {
  const res = await fetch(`${API_BASE}/documents/${id}`, {
    method: 'DELETE',
  });
  return handleResponse(res, 'Delete');
}

/**
 * Backend liveness check for the header status indicator.
 */
export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}
