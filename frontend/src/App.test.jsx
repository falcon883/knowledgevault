import { render, screen, fireEvent, within } from '@testing-library/react';
import App from './App.jsx';
import { setToken } from './auth.js';

// KV-39 — shell behaviour: the KV-43 sign-in gate and the KV-40 hash
// routing (tab survives refresh, hash picks the tab, sign-out returns
// to the gate). Screen data calls are mocked at the api module.
vi.mock('./api.js', () => ({
  checkHealth: vi.fn(async () => true),
  login: vi.fn(),
  signup: vi.fn(),
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
    vi.clearAllMocks();
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
});
