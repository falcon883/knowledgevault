/**
 * KnowledgeVault auth session (KV-43).
 *
 * The backend issues a 24-hour access token from POST /auth/signup and
 * POST /auth/login. The token is kept in localStorage so a page refresh
 * does not sign the user out, and is cleared on sign out or whenever the
 * backend rejects it with a 401.
 *
 * api.js cannot navigate the UI back to the sign-in screen by itself, so
 * App registers an unauthorized handler here; api.js invokes it on a 401
 * from any protected route.
 */

const TOKEN_KEY = 'kv_access_token';

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage unavailable (private mode); the session simply will not
    // survive a refresh.
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to clear.
  }
}

let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized() {
  if (unauthorizedHandler) unauthorizedHandler();
}
