import { Route } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, SettingRow } from './SettingRow';

export function RoutingSettingsPanel({ status }: { status: SettingsStatus['routing'] }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Route className="h-4 w-4 text-cyan-400" /> Routing Policy
          </CardTitle>
          <Badge>{status.mode}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <SettingRow label="Routing mode" value={status.mode} mono />
          <SettingRow label="Deterministic router" value={<BoolPill value={status.deterministic_router_enabled} />} />
          <SettingRow label="LLM shadow router" value={<BoolPill value={status.llm_shadow_router_enabled} />} />
          <SettingRow label="Compare logging" value={<BoolPill value={status.compare_logging_enabled} />} />
          <SettingRow label="Disagreement sink" value={status.disagreement_logging_sink} mono />
          <SettingRow label="DB disagreement logging" value={<BoolPill value={status.db_disagreement_logging_enabled} />} />
          <SettingRow label="Chat endpoint wired" value={<BoolPill value={status.chat_query_endpoint_wired} />} />
          <SettingRow label="Workflow planner" value={<BoolPill value={status.workflow_planner_enabled} />} />
          <SettingRow label="Workflow execution" value={<BoolPill value={status.workflow_planner_execution_enabled} />} />
          <SettingRow label="Workflow plan DB logging" value={<BoolPill value={status.workflow_plan_logging_enabled} />} />
          <SettingRow label="Deterministic threshold" value={status.deterministic_threshold} mono />
          <SettingRow label="LLM planner enabled" value={<BoolPill value={status.llm_planner_enabled} />} />
          <SettingRow label="Shadow router" value={<BoolPill value={status.shadow_router_enabled} />} />
          <SettingRow label="Compare node" value={<BoolPill value={status.compare_node_enabled} />} />
          <SettingRow label="Adjudicator policy" value={status.adjudicator_policy} mono />
          <SettingRow label="Fallback policy" value={status.fallback_policy} mono />
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
          <p className="soc-eyebrow mb-2">Confidence thresholds</p>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <ThresholdCell label="high" value={`≥ ${status.confidence_thresholds.high}`} tone="success" />
            <ThresholdCell label="medium" value={`≥ ${status.confidence_thresholds.medium}`} tone="warning" />
            <ThresholdCell label="low" value={`< ${status.confidence_thresholds.low}`} tone="destructive" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ThresholdCell({ label, value, tone }: { label: string; value: string; tone: 'success' | 'warning' | 'destructive' }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/40 p-2">
      <p className="soc-eyebrow">{label}</p>
      <Badge variant={tone} className="mt-1 font-mono">
        {value}
      </Badge>
    </div>
  );
}
