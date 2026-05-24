import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';
import { getCurrentUser, getHealth, logout } from './api/client';
import { AppShell } from './components/AppShell';
import { TooltipProvider } from './components/ui/tooltip';
import { ChatPage } from './pages/ChatPage';
import { DebugPage } from './pages/DebugPage';
import { InvestigationsPage } from './pages/InvestigationsPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { LoginPage } from './pages/LoginPage';
import { ScenariosPage } from './pages/ScenariosPage';
import { SettingsPage } from './pages/SettingsPage';
import { SocCockpit } from './pages/SocCockpit';
import type { AuthResponse, HealthResponse } from './types/api';

export default function App() {
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    getCurrentUser()
      .then(setAuth)
      .catch(() => setAuth({ authenticated: false }))
      .finally(() => setCheckingAuth(false));
  }, []);

  useEffect(() => {
    if (!auth?.authenticated) return;
    let cancelled = false;
    const tick = () => {
      getHealth()
        .then((value) => {
          if (!cancelled) {
            setHealth(value);
            setHealthError(null);
          }
        })
        .catch((err: Error) => {
          if (!cancelled) setHealthError(err.message);
        });
    };
    tick();
    const id = window.setInterval(tick, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [auth?.authenticated]);

  const handleLogout = async () => {
    await logout();
    setAuth({ authenticated: false });
  };

  if (checkingAuth) {
    return (
      <TooltipProvider>
        <main className="soc-canvas soc-grid flex h-screen items-center justify-center p-6">
          <section className="soc-panel-strong rounded-xl p-8 text-center">
            <p className="soc-eyebrow text-cyan-300">Protected demo environment</p>
            <h1 className="mt-3 text-2xl font-semibold">Velocis AI SOC Assistant</h1>
            <p className="mt-2 text-sm text-slate-400">Checking access…</p>
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

  const username = auth.username ?? 'analyst';

  return (
    <TooltipProvider>
      <BrowserRouter>
        <AppShell username={username} health={health} healthError={healthError} onLogout={handleLogout}>
          <Routes>
            <Route path="/" element={<Navigate to="/cockpit" replace />} />
            <Route path="/cockpit" element={<SocCockpit />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/investigations" element={<InvestigationsPage />} />
            <Route path="/scenarios" element={<ScenariosPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/settings/providers" element={<SettingsPage />} />
            <Route path="/debug" element={<DebugPage />} />
            <Route path="*" element={<Navigate to="/cockpit" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </TooltipProvider>
  );
}
