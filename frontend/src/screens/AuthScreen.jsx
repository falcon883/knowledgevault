import { useState } from 'react';
import { login, signup } from '../api.js';
import { setToken } from '../auth.js';
import { IconAlertCircle, IconBookOpen } from '../icons.jsx';

/**
 * KV-43 — Sign in / sign up screen.
 *
 * The backend protects every route except /health with an account token,
 * so this screen gates the app: POST /auth/signup or POST /auth/login
 * with {email, password} returns an access_token (24h), which is stored
 * via auth.js and sent on every later request. Backend failures come
 * back as {detail, code} — the detail text is shown verbatim so cases
 * like invalid_credentials, email_taken and weak_password read clearly.
 */

const MODES = [
  { id: 'signin', label: 'Sign in' },
  { id: 'signup', label: 'Sign up' },
];

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

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
    <div className="kv-auth-wrap">
      <section className="kv-card kv-auth-card">
        <span className="kv-brand-mark kv-auth-mark">
          <IconBookOpen size={22} />
        </span>
        <h2>{mode === 'signup' ? 'Create your account' : 'Welcome back'}</h2>
        <p className="kv-lede">
          {mode === 'signup'
            ? 'Sign up to start your own vault. Your documents are private to your account.'
            : 'Sign in to your KnowledgeVault account to reach your documents.'}
        </p>

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
          <label className="kv-label" htmlFor="kv-auth-email">
            Email
          </label>
          <input
            id="kv-auth-email"
            className="kv-input"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />

          <label className="kv-label" htmlFor="kv-auth-password">
            Password
          </label>
          <input
            id="kv-auth-password"
            className="kv-input"
            type="password"
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={mode === 'signup' ? '8+ characters' : 'Your password'}
          />

          {error && (
            <p className="kv-field-error kv-auth-error" role="alert">
              <IconAlertCircle size={15} /> {error}
            </p>
          )}

          <button type="submit" className="kv-btn kv-auth-submit" disabled={busy}>
            {busy
              ? mode === 'signup'
                ? 'Creating account…'
                : 'Signing in…'
              : mode === 'signup'
                ? 'Sign up'
                : 'Sign in'}
          </button>
        </form>
      </section>
    </div>
  );
}

export default AuthScreen;
