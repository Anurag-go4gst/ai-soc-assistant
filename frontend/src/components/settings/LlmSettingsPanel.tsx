import { Brain } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, PlaceholderConnectorBanner, SettingRow } from './SettingRow';

export function LlmSettingsPanel({ status }: { status: SettingsStatus['llm'] }) {
  const providers = status.providers ?? [];
  const roles = status.role_resolution ?? {};
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Brain className="h-4 w-4 text-cyan-400" /> LLM Registry
          </CardTitle>
          <ModeBadge mode={status.mode} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="rounded-md border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
          Model connectivity only. Final synthesis and direct tool calling are disabled until later stages.
        </p>
        {status.implemented === false ? <PlaceholderConnectorBanner fallback={status.fallback} /> : null}
        {!status.enabled ? <PanelMockBanner /> : null}
        <div>
          <SettingRow label="Configured providers" value={(status.providers_configured ?? []).join(', ') || 'mock'} mono />
          <SettingRow label="Default provider" value={status.default_provider ?? 'mock'} mono />
          <SettingRow label="Global concurrency" value={status.global_concurrency ?? 4} mono />
          <SettingRow label="Canary completion" value={<BoolPill value={status.health_canary_enabled === true} trueLabel="enabled" falseLabel="disabled" />} />
          <SettingRow label="Configured" value={<BoolPill value={status.configured} />} />
          <SettingRow label="Available" value={<BoolPill value={status.available} />} />
          <SettingRow label="Timeout" value={`${status.timeout_seconds}s`} mono />
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
          <p className="soc-eyebrow mb-2">Role mapping</p>
          {['router', 'synthesis', 'reasoning', 'teacher', 'general'].map((role) => (
            <SettingRow key={role} label={role} value={roles[role] ?? 'unavailable'} mono />
          ))}
        </div>
        <div className="space-y-2">
          {providers.map((provider) => (
            <div key={provider.name} className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-100">{provider.name}</p>
                  <p className="text-xs text-slate-500">
                    {provider.type} · {provider.family} · {provider.model_role}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="outline" className="font-mono text-[0.65rem]">{provider.model || 'model missing'}</Badge>
                  <BoolPill value={provider.available} trueLabel="available" falseLabel="unavailable" />
                </div>
              </div>
              <div className="mt-3 grid gap-1 text-xs">
                <SettingRow label="Base URL" value={<BoolPill value={provider.base_url_configured} trueLabel="configured" falseLabel="not configured" />} />
                <SettingRow label="API key" value={<BoolPill value={provider.api_key_configured} trueLabel="configured" falseLabel="not configured" />} />
                <SettingRow label="Auth mode" value={provider.auth_mode} mono />
                <SettingRow label="JSON mode" value={<BoolPill value={provider.supports_json_mode} />} />
                <SettingRow label="Streaming" value={<BoolPill value={provider.supports_streaming} />} />
                <SettingRow label="Tool calling" value={<BoolPill value={provider.supports_tool_calling} trueLabel="enabled" falseLabel="disabled" />} />
                <SettingRow label="Concurrency" value={provider.concurrency_limit} mono />
                {provider.context_tokens ? <SettingRow label="Context" value={`${provider.context_tokens.toLocaleString()} tok`} mono /> : null}
                {provider.max_output_tokens ? <SettingRow label="Max output" value={`${provider.max_output_tokens.toLocaleString()} tok`} mono /> : null}
                {provider.last_error ? <SettingRow label="Last error" value={provider.last_error} mono /> : null}
              </div>
            </div>
          ))}
        </div>
        <p className="text-[0.65rem] text-slate-500">Endpoint URLs and API keys are never exposed by this surface.</p>
        <Button type="button" variant="outline" size="sm" disabled className="w-full">
          Test model (disabled in readiness stage)
        </Button>
      </CardContent>
    </Card>
  );
}
