import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function EvidencePanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle>Evidence</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-slate-300">
        <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
          <Badge>Minimized context</Badge>
          <p className="mt-2">462 failed logins across 18 users from VPN segment.</p>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
          <Badge variant="secondary">Not sent to LLM</Badge>
          <p className="mt-2">Raw events and credentials stay outside reasoning payloads.</p>
        </div>
      </CardContent>
    </Card>
  );
}
