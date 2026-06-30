import { Network } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function GraphContextPanel() {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Network className="h-4 w-4 text-cyan-400" /> Graph Context
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-slate-300">
        {['APP-01 -> auth_index', 'vpn_pool -> 203.0.113.0/24', 'user cohort -> privileged candidates'].map((item) => (
          <div
            key={item}
            className="flex items-center gap-2.5 rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 font-mono text-xs text-slate-300 transition hover:border-cyan-500/40 hover:bg-slate-900/60"
          >
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400/70" />
            {item}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
