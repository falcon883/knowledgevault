import { useEffect, useState } from 'react';
import { checkHealth } from './api.js';
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
 */

const TABS = [
  { id: 'capture', label: 'Capture', Screen: UploadScreen, Icon: IconUploadCloud },
  { id: 'browse', label: 'Browse', Screen: BrowseScreen, Icon: IconFolder },
  { id: 'search', label: 'Search', Screen: SearchScreen, Icon: IconSearch },
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
        </div>
      </header>

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
          <ActiveScreen key={tab} onNavigate={setTab} />
        </main>
      </div>
    </div>
  );
}

export default App;
