import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import { getCurrentUser, logout } from './api/client';
import { LoginPage } from './pages/LoginPage';
import { SocCockpit } from './pages/SocCockpit';
import { TooltipProvider } from './components/ui/tooltip';
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
      <TooltipProvider>
        <main className="soc-canvas soc-grid flex min-h-screen items-center justify-center p-6">
          <section className="soc-panel rounded-2xl p-8 text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">Protected demo environment</p>
            <h1 className="mt-3 text-2xl font-bold">Velocis AI SOC Assistant</h1>
            <p className="mt-2 text-sm text-slate-400">Checking access...</p>
          </section>
        </main>
      </TooltipProvider>
    );
  }

  if (!auth?.authenticated) {
    return (
      <TooltipProvider>
        <LoginPage onAuthenticated={setAuth} />
        <Toaster richColors position="top-right" />
      </TooltipProvider>
    );
  }

  return (
    <TooltipProvider>
      <SocCockpit username={auth.username ?? 'analyst'} onLogout={handleLogout} />
      <Toaster richColors position="top-right" />
    </TooltipProvider>
  );
}
