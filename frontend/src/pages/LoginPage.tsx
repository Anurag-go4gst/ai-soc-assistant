import { FormEvent, useState } from 'react';
import { login } from '../api/client';
import type { AuthResponse } from '../types/api';

interface LoginPageProps {
  onAuthenticated: (auth: AuthResponse) => void;
}

export function LoginPage({ onAuthenticated }: LoginPageProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const auth = await login(username, password);
      onAuthenticated(auth);
    } catch {
      setError('Invalid credentials');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="loginShell">
      <section className="loginPanel" aria-labelledby="login-title">
        <p className="eyebrow">Protected demo environment</p>
        <h1 id="login-title">Velocis AI SOC Assistant</h1>
        <p className="loginCopy">Experience Center access verification</p>

        <form className="loginForm" onSubmit={handleSubmit}>
          <label>
            Username
            <input
              autoComplete="username"
              name="username"
              onChange={(event) => setUsername(event.target.value)}
              required
              type="text"
              value={username}
            />
          </label>
          <label>
            Password
            <input
              autoComplete="current-password"
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          {error ? <div className="formError">{error}</div> : null}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Verifying...' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}
