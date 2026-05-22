import { Activity, Database, Factory } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

const scenarios = [
  {
    title: 'Brute-force Login Spike',
    asset: 'APP-01',
    severity: 'Critical',
    icon: Activity,
    className: 'border-red-400/40 bg-red-500/10',
  },
  {
    title: 'DB Connection Pool Exhaustion',
    asset: 'ORDERS-DB',
    severity: 'High',
    icon: Database,
    className: 'border-amber-400/40 bg-amber-500/10',
  },
  {
    title: 'OT Grid Anomaly',
    asset: 'SUBSTATION-7',
    severity: 'Medium',
    icon: Factory,
    className: 'border-cyan-400/40 bg-cyan-500/10',
  },
];

export function AlertList() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle>Alert / Scenario Rail</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {scenarios.map((scenario) => {
          const Icon = scenario.icon;
          return (
            <button key={scenario.title} type="button" className={cn('w-full rounded-xl border p-3 text-left transition hover:border-cyan-400/60', scenario.className)}>
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-950/50">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold">{scenario.title}</span>
                  <span className="mt-1 block text-xs text-slate-400">{scenario.asset}</span>
                  <Badge variant={scenario.severity === 'Critical' ? 'destructive' : scenario.severity === 'High' ? 'warning' : 'default'} className="mt-2">
                    {scenario.severity}
                  </Badge>
                </span>
              </div>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}
