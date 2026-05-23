import { Plug } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, PlaceholderConnectorBanner, SettingRow } from './SettingRow';

export function McpSettingsPanel({ status }: { status: SettingsStatus['mcp'] }) {
  const servers = status.servers ?? [];
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Plug className="h-4 w-4 text-cyan-400" /> MCP Registry
          </CardTitle>
          <ModeBadge mode={status.mode} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="rounded-md border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
          Connection readiness only. MCP tool execution is disabled until SPL validation and execution stage.
        </p>
        {status.implemented === false ? <PlaceholderConnectorBanner fallback={status.fallback} /> : null}
        {!status.enabled ? <PanelMockBanner /> : null}
        <div>
          <SettingRow label="Mode" value={status.mode} mono />
          <SettingRow label="Default server" value={status.default_server ?? 'mock'} mono />
          <SettingRow label="Execution disabled globally" value={<BoolPill value={!(status.global_execution_enabled ?? false)} />} />
          <SettingRow label="Configured" value={<BoolPill value={status.configured} />} />
          <SettingRow label="Available" value={<BoolPill value={status.available} />} />
        </div>
        <div className="space-y-2">
          {servers.map((server) => (
            <div key={server.name} className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-100">{server.name}</p>
                  <p className="text-xs text-slate-500">
                    {server.type} · {server.transport}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <BoolPill value={server.enabled} trueLabel="enabled" falseLabel="disabled" />
                  <BoolPill value={server.configured} trueLabel="configured" falseLabel="missing config" />
                  <BoolPill value={server.available} trueLabel="available" falseLabel="unavailable" />
                </div>
              </div>
              <div className="mt-3 grid gap-1 text-xs">
                <SettingRow label="URL" value={<BoolPill value={server.url_configured} trueLabel="configured" falseLabel="not configured" />} />
                <SettingRow label="Command" value={<BoolPill value={server.command_configured} trueLabel="configured" falseLabel="not configured" />} />
                <SettingRow label="Auth" value={`${server.auth_mode} / ${server.auth_configured ? 'configured' : 'not configured'}`} mono />
                <SettingRow label="Execution" value={<BoolPill value={server.execution_enabled} trueLabel="enabled" falseLabel="blocked" />} />
                {server.last_error ? <SettingRow label="Last error" value={server.last_error} mono /> : null}
                {server.type === 'splunk' ? (
                  <>
                    <SettingRow label="Splunk app" value={server.splunk_app_id ?? '7931'} mono />
                    <SettingRow label="SAIA/SPL generation" value={<BoolPill value={server.saia_spl_generation_allowed === true} trueLabel="allowed" falseLabel="blocked" />} />
                  </>
                ) : null}
              </div>
              <SettingList label="Discovered tools" items={server.discovered_tools_safe_names} />
              <SettingList label="Blocked tools" items={server.blocked_tools_safe_names} />
            </div>
          ))}
        </div>
        <Button type="button" variant="outline" size="sm" disabled className="w-full">
          Test connection (disabled in readiness stage)
        </Button>
      </CardContent>
    </Card>
  );
}

function SettingList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="space-y-1.5">
      <p className="soc-eyebrow">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.length === 0 ? <span className="text-xs text-slate-500">none</span> : null}
        {items.map((item) => (
          <Badge key={item} variant="outline" className="font-mono text-[0.65rem]">
            {item}
          </Badge>
        ))}
      </div>
    </div>
  );
}
