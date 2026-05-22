import { ReactNode } from 'react';
import { SideNav } from './SideNav';
import { TopBar } from './TopBar';
import type { HealthResponse } from '@/types/api';

interface AppShellProps {
  children: ReactNode;
  health: HealthResponse | null;
  healthError: string | null;
  username: string;
  onLogout: () => Promise<void>;
}

export function AppShell({ children, health, healthError, username, onLogout }: AppShellProps) {
  return (
    <div className="soc-canvas soc-grid flex h-screen overflow-hidden text-slate-100">
      <SideNav />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar username={username} health={health} healthError={healthError} onLogout={onLogout} />
        <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
