import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AuthGate from './AuthGate';
import { api } from '../services/http';

jest.mock('../services/http', () => ({
  api: { get: jest.fn(), post: jest.fn() },
}));

beforeEach(() => {
  api.get.mockResolvedValue({ data: { authenticated: false } });
  api.post.mockResolvedValue({ data: { authenticated: true } });
});

test('signs in before rendering protected app content', async () => {
  render(<AuthGate><div>Protected chats</div></AuthGate>);

  expect(await screen.findByLabelText(/4-digit PIN/)).toBeInTheDocument();
  expect(screen.queryByText('Protected chats')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/4-digit PIN/), {
    target: { value: '1234abc' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

  await waitFor(() => expect(screen.getByText('Protected chats')).toBeInTheDocument());
  expect(api.post).toHaveBeenCalledWith('/auth/login', {
    password: '1234',
  });
});

test('displays the server error when the password is rejected', async () => {
  api.post.mockRejectedValue({ response: { data: { detail: 'Incorrect password.' } } });
  render(<AuthGate><div>Protected chats</div></AuthGate>);

  fireEvent.change(await screen.findByLabelText(/4-digit PIN/), {
    target: { value: '0000' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

  expect(await screen.findByText('Incorrect password.')).toBeInTheDocument();
  expect(screen.queryByText('Protected chats')).not.toBeInTheDocument();
});
