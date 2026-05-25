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
    <header
      className="soc-topbar sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-slate-800/80 px-4 lg:px-6"
      style={{ height: 'var(--shell-header)' }}
    >
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold tracking-tight">AI SOC Assistant</h1>
        <Badge>Experience Center</Badge>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant={backendOk ? 'success' : 'warning'} className="hidden md:inline-flex">
          <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current" />
          Backend {backendOk ? 'OK' : healthError ? 'Unavailable' : 'Checking'}
        </Badge>
        <div className="hidden items-center gap-1.5 rounded-md border border-slate-800 bg-slate-950/60 px-2.5 py-1.5 text-xs text-slate-300 md:flex">
          <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
          {username}
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={() => void onLogout()}>
          <LogOut className="h-3.5 w-3.5" />
          Logout
        </Button>
      </div>
    </header>
  );
}
