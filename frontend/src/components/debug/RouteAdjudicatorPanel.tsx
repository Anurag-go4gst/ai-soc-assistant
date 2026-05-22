import { Scale } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function RouteAdjudicatorPanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Scale className="h-4 w-4 text-cyan-300" /> Route Adjudicator</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Badge variant="success">selected: deterministic_router</Badge>
        <p className="text-slate-400">Reason: deterministic confidence exceeds planner by governed threshold.</p>
      </CardContent>
    </Card>
  );
}
