import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import AuthScreen from './AuthScreen.jsx';
import { forgotPassword, login, resetPassword, signup } from '../api.js';
import { getToken } from '../auth.js';

// The mode toggle and the submit button can share a label ("Sign in" /
// "Sign up"), so scope each query to its container.
function toggleButton(name) {
  const group = screen.getByRole('group', { name: 'Sign in or sign up' });
  return within(group).getByRole('button', { name });
}

// The form also holds the show/hide password button, so pick the submit
// by its label rather than by position.
function submitButton() {
  return within(document.querySelector('form')).getByRole('button', { name: /sign/i });
}

// KV-39 — the auth screen is the gate for the whole app (KV-43): mode
// switching, the client-side checks, and storing the issued token.
vi.mock('../api.js', () => ({
  checkHealth: vi.fn(async () => true),
  login: vi.fn(),
  signup: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
}));

function fillForm(email, password) {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
}

describe('AuthScreen', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('renders the sign-in mode by default, with labelled fields (KV-44)', () => {
    render(<AuthScreen onAuthenticated={() => {}} />);
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('switches to sign-up mode', () => {
    render(<AuthScreen onAuthenticated={() => {}} />);
    fireEvent.click(toggleButton('Sign up'));
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
  });

  it('rejects an empty email before calling the API', async () => {
    render(<AuthScreen onAuthenticated={() => {}} />);
    fireEvent.click(submitButton());
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter your email address.');
    expect(login).not.toHaveBeenCalled();
  });

  it('rejects a short password in sign-up mode', async () => {
    render(<AuthScreen onAuthenticated={() => {}} />);
    fireEvent.click(toggleButton('Sign up'));
    fillForm('a@b.c', 'short');
    fireEvent.click(submitButton());
    expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters');
    expect(signup).not.toHaveBeenCalled();
  });

  it('stores the token and notifies the shell on successful sign-in', async () => {
    login.mockResolvedValue({ access_token: 'tok-xyz' });
    const onAuthenticated = vi.fn();
    render(<AuthScreen onAuthenticated={onAuthenticated} />);

    fillForm('a@b.c', 'correct horse');
    fireEvent.click(submitButton());

    await screen.findByRole('heading', { name: 'Welcome back' });
    expect(login).toHaveBeenCalledWith('a@b.c', 'correct horse');
    expect(getToken()).toBe('tok-xyz');
    expect(onAuthenticated).toHaveBeenCalledTimes(1);
  });

  it('shows the backend detail text when sign-in fails', async () => {
    login.mockRejectedValue(Object.assign(new Error('nope'), { detail: 'Invalid credentials' }));
    render(<AuthScreen onAuthenticated={() => {}} />);

    fillForm('a@b.c', 'wrong');
    fireEvent.click(submitButton());

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials');
    expect(getToken()).toBeNull();
  });
});

// KV-59 — the password reset screens: the forgot form behind the
// sign-in screen's "Forgot password?" link, and the reset form the
// shell opens when the emailed link's token arrives as a prop.
describe('AuthScreen password reset (KV-59)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('opens the forgot form from sign-in and shows the backend message', async () => {
    forgotPassword.mockResolvedValue({
      message:
        'If an account exists for that email, we have sent a link to reset the password. It works for 30 minutes.',
    });
    render(<AuthScreen onAuthenticated={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: 'Forgot password?' }));
    expect(screen.getByRole('heading', { name: 'Forgot your password' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.c' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }));

    expect(
      await screen.findByText(/If an account exists for that email/),
    ).toBeInTheDocument();
    expect(forgotPassword).toHaveBeenCalledWith('a@b.c');
    expect(login).not.toHaveBeenCalled();
  });

  it('rejects an empty email in the forgot form', async () => {
    render(<AuthScreen onAuthenticated={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Forgot password?' }));
    fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter your email address.');
    expect(forgotPassword).not.toHaveBeenCalled();
  });

  it('opens in reset mode when a reset token is supplied', () => {
    render(
      <AuthScreen
        onAuthenticated={() => {}}
        resetToken="tok-123"
        onResetTokenConsumed={() => {}}
      />,
    );
    expect(screen.getByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument();
    expect(screen.getByLabelText('New password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm password')).toBeInTheDocument();
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument();
  });

  function fillReset(password, confirm) {
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: password } });
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: confirm } });
  }

  it('rejects a short or mismatched password in reset mode', async () => {
    render(
      <AuthScreen
        onAuthenticated={() => {}}
        resetToken="tok-123"
        onResetTokenConsumed={() => {}}
      />,
    );

    fillReset('short', 'short');
    fireEvent.click(screen.getByRole('button', { name: 'Set new password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters');

    fillReset('long-enough', 'different-one');
    fireEvent.click(screen.getByRole('button', { name: 'Set new password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The passwords do not match.');

    expect(resetPassword).not.toHaveBeenCalled();
  });

  it('stores the session token and notifies the shell on a successful reset', async () => {
    resetPassword.mockResolvedValue({ access_token: 'tok-new' });
    const onAuthenticated = vi.fn();
    const onResetTokenConsumed = vi.fn();
    render(
      <AuthScreen
        onAuthenticated={onAuthenticated}
        resetToken="tok-123"
        onResetTokenConsumed={onResetTokenConsumed}
      />,
    );

    fillReset('long-enough', 'long-enough');
    fireEvent.click(screen.getByRole('button', { name: 'Set new password' }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledTimes(1));
    expect(resetPassword).toHaveBeenCalledWith('tok-123', 'long-enough');
    expect(getToken()).toBe('tok-new');
    expect(onResetTokenConsumed).toHaveBeenCalledTimes(1);
  });

  it('offers a new link when the reset link is dead', async () => {
    resetPassword.mockRejectedValue(
      Object.assign(new Error('nope'), {
        detail: 'This reset link has expired. Ask for a new one.',
        code: 'reset_token_expired',
      }),
    );
    render(
      <AuthScreen
        onAuthenticated={() => {}}
        resetToken="tok-old"
        onResetTokenConsumed={() => {}}
      />,
    );

    fillReset('long-enough', 'long-enough');
    fireEvent.click(screen.getByRole('button', { name: 'Set new password' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('This reset link has expired');
    fireEvent.click(screen.getByRole('button', { name: 'Ask for a new link' }));
    expect(screen.getByRole('heading', { name: 'Forgot your password' })).toBeInTheDocument();
  });
});
