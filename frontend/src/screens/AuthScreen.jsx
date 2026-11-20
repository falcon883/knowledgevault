import { useEffect, useState } from 'react';
import { checkHealth, forgotPassword, login, resetPassword, signup } from '../api.js';
import { setToken } from '../auth.js';
import {
  IconAlertCircle,
  IconArrowRight,
  IconBookOpen,
  IconCheckCircle,
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
 * KV-59 — password reset screens, the frontend half of KV-53. A
 * "Forgot password?" link on the sign-in form opens the forgot mode:
 * an email goes to POST /auth/forgot-password, which always answers
 * 202 with the same message, shown verbatim, so the screen cannot be
 * used to probe which addresses hold accounts. The emailed link points
 * at the app root with ?reset_token=... (the backend builds it that
 * way so it works on the static host); the shell reads the token from
 * the query and passes it in as a prop, which opens the reset mode:
 * a new password goes to POST /auth/reset-password, and because the
 * backend answers a successful reset with a session token, the user
 * lands signed in. A spent, replaced or expired link comes back as a
 * 400 whose detail is shown verbatim, with an "Ask for a new link"
 * shortcut back to the forgot mode. A weak password is a 422 and does
 * not spend the link, so the form simply stays open for a retry.
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

// The three ways a reset link can be dead on arrival (backend KV-53);
// each is answered with a route back to the forgot form.
const DEAD_LINK_CODES = new Set([
  'invalid_reset_token',
  'reset_token_expired',
  'reset_token_used',
]);

const HEADINGS = {
  signin: 'Welcome back',
  signup: 'Create your account',
  forgot: 'Forgot your password',
  reset: 'Choose a new password',
};

const LEDES = {
  signin:
    'Sign in to your KnowledgeVault account to reach your documents, notes, and resources.',
  signup: 'Sign up to start your own vault. Your documents are private to your account.',
  forgot:
    'Enter your account email and we will send you a link to choose a new password. The link works for 30 minutes.',
  reset: 'Enter a new password for your account. This reset link works once.',
};

const SUBMIT_LABELS = {
  signin: 'Sign in',
  signup: 'Sign up',
  forgot: 'Send reset link',
  reset: 'Set new password',
};

const BUSY_LABELS = {
  signin: 'Signing in…',
  signup: 'Creating account…',
  forgot: 'Sending…',
  reset: 'Setting password…',
};

function AuthScreen({ onAuthenticated, resetToken = null, onResetTokenConsumed = () => {} }) {
  const [mode, setMode] = useState(() => (resetToken ? 'reset' : 'signin'));
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [backendOk, setBackendOk] = useState(null);
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [notice, setNotice] = useState('');
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
    setErrorCode('');
    setNotice('');
  }

  // Leaving the reset mode for any reason — success, a dead link, or
  // the user backing out — spends the shell's copy of the token, so
  // the reset screen is never shown twice for the same link.
  function leaveReset(next) {
    onResetTokenConsumed();
    switchMode(next);
  }

  function showFailure(err) {
    setError(
      typeof err.detail === 'string'
        ? err.detail
        : 'Something went wrong. Check the backend is running and try again.',
    );
    setErrorCode(typeof err.code === 'string' ? err.code : '');
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setErrorCode('');

    // Light client-side checks; the backend stays the authority and its
    // detail text is what the user ultimately sees.
    if (mode !== 'reset' && !email.trim()) {
      setError('Enter your email address.');
      return;
    }
    if ((mode === 'signup' || mode === 'reset') && password.length < 8) {
      setError('Use a password of at least 8 characters.');
      return;
    }
    if (mode === 'reset' && password !== confirmPassword) {
      setError('The passwords do not match.');
      return;
    }
    if (mode !== 'forgot' && !password) {
      setError('Enter your password.');
      return;
    }

    setBusy(true);
    try {
      if (mode === 'forgot') {
        const data = await forgotPassword(email.trim());
        // The 202 message is deliberately identical for known and
        // unknown addresses; show it as the confirmation either way.
        setNotice(
          typeof data?.message === 'string'
            ? data.message
            : 'If an account exists for that email, we have sent a link to reset the password.',
        );
      } else if (mode === 'reset') {
        const data = await resetPassword(resetToken, password);
        setToken(data.access_token);
        onResetTokenConsumed();
        onAuthenticated();
      } else {
        const data =
          mode === 'signup'
            ? await signup(email.trim(), password)
            : await login(email.trim(), password);
        setToken(data.access_token);
        onAuthenticated();
      }
    } catch (err) {
      showFailure(err);
    } finally {
      setBusy(false);
    }
  }

  const inAuthModes = mode === 'signin' || mode === 'signup';
  const showEmail = mode !== 'reset';
  const showConfirm = mode === 'reset';

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
        <h2>{HEADINGS[mode]}</h2>
        <p className="kv-lede">{LEDES[mode]}</p>

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

        {inAuthModes && (
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
        )}

        {notice ? (
          <>
            <p className="kv-status ok kv-auth2-notice" role="status">
              <IconCheckCircle size={17} /> {notice}
            </p>
            <button
              type="button"
              className="kv-btn kv-auth-submit kv-auth2-submit"
              onClick={() => switchMode('signin')}
            >
              Back to sign in
            </button>
          </>
        ) : (
          <form onSubmit={handleSubmit} noValidate>
            {showEmail && (
              <>
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
              </>
            )}

            {mode !== 'forgot' && (
              <>
                <label className="kv-label kv-auth2-label" htmlFor="kv-auth-password">
                  <IconLock size={15} /> {mode === 'reset' ? 'New password' : 'Password'}
                </label>
                <div className="kv-auth2-field">
                  <span className="kv-auth2-field-icon">
                    <IconLock size={17} />
                  </span>
                  <input
                    id="kv-auth-password"
                    className="kv-input kv-auth2-input kv-auth2-input-pw"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete={
                      mode === 'signin' ? 'current-password' : 'new-password'
                    }
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={
                      mode === 'signin' ? 'Your password' : '8+ characters'
                    }
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

                {mode === 'signin' && (
                  <div className="kv-auth2-linkrow">
                    <button
                      type="button"
                      className="kv-auth2-linkbtn"
                      onClick={() => switchMode('forgot')}
                    >
                      Forgot password?
                    </button>
                  </div>
                )}
              </>
            )}

            {showConfirm && (
              <>
                <label className="kv-label kv-auth2-label" htmlFor="kv-auth-confirm">
                  <IconLock size={15} /> Confirm password
                </label>
                <div className="kv-auth2-field">
                  <span className="kv-auth2-field-icon">
                    <IconLock size={17} />
                  </span>
                  <input
                    id="kv-auth-confirm"
                    className="kv-input kv-auth2-input"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat the new password"
                  />
                </div>
              </>
            )}

            {error && (
              <p className="kv-field-error kv-auth-error" role="alert">
                <IconAlertCircle size={15} /> {error}
              </p>
            )}

            {mode === 'reset' && DEAD_LINK_CODES.has(errorCode) && (
              <div className="kv-auth2-linkrow">
                <button
                  type="button"
                  className="kv-auth2-linkbtn"
                  onClick={() => leaveReset('forgot')}
                >
                  Ask for a new link
                </button>
              </div>
            )}

            <button type="submit" className="kv-btn kv-auth-submit kv-auth2-submit" disabled={busy}>
              {busy ? BUSY_LABELS[mode] : SUBMIT_LABELS[mode]}
              {!busy && <IconArrowRight size={18} />}
            </button>

            {!inAuthModes && (
              <div className="kv-auth2-backrow">
                <button
                  type="button"
                  className="kv-auth2-linkbtn"
                  onClick={() =>
                    mode === 'reset' ? leaveReset('signin') : switchMode('signin')
                  }
                >
                  Back to sign in
                </button>
              </div>
            )}
          </form>
        )}
      </section>
    </div>
  );
}

export default AuthScreen;
