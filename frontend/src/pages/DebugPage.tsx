import { Bug } from 'lucide-react';
import { CompareResultPanel } from '@/components/debug/CompareResultPanel';
import { DeterministicRouterPanel } from '@/components/debug/DeterministicRouterPanel';
import { NodeTimeline } from '@/components/debug/NodeTimeline';
import { PlannerDecisionPanel } from '@/components/debug/PlannerDecisionPanel';
import { RouteAdjudicatorPanel } from '@/components/debug/RouteAdjudicatorPanel';
import { SplTracePanel } from '@/components/SplTracePanel';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

const MOCK_TOOL_TRACE = [
  { step: 'plan', tool: 'planner', latency_ms: 412, status: 'ok' },
  { step: 'route', tool: 'route_adjudicator', latency_ms: 18, status: 'ok' },
  { step: 'tool_call', tool: 'splunk_run_query', latency_ms: 247, status: 'mock' },
  { step: 'synth', tool: 'synthesizer', latency_ms: 311, status: 'ok' },
];

const MOCK_RAW_RESPONSE = {
  trace_id: 'mock-00000000-0000-0000-0000-000000000000',
  route: 'llm_primary',
  planner: { confidence: 0.82, plan: ['search', 'summarize'] },
  deterministic: { confidence: 0.74, plan: ['search', 'summarize'] },
  compare: 'agree',
  message: 'Placeholder synth output.',
  evidence: { minimized_count: 3 },
};

export function DebugPage() {
  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="soc-eyebrow text-cyan-400">Debug</p>
            <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
              <Bug className="h-4 w-4 text-cyan-400" />
              Planner / Router / Compare Traces
            </h2>
          </div>
          <Badge variant="secondary">Internal — mock data</Badge>
        </header>

        <section className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          <PlannerDecisionPanel />
          <DeterministicRouterPanel />
          <CompareResultPanel />
          <RouteAdjudicatorPanel />
          <NodeTimeline />
          <SplTracePanel />
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
          <Card className="soc-panel">
            <CardHeader className="py-3">
              <CardTitle className="text-sm font-semibold">Tool Trace</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1 pr-3">Step</th>
                    <th className="py-1 pr-3">Tool</th>
                    <th className="py-1 pr-3">Latency</th>
                    <th className="py-1">Status</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  {MOCK_TOOL_TRACE.map((row) => (
                    <tr key={row.step} className="border-t border-slate-800/70">
                      <td className="py-1.5 pr-3 font-mono">{row.step}</td>
                      <td className="py-1.5 pr-3">{row.tool}</td>
                      <td className="py-1.5 pr-3 font-mono">{row.latency_ms} ms</td>
                      <td className="py-1.5">
                        <Badge variant={row.status === 'ok' ? 'success' : 'secondary'}>{row.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card className="soc-panel">
            <CardHeader className="py-3">
              <CardTitle className="text-sm font-semibold">Raw Mock Response</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-80 overflow-auto rounded-md border border-slate-800 bg-slate-950/70 p-3 text-[0.7rem] leading-relaxed text-slate-300">
                {JSON.stringify(MOCK_RAW_RESPONSE, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </section>
      </div>
    </ScrollArea>
  );
}
