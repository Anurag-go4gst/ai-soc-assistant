import { Brain } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, SettingRow } from './SettingRow';

export function LlmSettingsPanel({ status }: { status: SettingsStatus['llm'] }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Brain className="h-4 w-4 text-cyan-400" /> LLM Routing
          </CardTitle>
          <ModeBadge mode={status.mode} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {!status.enabled ? <PanelMockBanner /> : null}
        <div>
          <SettingRow label="LLM enabled" value={<BoolPill value={status.enabled} />} />
          <SettingRow label="Primary model" value={status.primary_model} mono />
          <SettingRow label="Reasoning enabled" value={<BoolPill value={status.reasoning_enabled} />} />
          <SettingRow
            label="Instruct endpoint"
            value={<BoolPill value={status.instruct_endpoint_configured} trueLabel="configured" falseLabel="not configured" />}
          />
          <SettingRow
            label="Reasoning endpoint"
            value={<BoolPill value={status.reasoning_endpoint_configured} trueLabel="configured" falseLabel="not configured" />}
          />
          <SettingRow label="Temperature" value={status.temperature} mono />
          <SettingRow label="Timeout" value={`${status.timeout_seconds}s`} mono />
          <SettingRow label="Max context" value={`${status.max_context_tokens.toLocaleString()} tok`} mono />
        </div>
        <p className="text-[0.65rem] text-slate-500">Endpoint URLs and API keys are never exposed by this surface.</p>
        <Button type="button" variant="outline" size="sm" disabled className="w-full">
          Test model (disabled in mock mode)
        </Button>
      </CardContent>
    </Card>
  );
}
