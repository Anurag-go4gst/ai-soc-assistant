import { GitCompareArrows } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function CompareResultPanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><GitCompareArrows className="h-4 w-4 text-cyan-300" /> Compare Node</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Badge variant="warning">match: false</Badge>
        <p className="text-slate-400">learning label: planner_under_specific · fallback: deterministic preferred</p>
      </CardContent>
    </Card>
  );
}
