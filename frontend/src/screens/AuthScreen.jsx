import { useEffect, useState } from 'react';
import { checkHealth, login, signup } from '../api.js';
import { setToken } from '../auth.js';
import {
  IconAlertCircle,
  IconArrowRight,
  IconBookOpen,
  IconEye,
  IconEyeOff,
  IconLayers,
  IconLock,
  IconMail,
  IconSearch,
  IconShieldCheck,
} from '../icons.jsx';
import vaultArt from '../assets/vault-art.webp';

/**
 * KV-43 — Sign in / sign up screen.
 *
 * The backend protects every route except /health with an account token,
 * so this screen gates the app: POST /auth/signup or POST /auth/login
 * with {email, password} returns an access_token (24h), which is stored
 * via auth.js and sent on every later request. Backend failures come
 * back as {detail, code} — the detail text is shown verbatim so cases
 * like invalid_credentials, email_taken and weak_password read clearly.
 *
 * Layout (Nov 2026 redesign): a dark hero band carries the brand, the
 * tagline, a live backend-status pill fed by the open /health route,
 * and the vault illustration; the form card overlaps it. The shell
 * renders this screen full-bleed while signed out, so the hero replaces
 * the usual top bar here — this screen owns the page's h1.
 */

const MODES = [
  { id: 'signin', label: 'Sign in' },
  { id: 'signup', label: 'Sign up' },
];

const FEATURES = [
  { Icon: IconLayers, label: 'Organize' },
  { Icon: IconSearch, label: 'Search' },
  { Icon: IconShieldCheck, label: 'Keep it secure' },
];

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [backendOk, setBackendOk] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // The status pill is a real check, not decoration: /health is the one
  // route that answers without a token.
  useEffect(() => {
    let cancelled = false;
    checkHealth().then((ok) => {
      if (!cancelled) setBackendOk(ok);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  function switchMode(next) {
    setMode(next);
    setError('');
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');

    // Light client-side checks; the backend stays the authority and its
    // detail text is what the user ultimately sees.
    if (!email.trim()) {
      setError('Enter your email address.');
      return;
    }
    if (mode === 'signup' && password.length < 8) {
      setError('Use a password of at least 8 characters.');
      return;
    }
    if (!password) {
      setError('Enter your password.');
      return;
    }

    setBusy(true);
    try {
      const data =
        mode === 'signup'
          ? await signup(email.trim(), password)
          : await login(email.trim(), password);
      setToken(data.access_token);
      onAuthenticated();
    } catch (err) {
      setError(
        typeof err.detail === 'string'
          ? err.detail
          : 'Something went wrong. Check the backend is running and try again.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="kv-auth2">
      <div className="kv-auth2-hero">
        <div className="kv-auth2-hero-inner">
          <div className="kv-auth2-brandrow">
            <span className="kv-brand-mark kv-auth2-mark">
              <IconBookOpen size={26} />
            </span>
            <div className="kv-auth2-brandtext">
              <h1 className="kv-auth2-title">KnowledgeVault</h1>
              <p className="kv-auth2-tagline">Personal archive for your knowledge</p>
            </div>
          </div>

          <p
            className={`kv-auth2-pill${backendOk == null ? '' : backendOk ? ' ok' : ' down'}`}
            role="status"
          >
            <i aria-hidden="true" />
            {backendOk == null
              ? 'Checking backend'
              : backendOk
                ? 'Backend connected'
                : 'Backend unreachable'}
          </p>

          <img className="kv-auth2-art" src={vaultArt} alt="" aria-hidden="true" />
        </div>
      </div>

      <section className="kv-card kv-auth-card kv-auth2-card">
        <h2>{mode === 'signup' ? 'Create your account' : 'Welcome back'}</h2>
        <p className="kv-lede">
          {mode === 'signup'
            ? 'Sign up to start your own vault. Your documents are private to your account.'
            : 'Sign in to your KnowledgeVault account to reach your documents, notes, and resources.'}
        </p>

        <ul className="kv-auth2-features">
          {FEATURES.map(({ Icon, label }, i) => (
            <li key={label} className="kv-auth2-feature-wrap">
              {i > 0 && <span className="kv-auth2-fdiv" aria-hidden="true" />}
              <span className="kv-auth2-feature">
                <span className="kv-auth2-chip">
                  <Icon size={19} />
                </span>
                {label}
              </span>
            </li>
          ))}
        </ul>

        <div className="kv-kind-toggle" role="group" aria-label="Sign in or sign up">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              className="kv-kind-btn"
              aria-pressed={mode === m.id}
              onClick={() => switchMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <label className="kv-label kv-auth2-label" htmlFor="kv-auth-email">
            <IconMail size={15} /> Email
          </label>
          <div className="kv-auth2-field">
            <span className="kv-auth2-field-icon">
              <IconMail size={17} />
            </span>
            <input
              id="kv-auth-email"
              className="kv-input kv-auth2-input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>

          <label className="kv-label kv-auth2-label" htmlFor="kv-auth-password">
            <IconLock size={15} /> Password
          </label>
          <div className="kv-auth2-field">
            <span className="kv-auth2-field-icon">
              <IconLock size={17} />
            </span>
            <input
              id="kv-auth-password"
              className="kv-input kv-auth2-input kv-auth2-input-pw"
              type={showPassword ? 'text' : 'password'}
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === 'signup' ? '8+ characters' : 'Your password'}
            />
            <button
              type="button"
              className="kv-auth2-eye"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((v) => !v)}
            >
              {showPassword ? <IconEyeOff size={19} /> : <IconEye size={19} />}
            </button>
          </div>

          {error && (
            <p className="kv-field-error kv-auth-error" role="alert">
              <IconAlertCircle size={15} /> {error}
            </p>
          )}

          <button type="submit" className="kv-btn kv-auth-submit kv-auth2-submit" disabled={busy}>
            {busy
              ? mode === 'signup'
                ? 'Creating account…'
                : 'Signing in…'
              : mode === 'signup'
                ? 'Sign up'
                : 'Sign in'}
            {!busy && <IconArrowRight size={18} />}
          </button>
        </form>
      </section>
    </div>
  );
}

export default AuthScreen;
