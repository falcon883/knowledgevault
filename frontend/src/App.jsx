import { useEffect, useState } from 'react';
import StatusCard from '../components/StatusCard';

function App() {
  const [apiStatus, setApiStatus] = useState('checking...');

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => setApiStatus(data.status === 'ok' ? 'connected' : 'unknown'))
      .catch(() => setApiStatus('backend not running'));
  }, []);

  return (
    <div style={styles.appShell}>
      <header style={styles.topbar}>
        <div style={styles.brand}>KnowledgeVault</div>
        <nav style={styles.nav}>
          <a href="#features" style={styles.navLink}>Features</a>
          <a href="#workflow" style={styles.navLink}>Workflow</a>
          <a href="#status" style={styles.navLink}>Status</a>
        </nav>
      </header>

      <main style={styles.page}>
        <section style={styles.hero}>
          <div style={styles.heroText}>
            <span style={styles.eyebrow}>Knowledge platform</span>
            <h1 style={styles.title}>Find the right knowledge, faster.</h1>
            <p style={styles.subtitle}>
              Organize, search, and discover the information your team actually needs.
            </p>
            <div style={styles.actions}>
              <button style={styles.primaryButton}>Get started</button>
              <button style={styles.secondaryButton}>View roadmap</button>
            </div>
          </div>

          <div style={styles.heroCard}>
            <div style={styles.cardLabel}>System overview</div>
            <div style={styles.metricRow}>
              <div>
                <div style={styles.metricValue}>24k</div>
                <div style={styles.metricLabel}>documents</div>
              </div>
              <div>
                <div style={styles.metricValue}>3.2s</div>
                <div style={styles.metricLabel}>avg. search</div>
              </div>
            </div>
            <StatusCard label="Backend status" status={apiStatus} />
          </div>
        </section>

        <section id="features" style={styles.features}>
          <div style={styles.featureBox}>
            <h3 style={styles.featureTitle}>Capture</h3>
            <p style={styles.featureText}>Import and organize knowledge from multiple sources.</p>
          </div>
          <div style={styles.featureBox}>
            <h3 style={styles.featureTitle}>Browse</h3>
            <p style={styles.featureText}>Explore related content with a clear, structured interface.</p>
          </div>
          <div style={styles.featureBox}>
            <h3 style={styles.featureTitle}>Search</h3>
            <p style={styles.featureText}>Find the answer, not just the closest keyword match.</p>
          </div>
        </section>
      </main>
    </div>
  );
}

const styles = {
  appShell: {
    minHeight: '100vh',
    background: 'linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%)',
    color: '#122033',
    fontFamily: 'system-ui, sans-serif',
  },
  topbar: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '1.25rem 2rem',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  brand: {
    fontSize: '1.3rem',
    fontWeight: 700,
    letterSpacing: '-0.04em',
  },
  nav: {
    display: 'flex',
    gap: '1.5rem',
  },
  navLink: {
    textDecoration: 'none',
    color: '#44546a',
    fontSize: '0.95rem',
  },
  page: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '2rem 2rem 4rem',
  },
  hero: {
    display: 'grid',
    gridTemplateColumns: '1.3fr 0.9fr',
    gap: '2rem',
    alignItems: 'center',
    padding: '3rem 0 2rem',
  },
  heroText: {
    maxWidth: '620px',
  },
  eyebrow: {
    display: 'inline-block',
    background: '#dfeafc',
    color: '#1d4ed8',
    padding: '0.45rem 0.8rem',
    borderRadius: '999px',
    fontSize: '0.75rem',
    fontWeight: 700,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    marginBottom: '1rem',
  },
  title: {
    fontSize: 'clamp(2.5rem, 5vw, 4.5rem)',
    lineHeight: 1.05,
    margin: '0 0 1rem',
    letterSpacing: '-0.06em',
  },
  subtitle: {
    fontSize: '1.15rem',
    color: '#4a5c75',
    lineHeight: 1.6,
    marginBottom: '2rem',
    maxWidth: '560px',
  },
  actions: {
    display: 'flex',
    gap: '1rem',
    flexWrap: 'wrap',
  },
  primaryButton: {
    border: 'none',
    borderRadius: '12px',
    background: '#1d4ed8',
    color: '#fff',
    padding: '0.9rem 1.4rem',
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  secondaryButton: {
    border: '1px solid #cfe0ff',
    borderRadius: '12px',
    background: '#ffffff',
    color: '#183153',
    padding: '0.9rem 1.4rem',
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
  },
  heroCard: {
    background: '#ffffff',
    border: '1px solid #e3ecff',
    borderRadius: '20px',
    boxShadow: '0 18px 40px rgba(30, 64, 175, 0.08)',
    padding: '1.5rem',
  },
  cardLabel: {
    color: '#5b6d84',
    fontSize: '0.8rem',
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    marginBottom: '1rem',
  },
  metricRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '1rem',
    marginBottom: '1rem',
  },
  metricValue: {
    fontSize: '2rem',
    fontWeight: 800,
    letterSpacing: '-0.06em',
    color: '#10233f',
  },
  metricLabel: {
    color: '#5c6f87',
    fontSize: '0.85rem',
  },
  features: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
    gap: '1.25rem',
    marginTop: '2rem',
  },
  featureBox: {
    background: '#fff',
    border: '1px solid #e5ecf7',
    borderRadius: '18px',
    padding: '1.5rem',
    boxShadow: '0 8px 20px rgba(15, 23, 42, 0.03)',
  },
  featureTitle: {
    margin: '0 0 0.6rem',
    fontSize: '1.2rem',
  },
  featureText: {
    margin: 0,
    color: '#53657b',
    lineHeight: 1.6,
  },
};

export default App;
