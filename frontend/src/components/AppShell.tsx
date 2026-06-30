import { ReactNode } from 'react';
import { SideNav } from './SideNav';
import { TopBar } from './TopBar';
import type { HealthResponse } from '@/types/api';

interface AppShellProps {
  children: ReactNode;
  health: HealthResponse | null;
  healthError: string | null;
  username: string;
  debugAccess?: boolean;
  onLogout: () => Promise<void>;
}

export function AppShell({ children, health, healthError, username, debugAccess = false, onLogout }: AppShellProps) {
  return (
    <div className="soc-canvas flex h-[100dvh] max-h-[100dvh] w-full overflow-hidden text-slate-100">
      <SideNav debugAccess={debugAccess} />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar username={username} health={health} healthError={healthError} onLogout={onLogout} />
        <main className="min-h-0 min-w-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
