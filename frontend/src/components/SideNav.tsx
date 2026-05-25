import { NavLink } from 'react-router-dom';
import {
  Activity,
  Bug,
  DatabaseZap,
  FileSearch,
  LayoutDashboard,
  MessageSquareText,
  Network,
  Settings as SettingsIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/cockpit', label: 'Cockpit', icon: LayoutDashboard },
  { to: '/chat', label: 'Chat', icon: MessageSquareText },
  { to: '/investigations', label: 'Investigations', icon: FileSearch },
  { to: '/scenarios', label: 'Scenarios', icon: Activity },
  { to: '/knowledge', label: 'Knowledge', icon: DatabaseZap },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
  { to: '/debug', label: 'Debug', icon: Bug },
] as const;

export function SideNav() {
  return (
    <aside
      className="hidden shrink-0 border-r border-slate-800/80 bg-slate-950/85 px-3 py-4 backdrop-blur-md lg:flex lg:flex-col"
      style={{ width: 'var(--shell-sidebar)' }}
    >
      <div className="mb-6 flex items-center gap-3 px-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-500 text-slate-950">
          <Network className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold">V.AI SOC</p>
          <p className="text-[0.65rem] text-slate-500">Experience Center</p>
        </div>
      </div>
      <nav className="flex flex-col gap-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition',
                  isActive
                    ? 'border border-cyan-500/25 bg-cyan-500/8 text-cyan-100'
                    : 'text-slate-400 hover:bg-slate-900/70 hover:text-slate-100',
                )
              }
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
      <p className="mt-auto px-2 pt-4 text-xs font-medium text-slate-400">
        Connected · index=pgcil_soc
      </p>
    </aside>
  );
}
