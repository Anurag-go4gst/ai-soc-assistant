import { LogOut, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { HealthResponse } from '@/types/api';

interface TopBarProps {
  username: string;
  health: HealthResponse | null;
  healthError: string | null;
  onLogout: () => Promise<void>;
}

export function TopBar({ username, health, healthError, onLogout }: TopBarProps) {
  const backendOk = health?.status === 'ok';

  return (
    <header className="soc-topbar sticky top-0 z-20 border-b border-slate-800/90">
      <div className="flex min-h-16 items-center justify-between gap-4 px-4 py-3 lg:px-6">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg font-bold tracking-tight">AI SOC Assistant</h1>
            <Badge>Experience Center</Badge>
            <Badge variant="secondary">Mock Routing Mode</Badge>
          </div>
          <p className="mt-1 text-xs text-slate-500">Governed investigation cockpit for Splunk assistant workflows</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={backendOk ? 'success' : 'warning'} className="hidden sm:inline-flex">
            <span className="mr-2 h-2 w-2 rounded-full bg-current" />
            Backend {backendOk ? 'OK' : healthError ? 'Unavailable' : 'Checking'}
          </Badge>
          <div className="hidden items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-300 md:flex">
            <ShieldCheck className="h-4 w-4 text-cyan-300" />
            {username}
          </div>
          <Button type="button" variant="secondary" size="sm" onClick={() => void onLogout()}>
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </div>
      </div>
    </header>
  );
}
