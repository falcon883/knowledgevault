import { useEffect, useState } from 'react';
import { checkHealth } from './api.js';
import UploadScreen from './screens/UploadScreen.jsx';
import BrowseScreen from './screens/BrowseScreen.jsx';
import SearchScreen from './screens/SearchScreen.jsx';
import './app.css';

/**
 * KnowledgeVault app shell.
 *
 * Tab navigation across the three Sprint 2 frontend screens:
 *  - KV-19 Capture (upload wired to POST /upload)
 *  - KV-17 Browse (document list wired to GET /documents)
 *  - KV-18 Search (semantic search wired to POST /search)
 */

const TABS = [
  { id: 'search', label: 'Search', Screen: SearchScreen },
  { id: 'browse', label: 'Browse', Screen: BrowseScreen },
  { id: 'capture', label: 'Capture', Screen: UploadScreen },
];

function App() {
  const [tab, setTab] = useState('search');
  const [backendOk, setBackendOk] = useState(null);

  useEffect(() => {
    let cancelled = false;
    checkHealth().then((ok) => {
      if (!cancelled) setBackendOk(ok);
    });
    return () => {
      cancelled = true;
    };
  }, [tab]);

  const active = TABS.find((t) => t.id === tab) ?? TABS[0];
  const ActiveScreen = active.Screen;

  return (
    <div className="kv-shell">
      <header className="kv-topbar">
        <div className="kv-brand">KnowledgeVault</div>
        <nav className="kv-nav" aria-label="Primary">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className="kv-tab"
              aria-pressed={tab === t.id}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
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
      </header>

      <main className="kv-main">
        <ActiveScreen key={tab} onNavigate={setTab} />
      </main>
    </div>
  );
}

export default App;
