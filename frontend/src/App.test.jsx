import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import App from './App.jsx';
import { setToken } from './auth.js';
import { listDocuments } from './api.js';

// KV-39 — shell behaviour: the KV-43 sign-in gate and the KV-40 hash
// routing (tab survives refresh, hash picks the tab, sign-out returns
// to the gate). Screen data calls are mocked at the api module.
vi.mock('./api.js', () => ({
  checkHealth: vi.fn(async () => true),
  login: vi.fn(),
  signup: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  changePassword: vi.fn(),
  uploadDocument: vi.fn(),
  listDocuments: vi.fn(async () => []),
  getDocument: vi.fn(),
  searchDocuments: vi.fn(async () => []),
  deleteDocument: vi.fn(),
}));

function navButton(name) {
  const nav = screen.getByRole('navigation', { name: 'Primary' });
  return within(nav).getByRole('button', { name });
}

describe('App shell', () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = '';
    window.history.pushState({}, '', '/');
    vi.clearAllMocks();
  });

  it('opens the reset screen when the URL carries a reset token (KV-59)', () => {
    window.history.pushState({}, '', '/?reset_token=tok-abc');
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument();
  });

  it('shows the sign-in gate when no token is stored', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument();
  });

  it('shows the workspace with Capture active by default when signed in', () => {
    setToken('tok');
    render(<App />);
    expect(navButton('Capture')).toHaveAttribute('aria-pressed', 'true');
    expect(navButton('Browse')).toHaveAttribute('aria-pressed', 'false');
    expect(navButton('Search')).toHaveAttribute('aria-pressed', 'false');
  });

  it('opens on the tab named in the URL hash (KV-40)', () => {
    setToken('tok');
    window.location.hash = '#/browse';
    render(<App />);
    expect(navButton('Browse')).toHaveAttribute('aria-pressed', 'true');
  });

  it('switching tabs updates the pressed state and the hash', () => {
    setToken('tok');
    render(<App />);
    fireEvent.click(navButton('Search'));
    expect(navButton('Search')).toHaveAttribute('aria-pressed', 'true');
    expect(window.location.hash).toBe('#/search');
  });

  it('sign out clears the session and returns to the gate', () => {
    setToken('tok');
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument();
  });

  it('re-loads the document list each time Browse is opened (KV-32)', async () => {
    // Found by the end-to-end tests: Browse used to show the list it loaded
    // before an upload until the page was refreshed.
    setToken('tok');
    render(<App />);
    await waitFor(() => expect(listDocuments).toHaveBeenCalledTimes(1));

    fireEvent.click(navButton('Browse'));
    await waitFor(() => expect(listDocuments).toHaveBeenCalledTimes(2));

    fireEvent.click(navButton('Search'));
    fireEvent.click(navButton('Browse'));
    await waitFor(() => expect(listDocuments).toHaveBeenCalledTimes(3));
  });

  it('opens the change password panel from the top bar (KV-62)', () => {
    setToken('tok');
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(screen.getByLabelText('Current password')).toBeInTheDocument();
    expect(screen.getByLabelText('New password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm new password')).toBeInTheDocument();
  });
});
