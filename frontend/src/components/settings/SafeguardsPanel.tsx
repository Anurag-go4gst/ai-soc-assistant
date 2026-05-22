import { ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, SettingRow } from './SettingRow';

export function SafeguardsPanel({ status }: { status: SettingsStatus['safeguards'] }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck className="h-4 w-4 text-emerald-400" /> Safeguards
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <SettingRow label="SPL validator" value={<BoolPill value={status.spl_validator_enabled} />} />
          <SettingRow label="Time range required" value={<BoolPill value={status.time_range_required} />} />
          <SettingRow label="Aggregation required" value={<BoolPill value={status.aggregation_required} />} />
          <SettingRow label="Raw event dump blocked" value={<BoolPill value={status.raw_event_dump_blocked} />} />
          <SettingRow label="Write-back approval required" value={<BoolPill value={status.write_approval_required} />} />
          <SettingRow label="Evidence validation" value={<BoolPill value={status.evidence_validation_enabled} />} />
          <SettingRow label="Prompt injection filter" value={<BoolPill value={status.prompt_injection_filter_enabled} />} />
        </div>
        <div>
          <p className="soc-eyebrow mb-1.5">Blocked SPL commands</p>
          <div className="flex flex-wrap gap-1.5">
            {status.blocked_spl_commands.map((cmd) => (
              <Badge key={cmd} variant="destructive" className="font-mono text-[0.65rem]">
                {cmd}
              </Badge>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
