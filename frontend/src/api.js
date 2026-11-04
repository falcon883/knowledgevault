/**
 * KnowledgeVault API client.
 *
 * Talks to the FastAPI backend (KV-13/14/15/16/21). The base URL defaults to
 * the local dev server and can be overridden with VITE_API_URL for deployed
 * environments.
 *
 * KV-43: every route except /health requires the account token issued by
 * POST /auth/signup or POST /auth/login. The token rides on each request
 * as `Authorization: Bearer <token>`; a 401 from a protected route clears
 * the token and notifies the app shell, which returns the user to the
 * sign-in screen.
 */

import { getToken, clearToken, notifyUnauthorized } from './auth.js';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function handleResponse(res, action, { isAuthCall = false } = {}) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail;
    // A 401 from a protected route means the token is missing, expired
    // (24h lifetime) or invalid: drop it and send the user to sign in.
    // Auth calls themselves are exempt - a failed login is a 401 too
    // (invalid_credentials) and must surface as a form error instead.
    if (res.status === 401 && !isAuthCall) {
      clearToken();
      notifyUnauthorized();
    }
    const err = new Error(
      typeof detail === 'string'
        ? detail
        : `${action} failed (HTTP ${res.status})`,
    );
    // KV-29: carry the HTTP status and the raw detail (a string, or an
    // object such as the KV-25 duplicate payload with id/filename) so
    // screens can show a specific, readable message per failure case.
    // KV-43: also carry the backend's machine-readable error code
    // (invalid_credentials, email_taken, weak_password, ...).
    err.status = res.status;
    err.detail = detail;
    err.code = body?.code;
    throw err;
  }
  return res.json();
}

/**
 * Create an account (KV-43). Returns { access_token, ... } on success;
 * the caller stores the token. Password must be 8+ characters.
 */
export async function signup(email, password) {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(res, 'Sign up', { isAuthCall: true });
}

/**
 * Sign in to an existing account (KV-43). Returns { access_token, ... }
 * on success; the caller stores the token.
 */
export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(res, 'Sign in', { isAuthCall: true });
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
  const res = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  return handleResponse(res, 'Upload');
}

/**
 * List uploaded documents, most recent first (KV-17).
 */
export async function listDocuments() {
  const res = await fetch(`${API_BASE}/documents`, {
    headers: authHeaders(),
  });
  return handleResponse(res, 'Could not load documents');
}

/**
 * Fetch one document's full record (KV-30). The list endpoint returns
 * summary fields only, so the Browse detail pane loads the full record
 * on selection to show the real source excerpt.
 */
export async function getDocument(id) {
  const res = await fetch(`${API_BASE}/documents/${id}`, {
    headers: authHeaders(),
  });
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
    headers: authHeaders({ 'Content-Type': 'application/json' }),
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
    headers: authHeaders(),
  });
  return handleResponse(res, 'Delete');
}

/**
 * Backend liveness check for the header status indicator. /health is the
 * one route that stays open without a token.
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
