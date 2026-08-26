import { FormEvent, useState } from 'react';
import { ArrowRight, Bot, CheckCircle2, LockKeyhole, Network, Radar, ShieldCheck, Workflow } from 'lucide-react';
import { login } from '../api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
    <main className="soc-canvas min-h-screen text-slate-100">
      <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-xl">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-400 text-slate-950 shadow-glow">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <p className="text-base font-semibold tracking-tight">Velocis AI SOC Assistant</p>
              <p className="text-xs font-medium text-slate-400">Analyst access verification</p>
            </div>
          </div>
          <Badge variant="success" className="hidden md:inline-flex">
            <span className="mr-2 h-2 w-2 rounded-full bg-emerald-400" />
            Governed workspace
          </Badge>
        </div>
      </header>

      <section className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-7xl items-center gap-8 px-5 py-10 sm:px-6 lg:grid-cols-[1.06fr_0.94fr] lg:px-8">
        <div className="max-w-3xl">
          <Badge className="mb-6 gap-2">
            <ShieldCheck className="h-4 w-4" />
            Governed AI investigation workspace
          </Badge>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
            SOC triage with visible routing, evidence, and safeguards.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">
            Validate analyst access, review governed evidence, compare routing decisions, and keep every AI step explainable before any execution is authorized.
          </p>
          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            {[
              { icon: Radar, label: 'Alert triage', text: 'Governed investigation flow' },
              { icon: Workflow, label: 'Route compare', text: 'Planner vs deterministic router' },
              { icon: Network, label: 'Evidence graph', text: 'Context ready for GraphRAG' },
            ].map((item) => (
              <Card key={item.label} className="soc-panel">
                <CardContent className="p-4">
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-200">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <p className="font-semibold">{item.label}</p>
                  <p className="mt-1 text-sm leading-5 text-slate-400">{item.text}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <Card className="soc-panel overflow-hidden" aria-labelledby="login-title">
          <CardHeader className="border-b border-slate-800 bg-slate-900/70">
            <div className="flex items-start justify-between gap-4">
              <div>
                <CardTitle id="login-title" className="text-2xl">Sign in</CardTitle>
                <p className="mt-2 text-sm leading-6 text-slate-400">Use your authorized analyst account.</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-400/10 text-cyan-200">
                <LockKeyhole className="h-5 w-5" />
              </div>
            </div>
          </CardHeader>

          <form className="space-y-5 p-6" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                autoComplete="username"
                id="username"
                name="username"
                onChange={(event) => setUsername(event.target.value)}
                required
                type="text"
                value={username}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                autoComplete="current-password"
                id="password"
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </div>

            {error ? <div className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm font-medium text-red-100">{error}</div> : null}

            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? 'Verifying...' : <>Continue <ArrowRight className="h-4 w-4" /></>}
            </Button>
          </form>

          <div className="grid gap-3 border-t border-slate-800 bg-slate-900/60 px-6 py-5 text-sm text-slate-300 sm:grid-cols-3">
            {['Session cookie', 'SSL proxy', 'Local backend'].map((item) => (
              <div key={item} className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                {item}
              </div>
            ))}
          </div>
        </Card>
      </section>
    </main>
  );
}
