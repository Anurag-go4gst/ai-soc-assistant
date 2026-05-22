import { LineChart } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, SettingRow } from './SettingRow';

export function ObservabilityPanel({ status }: { status: SettingsStatus['observability'] }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <LineChart className="h-4 w-4 text-cyan-400" /> Observability
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <SettingRow label="Telemetry enabled" value={<BoolPill value={status.telemetry_enabled} />} />
          <SettingRow label="Trace logging enabled" value={<BoolPill value={status.trace_logging_enabled} />} />
          <SettingRow label="Audit sink status" value={status.audit_sink_status} mono />
          <SettingRow label="Planned Splunk audit index" value={status.audit_index} mono />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Metric label="Recent trace" value={status.recent_trace ?? '—'} />
          <Metric label="Planner/det mismatch" value={status.planner_deterministic_mismatch_count.toString()} />
          <Metric label="Fallback count" value={status.fallback_count.toString()} />
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/60 p-2.5">
      <p className="soc-eyebrow">{label}</p>
      <p className="mt-1 truncate font-mono text-xs text-slate-100" title={value}>
        {value}
      </p>
    </div>
  );
}
