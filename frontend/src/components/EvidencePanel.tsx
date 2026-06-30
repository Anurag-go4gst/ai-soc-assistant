import { FileSearch } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function EvidencePanel() {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <FileSearch className="h-4 w-4 text-cyan-400" />
          Evidence
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-slate-300">
        <div className="relative overflow-hidden rounded-lg border border-slate-800 bg-slate-950/70 p-3 pl-4">
          <span className="absolute inset-y-0 left-0 w-1 bg-cyan-400/70" />
          <Badge>Minimized context</Badge>
          <p className="mt-2 leading-relaxed">462 failed logins across 18 users from VPN segment.</p>
        </div>
        <div className="relative overflow-hidden rounded-lg border border-slate-800 bg-slate-950/70 p-3 pl-4">
          <span className="absolute inset-y-0 left-0 w-1 bg-emerald-400/60" />
          <Badge variant="secondary">Not sent to LLM</Badge>
          <p className="mt-2 leading-relaxed">Raw events and credentials stay outside reasoning payloads.</p>
        </div>
      </CardContent>
    </Card>
  );
}
