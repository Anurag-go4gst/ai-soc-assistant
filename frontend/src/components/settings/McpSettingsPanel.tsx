import { useEffect, useState } from 'react';
import { Plug, Save } from 'lucide-react';
import { toast } from 'sonner';
import { getMcpConnection, saveMcpConnection, verifyMcpConnection } from '@/api/client';
import type { McpConnectionConfig } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { McpConnectionVerificationResult, SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, PlaceholderConnectorBanner, SettingRow } from './SettingRow';

const HUMAN_ERROR: Record<string, string> = {
  mcp_url_is_required: 'MCP URL is required.',
  mcp_url_is_not_valid: 'MCP URL must be an http(s) URL from the Splunk MCP app.',
  bearer_token_is_required: 'Bearer token is required.',
  timeout_seconds_must_be_positive: 'Timeout must be greater than 0.',
  execution_enablement_requires_env_change_control: 'Execution must stay disabled here; enable live execution only through change-controlled env flags.',
};

export function McpSettingsPanel({ status }: { status: SettingsStatus['mcp'] }) {
  const servers = status.servers ?? [];
  const [conn, setConn] = useState<McpConnectionConfig | null>(null);
  const [bearerToken, setBearerToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [verification, setVerification] = useState<McpConnectionVerificationResult | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const loadConnection = () => {
    void getMcpConnection()
      .then((r) => setConn(r.connection))
      .catch(() => setConn(null));
  };

  useEffect(loadConnection, []);

  const patch = (partial: Partial<McpConnectionConfig>) => setConn((current) => (current ? { ...current, ...partial } : current));

  const saveConnection = async () => {
    if (!conn || saving) return;
    setSaving(true);
    try {
      const result = await saveMcpConnection({
        enabled: conn.enabled,
        deployment_mode: conn.deployment_mode,
        discovery_policy: conn.discovery_policy,
        transport: conn.transport,
        auth_method: conn.auth_method,
        url: conn.url,
        bearer_token: bearerToken,
        timeout_seconds: conn.timeout_seconds,
        saia_tools_enabled: conn.saia_tools_enabled && conn.deployment_mode !== 'air_gapped',
        splunk_ai_assistant_mode: conn.splunk_ai_assistant_mode,
        allow_saved_search: conn.allow_saved_search,
        execution_enabled: false,
      });
      if (result.saved) {
        setConn(result.connection);
        setBearerToken('');
        toast.success('Splunk MCP connection saved.');
      } else {
        const msg = result.validation_errors.map((e) => HUMAN_ERROR[e] ?? e).join(' ');
        toast.error(msg || 'Validation failed.');
      }
    } catch (err) {
      toast.error(`Save failed: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

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
        {conn ? (
          <div className="rounded-md border border-cyan-500/20 bg-slate-950/50 p-3">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="soc-eyebrow">Splunk MCP connection</p>
                <p className="text-xs text-slate-500">Paste the exact endpoint URL from the Splunk MCP Server app (include /mcp if shown).</p>
              </div>
              <Badge variant="secondary" className="text-[0.65rem]">
                source: {conn.source}
              </Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">Enabled</Label>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={conn.enabled}
                    onChange={(e) => patch({ enabled: e.target.checked })}
                    className="h-4 w-4 accent-cyan-500"
                  />
                  <span className="text-xs text-slate-400">Use configured Splunk MCP server</span>
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Environment</Label>
                <select
                  value={conn.deployment_mode}
                  onChange={(e) =>
                    patch({
                      deployment_mode: e.target.value,
                      saia_tools_enabled: e.target.value === 'air_gapped' ? false : conn.saia_tools_enabled,
                    })
                  }
                  className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40"
                >
                  {['coe', 'customer_test', 'production', 'air_gapped'].map((mode) => (
                    <option key={mode} value={mode}>
                      {mode}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="mt-3 space-y-1">
              <Label className="text-xs">MCP endpoint URL</Label>
              <Input
                value={conn.url}
                onChange={(e) => patch({ url: e.target.value })}
                placeholder="https://<MCP_SERVER_ENDPOINT>"
                className="text-sm"
              />
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">Bearer token {conn.bearer_token_configured ? '(configured - leave blank to keep)' : ''}</Label>
                <Input
                  type="password"
                  value={bearerToken}
                  onChange={(e) => setBearerToken(e.target.value)}
                  placeholder={conn.bearer_token_configured ? 'stored encrypted token' : 'Splunk MCP encrypted token'}
                  className="text-sm"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Timeout (s)</Label>
                <Input
                  type="number"
                  value={conn.timeout_seconds}
                  onChange={(e) => patch({ timeout_seconds: Number(e.target.value) || 0 })}
                  className="text-sm"
                />
              </div>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">Discovery policy</Label>
                <select
                  value={conn.discovery_policy}
                  onChange={(e) => patch({ discovery_policy: e.target.value })}
                  className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40"
                >
                  {['dynamic', 'restricted', 'static_only'].map((policy) => (
                    <option key={policy} value={policy}>
                      {policy}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Allow saved search execution</Label>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={conn.allow_saved_search}
                    onChange={(e) => patch({ allow_saved_search: e.target.checked })}
                    className="h-4 w-4 accent-cyan-500"
                  />
                  <span className="text-xs text-slate-400">Enable splunk_run_saved_search in tool allowlist (COE-reviewed only)</span>
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Splunk AI Assistant tools</Label>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    disabled={conn.deployment_mode === 'air_gapped'}
                    checked={conn.saia_tools_enabled && conn.deployment_mode !== 'air_gapped'}
                    onChange={(e) => patch({ saia_tools_enabled: e.target.checked })}
                    className="h-4 w-4 accent-cyan-500"
                  />
                  <span className="text-xs text-slate-400">{conn.deployment_mode === 'air_gapped' ? 'disabled for air-gapped' : 'include saia_* if discovered'}</span>
                </div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button size="sm" disabled={saving} onClick={() => void saveConnection()} className="gap-1">
                <Save className="h-3.5 w-3.5" />
                {saving ? 'Saving...' : 'Save connection'}
              </Button>
              <span className="text-xs text-slate-500">Search execution remains blocked until global and server execution flags are enabled outside the UI.</span>
            </div>
          </div>
        ) : null}
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
          <SettingRow label="Splunk AI tools enabled" value={<BoolPill value={status.splunk_saia_tools_enabled ?? false} />} />
          <SettingRow label="Splunk AI tools must be discovered" value={<BoolPill value={status.splunk_saia_require_discovery ?? true} />} />
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
                    <SettingRow label="Splunk AI SPL generation" value={<BoolPill value={server.saia_spl_generation_allowed === true} trueLabel="allowed" falseLabel="blocked" />} />
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
        <SettingRow label="Server handshake" value={result.mcp_handshake} mono />
        <SettingRow label="Tools discovered" value={result.tools_discovered_count} mono />
        <SettingRow label="Splunk core tools" value={result.splunk_core_tools_discovered_count} mono />
        <SettingRow label="Splunk AI tools" value={result.saia_tools_discovered_count} mono />
        <SettingRow label="Execution policy" value={result.execution_policy === 'gated' ? 'Gated; discovery only' : result.execution_policy} mono />
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
                    <Badge variant={tool.blocked ? 'destructive' : 'secondary'}>{tool.blocked ? 'blocked by policy' : 'discovery only'}</Badge>
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
