import { Route } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function DeterministicRouterPanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Route className="h-4 w-4 text-cyan-300" /> Deterministic Router</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Badge variant="success">route: investigate_authentication</Badge>
        <p className="text-slate-400">confidence: 0.80 · matched brute/login rule</p>
      </CardContent>
    </Card>
  );
}
