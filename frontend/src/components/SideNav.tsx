import { Activity, Bug, DatabaseZap, FileSearch, LayoutDashboard, MessageSquareText, Network } from 'lucide-react';
import { cn } from '@/lib/utils';

export type SocSection = 'cockpit' | 'chat' | 'investigations' | 'scenarios' | 'knowledge' | 'debug';

const navItems: Array<{ id: SocSection; label: string; icon: typeof LayoutDashboard }> = [
  { id: 'cockpit', label: 'Cockpit', icon: LayoutDashboard },
  { id: 'chat', label: 'Chat', icon: MessageSquareText },
  { id: 'investigations', label: 'Investigations', icon: FileSearch },
  { id: 'scenarios', label: 'Scenarios', icon: Activity },
  { id: 'knowledge', label: 'Knowledge', icon: DatabaseZap },
  { id: 'debug', label: 'Debug', icon: Bug },
];

interface SideNavProps {
  active: SocSection;
  onChange: (section: SocSection) => void;
}

export function SideNav({ active, onChange }: SideNavProps) {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-slate-800/90 bg-slate-950/80 p-4 backdrop-blur-xl lg:block">
      <div className="mb-6 flex items-center gap-3 px-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400 text-slate-950 shadow-glow">
          <Network className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-bold">AI SOC Assistant</p>
          <p className="text-xs text-slate-500">Splunk-ready scaffold</p>
        </div>
      </div>
      <nav className="space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={cn(
                'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-semibold transition',
                active === item.id
                  ? 'border border-cyan-400/30 bg-cyan-400/10 text-cyan-100 shadow-sm'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-100',
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
