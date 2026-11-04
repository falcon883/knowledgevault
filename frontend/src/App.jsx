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
 *
 * KV-40 — the active tab is mirrored in the URL hash (#/capture,
 * #/browse, #/search), so a refresh keeps the tab and the browser's
 * Back/Forward buttons move between tabs. Hash routing is deliberate:
 * the app will be statically hosted (S3/CloudFront), where history-API
 * rewrites are not guaranteed. The gate is unaffected: a signed-out
 * user sees the auth screen whatever the hash says, and the tab named
 * in the hash is the one shown after sign-in.
 */

const TABS = [
  { id: 'capture', label: 'Capture', Screen: UploadScreen, Icon: IconUploadCloud },
  { id: 'browse', label: 'Browse', Screen: BrowseScreen, Icon: IconFolder },
  { id: 'search', label: 'Search', Screen: SearchScreen, Icon: IconSearch },
];

// KV-40 — hash <-> tab mapping. The hash looks like "#/browse"; anything
// else (empty, unknown tab) is treated as "no tab named" by tabFromHash.
const TAB_IDS = new Set(TABS.map((t) => t.id));

function tabFromHash() {
  const raw = window.location.hash.replace(/^#\/?/, '');
  return TAB_IDS.has(raw) ? raw : null;
}

function hashForTab(id) {
  return `#/${id}`;
}

function App() {
  // KV-40 — start on the tab named in the URL; Capture when it names none.
  const [tab, setTab] = useState(() => tabFromHash() ?? 'capture');
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

  // KV-40 — on first load, normalise the URL to the active tab's hash.
  // replaceState, not a hash assignment, so the landing URL is rewritten
  // in place instead of gaining a duplicate history entry.
  useEffect(() => {
    if (tabFromHash() !== tab) {
      window.history.replaceState(null, '', hashForTab(tab));
    }
    // Runs once on mount; `tab` here is the initial tab by construction.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // KV-40 — Back/Forward (and a hand-edited hash) move the tab. Hash
  // changes caused by selectTab below also land here; the functional
  // update makes those a no-op because the tab already matches.
  useEffect(() => {
    function onHashChange() {
      const next = tabFromHash();
      if (next) setTab((cur) => (next === cur ? cur : next));
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // Single path for switching tabs: state first, then the URL. Assigning
  // location.hash pushes a history entry — which is what makes Back
  // work — and fires hashchange, handled as a no-op above.
  function selectTab(next) {
    setTab(next);
    if (tabFromHash() !== next) window.location.hash = hashForTab(next);
  }

  function navigate(next) {
    if (next === 'browse') setBrowseRefresh((n) => n + 1);
    selectTab(next);
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
                  onClick={() => selectTab(t.id)}
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
