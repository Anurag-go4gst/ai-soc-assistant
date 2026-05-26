import { useState } from 'react';
import { Plug } from 'lucide-react';
import { toast } from 'sonner';
import { verifyMcpConnection } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { McpConnectionVerificationResult, SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, PlaceholderConnectorBanner, SettingRow } from './SettingRow';

export function McpSettingsPanel({ status }: { status: SettingsStatus['mcp'] }) {
  const servers = status.servers ?? [];
  const [verification, setVerification] = useState<McpConnectionVerificationResult | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const runVerification = async (action: 'validate' | 'test' | 'discover') => {
    setBusyAction(action);
    try {
      const result = await verifyMcpConnection(action);
      setVerification(result);
      toast[result.status === 'Connected' || result.status === 'Config valid, not tested' ? 'success' : 'warning'](result.failure_reason);
    } catch (err) {
      toast.error(`MCP ${action} failed: ${(err as Error).message}`);
    } finally {
      setBusyAction(null);
    }
  };
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
        <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="space-y-1">
              <p className="soc-eyebrow">Connection verification</p>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={verification?.status === 'Connected' ? 'success' : verification ? 'warning' : 'secondary'}>
                  {verification?.status ?? 'Not checked'}
                </Badge>
                {verification?.last_checked_time ? <span className="text-[0.65rem] text-slate-500">{new Date(verification.last_checked_time).toLocaleString()}</span> : null}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" disabled={!!busyAction} onClick={() => runVerification('validate')}>
                {busyAction === 'validate' ? 'Validating...' : 'Validate settings'}
              </Button>
              <Button type="button" variant="outline" size="sm" disabled={!!busyAction} onClick={() => runVerification('test')}>
                {busyAction === 'test' ? 'Testing...' : 'Test connection'}
              </Button>
              <Button type="button" variant="outline" size="sm" disabled={!!busyAction} onClick={() => runVerification('discover')}>
                {busyAction === 'discover' ? 'Discovering...' : 'Discover tools'}
              </Button>
            </div>
          </div>
          {verification ? <McpVerificationResult result={verification} /> : null}
        </div>
        <div>
          <SettingRow label="Mode" value={status.mode} mono />
          <SettingRow label="Default server" value={status.default_server ?? 'mock'} mono />
          <SettingRow label="Environment mode" value={status.environment_mode ?? 'coe'} mono />
          <SettingRow label="Splunk MCP enabled" value={<BoolPill value={status.splunk_mcp_enabled ?? false} />} />
          <SettingRow label="Discovery mode" value={status.splunk_mcp_discovery_mode ?? 'dynamic'} mono />
          <SettingRow label="Splunk AI Assistant mode" value={status.splunk_ai_assistant_mode ?? 'auto'} mono />
          <SettingRow label="SAIA tools enabled" value={<BoolPill value={status.splunk_saia_tools_enabled ?? false} />} />
          <SettingRow label="SAIA require discovery" value={<BoolPill value={status.splunk_saia_require_discovery ?? true} />} />
          <SettingRow label="Fallback required" value={<BoolPill value={status.fallback_required ?? true} trueLabel="yes" falseLabel="no" />} />
          <SettingRow label="Core tools discovered" value={status.discovered_core_tool_count ?? 0} mono />
          <SettingRow label="SAIA tools discovered" value={status.discovered_saia_tool_count ?? 0} mono />
          <SettingRow label="Run query requires validation" value={<BoolPill value={status.splunk_run_query_require_validation ?? true} />} />
          <SettingRow label="Saved search allowed" value={<BoolPill value={status.splunk_allow_run_saved_search ?? false} />} />
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
      </CardContent>
    </Card>
  );
}

function McpVerificationResult({ result }: { result: McpConnectionVerificationResult }) {
  return (
    <div data-testid="mcp-connection-result" className="mt-3 space-y-3 text-xs">
      <p className={result.status === 'Connected' ? 'text-emerald-200' : 'text-amber-100'}>{result.failure_reason}</p>
      <div className="grid gap-1 sm:grid-cols-2">
        <SettingRow label="URL configured" value={<BoolPill value={result.url_configured} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Authentication configured" value={<BoolPill value={result.authentication_configured} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Reachable" value={result.reachable === null ? 'not tested' : <BoolPill value={result.reachable} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Authenticated" value={result.authenticated === null ? 'not tested' : <BoolPill value={result.authenticated} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="MCP handshake" value={result.mcp_handshake} mono />
        <SettingRow label="Tools discovered" value={result.tools_discovered_count} mono />
        <SettingRow label="Splunk core tools" value={result.splunk_core_tools_discovered_count} mono />
        <SettingRow label="SAIA tools" value={result.saia_tools_discovered_count} mono />
        <SettingRow label="Execution policy" value={result.execution_policy} mono />
      </div>
      {result.tools.length ? (
        <div className="overflow-x-auto rounded border border-slate-800">
          <table className="w-full min-w-[520px] text-left text-[0.7rem]">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-2 py-1.5 font-medium">Tool</th>
                <th className="px-2 py-1.5 font-medium">Capability</th>
                <th className="px-2 py-1.5 font-medium">Classification</th>
                <th className="px-2 py-1.5 font-medium">Policy</th>
              </tr>
            </thead>
            <tbody>
              {result.tools.map((tool) => (
                <tr key={tool.name} className="border-t border-slate-800">
                  <td className="px-2 py-1.5 font-mono text-slate-200">{tool.name}</td>
                  <td className="px-2 py-1.5 font-mono text-slate-400">{tool.capability ?? 'unknown'}</td>
                  <td className="px-2 py-1.5 text-slate-400">{(tool.categories ?? []).join(', ') || 'unknown'}</td>
                  <td className="px-2 py-1.5">
                    <Badge variant={tool.blocked ? 'destructive' : 'secondary'}>{tool.blocked ? 'blocked' : 'discovery only'}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <details className="rounded border border-slate-800 bg-slate-950/60 px-2 py-1.5">
        <summary className="cursor-pointer text-slate-400">Technical details</summary>
        <p className="mt-2 break-words font-mono text-[0.65rem] text-slate-500">{result.technical_error_detail || 'none'}</p>
      </details>
    </div>
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
