import { useEffect, useState } from 'react';
import { checkHealth } from './api.js';
import { getToken, clearToken, setUnauthorizedHandler } from './auth.js';
import AuthScreen from './screens/AuthScreen.jsx';
import UploadScreen from './screens/UploadScreen.jsx';
import BrowseScreen from './screens/BrowseScreen.jsx';
import SearchScreen from './screens/SearchScreen.jsx';
import { IconBookOpen, IconFolder, IconSearch, IconUploadCloud } from './icons.jsx';
import './app.css';

/**
 * KnowledgeVault app shell.
 *
 * Wireframe layout (slim top bar over a left sidebar nav) in the app's
 * white-and-blue theme: brand left in the top bar, archive label and
 * backend status right; the three screens stack as sidebar buttons.
 *
 *  - KV-19 Capture (upload wired to POST /upload)
 *  - KV-17 Browse (document list wired to GET /documents)
 *  - KV-18 Search (semantic search wired to POST /search)
 *
 * KV-31 — the screens stay mounted while hidden (no more remount on tab
 * switch), so a search query and its results survive a trip to another
 * tab. Browse still refreshes its list whenever it is navigated to from
 * the upload flow, via the browseRefresh signal.
 *
 * KV-43 — the backend requires an account token on every route except
 * /health, so the shell gates on sign-in: with no stored token the auth
 * screen replaces the workspace, and any 401 from the API (expired or
 * invalid token) clears the token and returns the user to sign-in.
 */

const TABS = [
  { id: 'capture', label: 'Capture', Screen: UploadScreen, Icon: IconUploadCloud },
  { id: 'browse', label: 'Browse', Screen: BrowseScreen, Icon: IconFolder },
  { id: 'search', label: 'Search', Screen: SearchScreen, Icon: IconSearch },
];

function App() {
  const [tab, setTab] = useState('search');
  const [backendOk, setBackendOk] = useState(null);
  const [signedIn, setSignedIn] = useState(() => Boolean(getToken()));
  // Bumped every time Browse is navigated to from the upload flow, so its
  // list refreshes even though the screen no longer remounts on tab switch.
  const [browseRefresh, setBrowseRefresh] = useState(0);

  // api.js calls this when a protected route answers 401.
  useEffect(() => {
    setUnauthorizedHandler(() => setSignedIn(false));
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    checkHealth().then((ok) => {
      if (!cancelled) setBackendOk(ok);
    });
    return () => {
      cancelled = true;
    };
  }, [tab, signedIn]);

  function navigate(next) {
    if (next === 'browse') setBrowseRefresh((n) => n + 1);
    setTab(next);
  }

  function signOut() {
    clearToken();
    setSignedIn(false);
  }

  return (
    <div className="kv-shell">
      <header className="kv-topbar">
        <div className="kv-brand">
          <span className="kv-brand-mark">
            <IconBookOpen size={20} />
          </span>
          KnowledgeVault
        </div>
        <div className="kv-top-right">
          <span className="kv-archive">Personal archive</span>
          <span
            className={`kv-status-dot${backendOk == null ? '' : backendOk ? ' ok' : ' down'}`}
            title="Backend API status"
          >
            <i aria-hidden="true" />
            {backendOk == null
              ? 'checking backend…'
              : backendOk
                ? 'backend connected'
                : 'backend not running'}
          </span>
          {signedIn && (
            <button
              type="button"
              className="kv-btn kv-btn-secondary kv-btn-small"
              onClick={signOut}
            >
              Sign out
            </button>
          )}
        </div>
      </header>

      {signedIn ? (
        <div className="kv-body">
          <nav className="kv-nav" aria-label="Primary">
            {TABS.map((t) => {
              const TabIcon = t.Icon;
              return (
                <button
                  key={t.id}
                  type="button"
                  className="kv-tab"
                  aria-pressed={tab === t.id}
                  onClick={() => setTab(t.id)}
                >
                  <TabIcon size={17} />
                  {t.label}
                </button>
              );
            })}
          </nav>

          <main className="kv-main">
            {TABS.map((t) => {
              const Screen = t.Screen;
              const isActive = tab === t.id;
              return (
                <div
                  key={t.id}
                  className="kv-screen"
                  hidden={!isActive}
                  aria-hidden={!isActive}
                >
                  <Screen
                    onNavigate={navigate}
                    refreshSignal={t.id === 'browse' ? browseRefresh : undefined}
                  />
                </div>
              );
            })}
          </main>
        </div>
      ) : (
        <main className="kv-main kv-main-auth">
          <AuthScreen onAuthenticated={() => setSignedIn(true)} />
        </main>
      )}
    </div>
  );
}

export default App;
