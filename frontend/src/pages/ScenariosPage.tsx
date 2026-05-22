import { Activity } from 'lucide-react';
import { AlertList } from '@/components/AlertList';
import { ScrollArea } from '@/components/ui/scroll-area';

export function ScenariosPage() {
  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header>
          <p className="soc-eyebrow text-cyan-400">Scenarios</p>
          <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
            <Activity className="h-4 w-4 text-cyan-400" />
            Demo Scenario Library
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Curated demo scenarios for the Experience Center. Mock data; no live alerting yet.
          </p>
        </header>
        <div className="max-w-xl">
          <AlertList />
        </div>
      </div>
    </ScrollArea>
  );
}
