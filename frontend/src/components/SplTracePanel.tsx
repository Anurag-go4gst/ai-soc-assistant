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
        <div className="mb-3 flex flex-wrap gap-2">
          <Badge variant="success">Validator: approved</Badge>
          <Badge variant="secondary">MCP execution disabled</Badge>
        </div>
        <code className="block overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-cyan-100">
          search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100
        </code>
        <p className="mt-2 text-xs text-slate-400">SPL validation complete. MCP execution is disabled.</p>
      </CardContent>
    </Card>
  );
}
