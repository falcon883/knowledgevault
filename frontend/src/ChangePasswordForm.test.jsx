import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChangePasswordForm from './ChangePasswordForm.jsx';
import { changePassword } from './api.js';

// KV-62 — the change-password panel: client-side checks mirror the
// auth screen's wording, success shows the backend's message and
// clears the form, and backend failures (wrong current password,
// weak new password, rate limit) surface their detail text verbatim.
vi.mock('./api.js', () => ({
  changePassword: vi.fn(),
}));

function fill(current, next, confirm) {
  fireEvent.change(screen.getByLabelText('Current password'), {
    target: { value: current },
  });
  fireEvent.change(screen.getByLabelText('New password'), {
    target: { value: next },
  });
  fireEvent.change(screen.getByLabelText('Confirm new password'), {
    target: { value: confirm },
  });
}

function submit() {
  fireEvent.click(screen.getByRole('button', { name: 'Change password' }));
}

describe('ChangePasswordForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the three password fields', () => {
    render(<ChangePasswordForm onClose={() => {}} />);
    expect(screen.getByLabelText('Current password')).toBeInTheDocument();
    expect(screen.getByLabelText('New password')).toBeInTheDocument();
    expect(screen.getByLabelText('Confirm new password')).toBeInTheDocument();
  });

  it('rejects a mismatched confirmation without calling the API', async () => {
    render(<ChangePasswordForm onClose={() => {}} />);
    fill('old-password', 'new-password', 'different-password');
    submit();
    expect(
      await screen.findByText('The passwords do not match.'),
    ).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it('rejects a new password under 8 characters without calling the API', async () => {
    render(<ChangePasswordForm onClose={() => {}} />);
    fill('old-password', 'short', 'short');
    submit();
    expect(
      await screen.findByText('Use a password of at least 8 characters.'),
    ).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it('shows the backend success message and clears the fields', async () => {
    changePassword.mockResolvedValue({ message: 'Password changed.' });
    render(<ChangePasswordForm onClose={() => {}} />);
    fill('old-password', 'new-password', 'new-password');
    submit();
    expect(await screen.findByText('Password changed.')).toBeInTheDocument();
    expect(changePassword).toHaveBeenCalledWith('old-password', 'new-password');
    await waitFor(() => {
      expect(screen.getByLabelText('Current password')).toHaveValue('');
      expect(screen.getByLabelText('New password')).toHaveValue('');
      expect(screen.getByLabelText('Confirm new password')).toHaveValue('');
    });
  });

  it('shows the backend detail when the current password is wrong', async () => {
    changePassword.mockRejectedValue(
      Object.assign(new Error('Your current password is not right.'), {
        status: 400,
        code: 'wrong_password',
      }),
    );
    render(<ChangePasswordForm onClose={() => {}} />);
    fill('not-it', 'new-password', 'new-password');
    submit();
    expect(
      await screen.findByText('Your current password is not right.'),
    ).toBeInTheDocument();
  });
});
