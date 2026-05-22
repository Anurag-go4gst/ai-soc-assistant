import { Network } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function GraphContextPanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Network className="h-4 w-4 text-cyan-300" /> Graph Context</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-slate-300">
        {['APP-01 -> auth_index', 'vpn_pool -> 203.0.113.0/24', 'user cohort -> privileged candidates'].map((item) => (
          <div key={item} className="rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2">{item}</div>
        ))}
      </CardContent>
    </Card>
  );
}
