import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster, toast } from 'sonner';
import { getCurrentUser, getHealth, logout, UNAUTHORIZED_EVENT } from './api/client';
import { AppShell } from './components/AppShell';
import { TooltipProvider } from './components/ui/tooltip';
import { ChatPage } from './pages/ChatPage';
import { DebugPage } from './pages/DebugPage';
import { InvestigationsPage } from './pages/InvestigationsPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { LlmLabPage } from './pages/LlmLabPage';
import { LoginPage } from './pages/LoginPage';
import { QualityPage } from './pages/QualityPage';
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
    const onProfileUpdated = (event: Event) => {
      const detail = (event as CustomEvent<AuthResponse>).detail;
      if (detail?.authenticated) {
        setAuth(detail);
      } else {
        void getCurrentUser().then(setAuth).catch(() => setAuth({ authenticated: false }));
      }
    };
    window.addEventListener('ai-soc-profile-updated', onProfileUpdated);
    return () => window.removeEventListener('ai-soc-profile-updated', onProfileUpdated);
  }, []);

  // Any gated API call returning 401 means the session expired/was invalidated.
  // Drop the cached auth state so the app bounces to the login screen instead of
  // leaving the user in a logged-in-looking shell where every call silently fails.
  useEffect(() => {
    const onUnauthorized = () => {
      setAuth((current) => {
        if (current && current.authenticated === false) return current;
        toast.error('Your session has expired. Please sign in again.');
        return { authenticated: false };
      });
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
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
        <main className="soc-canvas flex h-screen items-center justify-center p-6">
          <section className="soc-panel-strong rounded-xl p-8 text-center">
            <p className="soc-eyebrow text-cyan-300">Governed SOC workspace</p>
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
        <AppShell
          username={username}
          debugAccess={Boolean(auth.debug_access)}
          health={health}
          healthError={healthError}
          onLogout={handleLogout}
        >
          <Routes>
            <Route path="/" element={<Navigate to="/cockpit" replace />} />
            <Route path="/cockpit" element={<SocCockpit />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/llm-lab" element={<LlmLabPage />} />
            <Route path="/investigations" element={<InvestigationsPage />} />
            <Route path="/scenarios" element={<ScenariosPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/quality" element={<QualityPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/settings/providers" element={<SettingsPage />} />
            <Route path="/settings/mcp" element={<SettingsPage />} />
            <Route path="/settings/source-profiles" element={<SettingsPage />} />
            <Route path="/debug" element={<DebugPage />} />
            <Route path="*" element={<Navigate to="/cockpit" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </TooltipProvider>
  );
}
