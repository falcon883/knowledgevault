import { render, screen, fireEvent, within } from '@testing-library/react';
import AuthScreen from './AuthScreen.jsx';
import { login, signup } from '../api.js';
import { getToken } from '../auth.js';

// The mode toggle and the submit button can share a label ("Sign in" /
// "Sign up"), so scope each query to its container.
function toggleButton(name) {
  const group = screen.getByRole('group', { name: 'Sign in or sign up' });
  return within(group).getByRole('button', { name });
}

function submitButton() {
  return within(document.querySelector('form')).getByRole('button');
}

// KV-39 — the auth screen is the gate for the whole app (KV-43): mode
// switching, the client-side checks, and storing the issued token.
vi.mock('../api.js', () => ({
  login: vi.fn(),
  signup: vi.fn(),
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
