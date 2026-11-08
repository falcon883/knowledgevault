import {
  getToken,
  setToken,
  clearToken,
  setUnauthorizedHandler,
  notifyUnauthorized,
} from './auth.js';

// KV-39 — the token session is the app's sign-in state: a refresh must
// keep the user signed in, and a 401 anywhere must reach the shell.
describe('auth session', () => {
  beforeEach(() => {
    localStorage.clear();
    setUnauthorizedHandler(null);
  });

  it('starts signed out', () => {
    expect(getToken()).toBeNull();
  });

  it('stores and returns the token', () => {
    setToken('tok-123');
    expect(getToken()).toBe('tok-123');
  });

  it('clears the token on sign out', () => {
    setToken('tok-123');
    clearToken();
    expect(getToken()).toBeNull();
  });

  it('invokes the registered unauthorized handler', () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    notifyUnauthorized();
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('does not throw when no handler is registered', () => {
    expect(() => notifyUnauthorized()).not.toThrow();
  });
});
