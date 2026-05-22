import { useEffect, useState } from 'react';
import { getCurrentUser, logout } from './api/client';
import { LoginPage } from './pages/LoginPage';
import { SocCockpit } from './pages/SocCockpit';
import type { AuthResponse } from './types/api';

export default function App() {
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    getCurrentUser()
      .then(setAuth)
      .catch(() => setAuth({ authenticated: false }))
      .finally(() => setCheckingAuth(false));
  }, []);

  const handleLogout = async () => {
    await logout();
    setAuth({ authenticated: false });
  };

  if (checkingAuth) {
    return (
      <main className="loginShell">
        <section className="loginPanel">
          <p className="eyebrow">Protected demo environment</p>
          <h1>Velocis AI SOC Assistant</h1>
          <p className="loginCopy">Checking access...</p>
        </section>
      </main>
    );
  }

  if (!auth?.authenticated) {
    return <LoginPage onAuthenticated={setAuth} />;
  }

  return <SocCockpit username={auth.username ?? 'analyst'} onLogout={handleLogout} />;
}
