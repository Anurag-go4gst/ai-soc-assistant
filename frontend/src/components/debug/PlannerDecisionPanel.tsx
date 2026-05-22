import { BrainCircuit } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function PlannerDecisionPanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><BrainCircuit className="h-4 w-4 text-cyan-300" /> LLM Planner Decision</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Badge>route: investigate_alert</Badge>
        <p className="text-slate-400">confidence: 0.62 · source: mock planner · no LLM call yet</p>
      </CardContent>
    </Card>
  );
}
