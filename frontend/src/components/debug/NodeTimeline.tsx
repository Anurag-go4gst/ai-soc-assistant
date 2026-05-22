import { Clock3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const nodes = ['ingress', 'planner', 'deterministic_router', 'compare', 'adjudicator', 'response'];

export function NodeTimeline() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-cyan-300" /> Node Timeline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {nodes.map((node, index) => (
          <div key={node} className="flex items-center gap-3 text-sm text-slate-300">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-400/10 text-xs text-cyan-200">{index + 1}</span>
            {node}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
