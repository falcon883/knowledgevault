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
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `${action} failed (HTTP ${res.status})`);
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
