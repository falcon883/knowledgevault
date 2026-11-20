import { useState } from 'react';
import { changePassword } from './api.js';
import { IconCheckCircle } from './icons.jsx';

/**
 * KV-62 — change password while signed in (backend KV-62).
 *
 * A dedicated page in the app shell (routed as #/password), not a
 * panel over the workspace: the shell hands it the main content area
 * and a way back (onClose), and it renders the page heading, a short
 * explainer and the form in a card. The form asks for the current
 * password and the new password twice; the backend re-checks the
 * current password, so a stolen session alone cannot lock the owner
 * out. On success the backend's message ("Password changed.") is
 * shown and the session simply continues — the token is unchanged.
 * Failures show the backend's detail text verbatim: a wrong current
 * password (400 wrong_password), a weak, over-long or unchanged new
 * password (422), or a rate limit (429). The client-side checks
 * mirror the AuthScreen wording; they only save a round trip, the
 * backend remains the authority.
 */
function ChangePasswordForm({ onClose }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!current) {
      setError('Enter your current password.');
      return;
    }
    if (next.length < 8) {
      setError('Use a password of at least 8 characters.');
      return;
    }
    if (next !== confirm) {
      setError('The passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      const data = await changePassword(current, next);
      setNotice(
        typeof data?.message === 'string' ? data.message : 'Password changed.',
      );
      setCurrent('');
      setNext('');
      setConfirm('');
    } catch (err) {
      setError(err.message || 'Change password failed. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="kv-changepw">
      <h2 className="kv-changepw-title">Change password</h2>
      <p className="kv-changepw-sub">
        Use your current password to set a new one. You stay signed in, and
        changing it cancels any password-reset links you have requested.
      </p>

      <section className="kv-card kv-changepw-card" aria-label="Change password form">
        {notice ? (
          <p className="kv-status ok" role="status">
            <IconCheckCircle size={17} /> {notice}
          </p>
        ) : null}
        {error ? (
          <p className="kv-status error" role="alert">
            {error}
          </p>
        ) : null}

        <form onSubmit={handleSubmit} noValidate>
          <label className="kv-label" htmlFor="kv-changepw-current">
            Current password
          </label>
          <input
            id="kv-changepw-current"
            className="kv-input"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            placeholder="Your current password"
          />

          <label className="kv-label" htmlFor="kv-changepw-new">
            New password
          </label>
          <input
            id="kv-changepw-new"
            className="kv-input"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            placeholder="8+ characters"
          />

          <label className="kv-label" htmlFor="kv-changepw-confirm">
            Confirm new password
          </label>
          <input
            id="kv-changepw-confirm"
            className="kv-input"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Repeat the new password"
          />

          <div className="kv-changepw-actions">
            <button
              type="submit"
              className="kv-btn kv-btn-primary"
              disabled={busy}
            >
              Change password
            </button>
            <button
              type="button"
              className="kv-btn kv-btn-secondary"
              onClick={onClose}
            >
              Cancel
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default ChangePasswordForm;
