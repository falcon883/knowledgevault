import { useEffect, useState } from 'react';

/**
 * KnowledgeVault - Sprint 1 placeholder landing page.
 *
 * Demonstrates the chosen frontend framework and build tooling only,
 * per Section 5.2 of the Vision/Roadmap/Release Plan. Real capture,
 * browse, and search screens are built starting in Sprint 1
 * (see Roadmap Theme 1 and 2).
 */
function App() {
  const [apiStatus, setApiStatus] = useState('checking...');

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => setApiStatus(data.status === 'ok' ? 'connected' : 'unknown'))
      .catch(() => setApiStatus('backend not running'));
  }, []);

  return (
    <main style={styles.page}>
      <h1 style={styles.title}>KnowledgeVault</h1>
      <p style={styles.subtitle}>
        Find what you meant, not just what you typed.
      </p>
      <p style={styles.status}>
        Backend status: <strong>{apiStatus}</strong>
      </p>
      <p style={styles.note}>
        This is a Sprint 1 placeholder. Upload, browse, and search screens
        arrive in upcoming sprints per the project roadmap.
      </p>
    </main>
  );
}

const styles = {
  page: {
    fontFamily: 'system-ui, sans-serif',
    maxWidth: '640px',
    margin: '80px auto',
    textAlign: 'center',
    color: '#1a1a1a',
  },
  title: {
    fontSize: '2.5rem',
    marginBottom: '0.25rem',
  },
  subtitle: {
    fontSize: '1.1rem',
    color: '#555',
    marginBottom: '2rem',
  },
  status: {
    fontSize: '1rem',
  },
  note: {
    marginTop: '2rem',
    fontSize: '0.9rem',
    color: '#888',
  },
};

export default App;
