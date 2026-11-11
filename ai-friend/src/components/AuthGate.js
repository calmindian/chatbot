import React, { useEffect, useState } from 'react';
import { Alert, Button, CircularProgress, TextField } from '@mui/material';
import { api } from '../services/http';
import './AuthGate.css';

export default function AuthGate({ children }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    api.get('/auth/status')
      .then(response => {
        if (active) setAuthenticated(response.data.authenticated === true);
      })
      .catch(() => {
        if (active) setError('Could not reach the server. Check that it is running, then try again.');
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => { active = false; };
  }, []);

  const handleLogin = async event => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const response = await api.post('/auth/login', { password: pin });
      setAuthenticated(response.data.authenticated === true);
      setPin('');
    } catch (loginError) {
      setError(loginError.response?.data?.detail || 'Sign-in failed. Check the password and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
      setAuthenticated(false);
      setPin('');
    } catch (logoutError) {
      setError(logoutError.response?.data?.detail || 'Could not sign out. Please try again.');
    }
  };

  if (checking) {
    return <main className="auth-loading"><CircularProgress aria-label="Checking sign-in" /></main>;
  }
  if (authenticated) {
    return typeof children === 'function' ? children(handleLogout) : children;
  }

  return (
    <main className="auth-gate">
      <form className="auth-card" onSubmit={handleLogin}>
        <div className="auth-mark" aria-hidden="true">✦</div>
        <p className="auth-eyebrow">YOUR COMPANION SPACE</p>
        <h1>Welcome back</h1>
        <p className="auth-description">Enter the 4-digit shared PIN to continue.</p>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          autoFocus
          fullWidth
          required
          label="4-digit PIN"
          type="password"
          autoComplete="one-time-code"
          value={pin}
          onChange={event => setPin(event.target.value.replace(/\D/g, '').slice(0, 4))}
          inputProps={{ inputMode: 'numeric', pattern: '[0-9]{4}', maxLength: 4 }}
        />
        <Button
          fullWidth
          type="submit"
          variant="contained"
          disabled={submitting || pin.length !== 4}
        >
          {submitting ? <CircularProgress size={20} color="inherit" /> : 'Sign in'}
        </Button>
      </form>
    </main>
  );
}
