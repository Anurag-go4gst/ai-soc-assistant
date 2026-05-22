import { ReactNode } from 'react';
import { SideNav, type SocSection } from './SideNav';
import { TopBar } from './TopBar';
import type { HealthResponse } from '@/types/api';

interface AppShellProps {
  activeSection: SocSection;
  children: ReactNode;
  health: HealthResponse | null;
  healthError: string | null;
  username: string;
  onLogout: () => Promise<void>;
  onSectionChange: (section: SocSection) => void;
}

export function AppShell({
  activeSection,
  children,
  health,
  healthError,
  username,
  onLogout,
  onSectionChange,
}: AppShellProps) {
  return (
    <main className="soc-canvas soc-grid min-h-screen text-slate-100">
      <div className="flex min-h-screen">
        <SideNav active={activeSection} onChange={onSectionChange} />
        <div className="min-w-0 flex-1">
          <TopBar username={username} health={health} healthError={healthError} onLogout={onLogout} />
          {children}
        </div>
      </div>
    </main>
  );
}
