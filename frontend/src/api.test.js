import {
  checkHealth,
  login,
  signup,
  listDocuments,
  searchDocuments,
} from './api.js';
import { getToken, setToken, setUnauthorizedHandler } from './auth.js';

// KV-39 — the API client owns three behaviours the screens rely on:
// the Bearer header on protected routes, the 401 session reset, and
// error objects carrying status/detail/code for readable messages.
function mockFetch(status, body) {
  return vi.fn(async () => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }));
}

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear();
    setUnauthorizedHandler(null);
    vi.restoreAllMocks();
  });

  it('checkHealth is true only when the backend reports ok', async () => {
    vi.stubGlobal('fetch', mockFetch(200, { status: 'ok' }));
    await expect(checkHealth()).resolves.toBe(true);

    vi.stubGlobal('fetch', mockFetch(200, { status: 'starting' }));
    await expect(checkHealth()).resolves.toBe(false);

    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down'); }));
    await expect(checkHealth()).resolves.toBe(false);
  });

  it('sends the stored token as a Bearer header on protected routes', async () => {
    setToken('tok-abc');
    const fetchMock = mockFetch(200, []);
    vi.stubGlobal('fetch', fetchMock);

    await listDocuments();

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.Authorization).toBe('Bearer tok-abc');
  });

  it('sends no Authorization header when signed out', async () => {
    const fetchMock = mockFetch(200, []);
    vi.stubGlobal('fetch', fetchMock);

    await listDocuments();

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.Authorization).toBeUndefined();
  });

  it('posts the query as JSON for search', async () => {
    const fetchMock = mockFetch(200, []);
    vi.stubGlobal('fetch', fetchMock);

    await searchDocuments('transformers', 5);

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain('/search');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ query: 'transformers', limit: 5 });
  });

  it('a 401 from a protected route clears the token and notifies the shell', async () => {
    setToken('expired');
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    vi.stubGlobal('fetch', mockFetch(401, { detail: 'token expired', code: 'token_expired' }));

    await expect(listDocuments()).rejects.toMatchObject({
      status: 401,
      detail: 'token expired',
      code: 'token_expired',
    });
    expect(getToken()).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('a 401 from login itself keeps the session and surfaces the error', async () => {
    // A failed login is a 401 too (invalid_credentials) — it must read
    // as a form error, not trigger the session reset.
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    vi.stubGlobal('fetch', mockFetch(401, { detail: 'Invalid credentials', code: 'invalid_credentials' }));

    await expect(login('a@b.c', 'wrong-password')).rejects.toMatchObject({
      status: 401,
      code: 'invalid_credentials',
    });
    expect(handler).not.toHaveBeenCalled();
  });

  it('signup returns the issued token payload', async () => {
    vi.stubGlobal('fetch', mockFetch(200, { access_token: 'new-tok' }));
    await expect(signup('a@b.c', 'long-enough')).resolves.toEqual({ access_token: 'new-tok' });
  });

  it('non-401 errors carry status and detail without clearing the token', async () => {
    setToken('tok-abc');
    vi.stubGlobal('fetch', mockFetch(500, { detail: 'boom' }));

    await expect(listDocuments()).rejects.toMatchObject({ status: 500, detail: 'boom' });
    expect(getToken()).toBe('tok-abc');
  });
});
