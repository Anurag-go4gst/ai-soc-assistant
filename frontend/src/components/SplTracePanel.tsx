import { TerminalSquare } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function SplTracePanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><TerminalSquare className="h-4 w-4 text-cyan-300" /> SPL Trace</CardTitle>
      </CardHeader>
      <CardContent>
        <Badge variant="success" className="mb-3">Validator: time range + aggregation present</Badge>
        <code className="block overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-cyan-100">
          index=auth earliest=-15m latest=now | stats count by user, src_ip
        </code>
      </CardContent>
    </Card>
  );
}
