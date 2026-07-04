import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Boxes, HelpCircle, PlugZap, Radar, Save, Wrench } from 'lucide-react';
import { toast } from 'sonner';
import { getMcpConnection, saveMcpConnection, verifyMcpConnection } from '@/api/client';
import type { McpConnectionConfig } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { McpConnectionVerificationResult, ProviderRegistryItem, ProviderSettingsStatus, ProviderToolStatus } from '@/types/api';
import { BoolPill, SettingRow } from './SettingRow';

const TOOL_GROUP_ORDER = ['discovery', 'context_lookup', 'event_query', 'asset_lookup', 'candidate_generation', 'explanation', 'optimization', 'execution', 'saved_search_execution', 'write_action', 'admin_action', 'unknown'];
const HUMAN_ERROR: Record<string, string> = {
  mcp_url_is_required: 'MCP URL is required.',
  mcp_url_is_not_valid: 'MCP URL must be an http(s) URL from the Splunk MCP app.',
  bearer_token_is_required: 'Bearer token is required.',
  timeout_seconds_must_be_positive: 'Timeout must be greater than 0.',
};

export function ProvidersSettingsPanel({ status, onStatusChange }: { status: ProviderSettingsStatus; onStatusChange?: () => void }) {
  const providers = status.providers ?? [];
  const toolGroups = status.tool_groups ?? {};

  const activeProviders = useMemo(() => providers.filter((provider) => provider.available || provider.enabled), [providers]);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="soc-eyebrow text-cyan-400">Providers & MCP</p>
          <h3 className="mt-1 text-base font-semibold text-slate-100">Integration readiness</h3>
        </div>
      </header>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <SplunkCapabilityCard status={status} onStatusChange={onStatusChange} />
        <SaiaPanel status={status} />
      </div>

      <Card className="soc-panel">
        <CardHeader className="py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <Boxes className="h-4 w-4 text-cyan-400" /> Provider Registry
            </CardTitle>
            <div className="flex gap-1.5">
              <Badge variant="outline">{activeProviders.length} configured</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ProviderTable providers={providers} />
        </CardContent>
      </Card>

      <ToolDiscoveryPanel toolGroups={toolGroups} />
    </div>
  );
}

function SplunkCapabilityCard({ status, onStatusChange }: { status: ProviderSettingsStatus; onStatusChange?: () => void }) {
  const splunk = status.splunk_capability ?? {};
  const coreCount = arrayLength(splunk.available_core_tools) ?? numberValue(splunk.discovered_core_tool_count) ?? 0;
  const saiaCount = arrayLength(splunk.available_saia_tools) ?? numberValue(splunk.discovered_saia_tool_count) ?? 0;
  const [verification, setVerification] = useState<McpConnectionVerificationResult | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [conn, setConn] = useState<McpConnectionConfig | null>(null);
  const [bearerToken, setBearerToken] = useState('');
  const [saving, setSaving] = useState(false);

  const loadConnection = () => {
    void getMcpConnection()
      .then((result) => setConn(result.connection))
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
        execution_enabled: conn.execution_enabled,
      });
      if (result.saved) {
        setConn(result.connection);
        setBearerToken('');
        onStatusChange?.();
        toast.success('Splunk MCP connection saved.');
      } else {
        const msg = result.validation_errors.map((error) => HUMAN_ERROR[error] ?? error).join(' ');
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
      loadConnection();
      onStatusChange?.();
      toast[result.status === 'Connected' ? 'success' : 'warning'](result.failure_reason);
    } catch (err) {
      toast.error(`MCP ${action} failed: ${(err as Error).message}`);
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <PlugZap className="h-4 w-4 text-cyan-400" /> Splunk MCP Capability
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-x-5 md:grid-cols-2">
        {conn ? (
          <div className="mb-3 rounded-md border border-cyan-500/20 bg-slate-950/50 p-3 md:col-span-2">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="soc-eyebrow">Splunk connection</p>
                <p className="text-xs text-slate-500">Endpoint and token are stored locally; the token is write-only.</p>
              </div>
              <Badge variant="secondary" className="text-[0.65rem]">
                source: {conn.source}
              </Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Connection enabled">
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input type="checkbox" checked={conn.enabled} onChange={(event) => patch({ enabled: event.target.checked })} className="h-4 w-4 accent-cyan-500" />
                  Use configured Splunk MCP server
                </label>
              </Field>
              <Field label="Environment">
                <select
                  value={conn.deployment_mode}
                  onChange={(event) => patch({ deployment_mode: event.target.value, saia_tools_enabled: event.target.value === 'air_gapped' ? false : conn.saia_tools_enabled })}
                  className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40"
                >
                  {['coe', 'customer_test', 'production', 'air_gapped'].map((mode) => (
                    <option key={mode} value={mode}>
                      {mode}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="mt-3">
              <Field label="MCP endpoint URL">
                <Input value={conn.url} onChange={(event) => patch({ url: event.target.value })} placeholder="https://<MCP_SERVER_ENDPOINT>" className="text-sm" />
              </Field>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label={`Bearer token ${conn.bearer_token_configured ? '(configured - leave blank to keep)' : ''}`}>
                <Input type="password" value={bearerToken} onChange={(event) => setBearerToken(event.target.value)} placeholder={conn.bearer_token_configured ? 'stored token' : 'Splunk MCP token'} className="text-sm" />
              </Field>
              <Field label="Timeout (s)">
                <Input type="number" value={conn.timeout_seconds} onChange={(event) => patch({ timeout_seconds: Number(event.target.value) || 0 })} className="text-sm" />
              </Field>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Discovery policy">
                <select value={conn.discovery_policy} onChange={(event) => patch({ discovery_policy: event.target.value })} className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40">
                  {['dynamic', 'restricted', 'static_only'].map((policy) => (
                    <option key={policy} value={policy}>
                      {policy}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Allow live searches in chat">
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input type="checkbox" checked={conn.execution_enabled} onChange={(event) => patch({ execution_enabled: event.target.checked })} className="h-4 w-4 accent-cyan-500" />
                  Enable the Splunk MCP execution gate for validated searches
                </label>
              </Field>
              <Field label="Allow saved search execution">
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input type="checkbox" checked={conn.allow_saved_search} onChange={(event) => patch({ allow_saved_search: event.target.checked })} className="h-4 w-4 accent-cyan-500" />
                  Include splunk_run_saved_search in the tool allowlist
                </label>
              </Field>
              <Field label="Splunk AI Assistant tools">
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input type="checkbox" disabled={conn.deployment_mode === 'air_gapped'} checked={conn.saia_tools_enabled && conn.deployment_mode !== 'air_gapped'} onChange={(event) => patch({ saia_tools_enabled: event.target.checked })} className="h-4 w-4 accent-cyan-500" />
                  {conn.deployment_mode === 'air_gapped' ? 'disabled for air-gapped' : 'include saia_* if discovered'}
                </label>
              </Field>
            </div>
            {conn.last_error ? (
              <div className="mt-3 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
                <p>{conn.last_error}</p>
                {conn.last_technical_detail ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-amber-200">Error details</summary>
                    <p className="mt-2 break-words font-mono text-[0.65rem] text-amber-100/80">{conn.last_technical_detail}</p>
                  </details>
                ) : null}
              </div>
            ) : null}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button size="sm" disabled={saving} onClick={() => void saveConnection()} className="gap-1">
                <Save className="h-3.5 w-3.5" />
                {saving ? 'Saving...' : 'Save connection'}
              </Button>
              <BoolPill value={conn.bearer_token_configured} trueLabel="token configured" falseLabel="token missing" />
            </div>
          </div>
        ) : null}
        <div className="mb-3 rounded-md border border-slate-800 bg-slate-950/50 p-3 md:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="soc-eyebrow">Connection status</p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <Badge variant={(verification?.status ?? conn?.last_check_status) === 'Connected' ? 'success' : verification || conn?.last_check_status ? 'warning' : 'secondary'}>{verification?.status ?? conn?.last_check_status ?? 'Not checked'}</Badge>
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
          {verification ? (
            <div className="mt-3 space-y-2 text-xs">
              <p className={verification.status === 'Connected' ? 'text-emerald-200' : 'text-amber-100'}>{verification.failure_reason}</p>
              <div className="grid gap-1 sm:grid-cols-2">
                <SettingRow label="URL configured" value={<BoolPill value={verification.url_configured} trueLabel="yes" falseLabel="no" />} />
                <SettingRow label="Authentication configured" value={<BoolPill value={verification.authentication_configured} trueLabel="yes" falseLabel="no" />} />
                <SettingRow label="Reachable" value={verification.reachable === null ? 'not tested' : <BoolPill value={verification.reachable} trueLabel="yes" falseLabel="no" />} />
                <SettingRow label="Authenticated" value={verification.authenticated === null ? 'not tested' : <BoolPill value={verification.authenticated} trueLabel="yes" falseLabel="no" />} />
                <SettingRow label="Server handshake" value={verification.mcp_handshake} mono />
                <SettingRow label="Tools discovered" value={verification.tools_discovered_count} mono />
                <SettingRow label="Splunk core tools" value={verification.splunk_core_tools_discovered_count} mono />
                <SettingRow label="Splunk AI tools" value={verification.saia_tools_discovered_count} mono />
                <SettingRow label="Execution policy" value={verification.execution_policy === 'gated' ? 'Gated; discovery only' : verification.execution_policy} mono />
              </div>
              <details className="rounded border border-slate-800 bg-slate-950/60 px-2 py-1.5">
                <summary className="cursor-pointer text-slate-400">Technical details</summary>
                <p className="mt-2 break-words font-mono text-[0.65rem] text-slate-500">{verification.technical_error_detail || 'none'}</p>
              </details>
            </div>
          ) : null}
        </div>
        <SettingRow label="MCP available" value={<BoolPill value={Boolean(splunk.mcp_available)} trueLabel="available" falseLabel="unavailable" />} />
        <SettingRow label="Core splunk_* tools" value={<BoolPill value={Boolean(splunk.core_splunk_tools_available)} trueLabel="available" falseLabel="missing" />} />
        <SettingRow label="SAIA available" value={<BoolPill value={Boolean(splunk.saia_available)} trueLabel="available" falseLabel="not found" />} />
        <SettingRow label="SAIA usable" value={<BoolPill value={Boolean(splunk.saia_usable)} trueLabel="usable" falseLabel="fallback" />} />
        <SettingRow label="Fallback required" value={<BoolPill value={Boolean(splunk.fallback_required)} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Environment mode" value={String(splunk.environment_mode ?? 'coe')} mono />
        <SettingRow label="Discovery mode" value={String(splunk.discovery_mode ?? 'dynamic')} mono />
        <SettingRow label="Run query validation" value={<BoolPill value={Boolean(splunk.run_query_requires_validation ?? true)} trueLabel="required" falseLabel="not required" />} />
        <SettingRow label="Saved search" value={<BoolPill value={Boolean(splunk.run_saved_search_allowed)} trueLabel="allowed" falseLabel="blocked" />} />
        <SettingRow label="Core tool count" value={coreCount} mono />
        <SettingRow label="SAIA tool count" value={saiaCount} mono />
        <SettingRow label="Last discovered" value={String(splunk.discovered_at ?? 'not reported')} mono className="md:col-span-2" />
      </CardContent>
    </Card>
  );
}

function SaiaPanel({ status }: { status: ProviderSettingsStatus }) {
  const saia = status.saia;
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Radar className="h-4 w-4 text-cyan-400" /> Splunk AI Assistant
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="rounded-md border border-cyan-400/20 bg-cyan-400/8 px-3 py-2 text-xs text-cyan-100">
          SAIA tools are available only when Splunk AI Assistant is installed. If unavailable, AI-SOC fallback providers are used.
        </p>
        <div>
          <SettingRow label="Mode" value={saia.splunk_ai_assistant_mode} mono />
          <SettingRow label="Discovered" value={<BoolPill value={saia.saia_discovered} trueLabel="yes" falseLabel="no" />} />
          <SettingRow label="Usable" value={<BoolPill value={saia.saia_usable} trueLabel="yes" falseLabel="no" />} />
          <SettingRow label="Fallback active" value={<BoolPill value={saia.fallback_active} trueLabel="yes" falseLabel="no" />} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(saia.features).map(([name, enabled]) => (
            <div key={name} className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2">
              <p className="text-xs font-medium text-slate-200">{name}</p>
              <BoolPill value={enabled} trueLabel="enabled" falseLabel="disabled" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ProviderTable({ providers }: { providers: ProviderRegistryItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[920px] text-left text-xs">
        <thead className="border-b border-slate-800 text-slate-500">
          <tr>
            <th className="py-2 pr-3 font-medium">Provider name</th>
            <th className="px-3 py-2 font-medium">Provider type</th>
            <th className="px-3 py-2 font-medium">Enabled/status</th>
            <th className="px-3 py-2 font-medium">Environment mode</th>
            <th className="px-3 py-2 font-medium">Available</th>
            <th className="px-3 py-2 font-medium">Discovered</th>
            <th className="px-3 py-2 font-medium">HIL ops</th>
            <th className="px-3 py-2 font-medium">Last discovered</th>
          </tr>
        </thead>
        <tbody>
          {providers.map((provider) => (
            <tr key={provider.provider_id} className="border-b border-slate-900 last:border-b-0">
              <td className="py-2 pr-3">
                <div className="font-medium text-slate-100">{provider.display_name}</div>
                <div className="font-mono text-[0.68rem] text-slate-500">{provider.provider_id}</div>
              </td>
              <td className="px-3 py-2 font-mono text-slate-300">{provider.provider_type}</td>
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1">
                  <BoolPill value={provider.enabled} trueLabel="enabled" falseLabel="disabled" />
                <Badge variant={provider.available ? 'success' : 'warning'}>{provider.status}</Badge>
                </div>
              </td>
              <td className="px-3 py-2 font-mono text-slate-300">{provider.environment_mode}</td>
              <td className="px-3 py-2">
                <BoolPill value={provider.available} trueLabel="yes" falseLabel="no" />
              </td>
              <td className="px-3 py-2 font-mono text-slate-300">
                {provider.discovered_operations_count} ops / {provider.discovered_tools_count} tools
              </td>
              <td className="px-3 py-2 font-mono text-slate-300">{provider.hil_required_operations_count}</td>
              <td className="px-3 py-2 font-mono text-slate-400">{provider.last_discovered ?? 'not run'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ToolDiscoveryPanel({ toolGroups }: { toolGroups: Record<string, ProviderToolStatus[]> }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Wrench className="h-4 w-4 text-cyan-400" /> Tool Discovery
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 xl:grid-cols-2">
        {TOOL_GROUP_ORDER.filter((category) => (toolGroups[category] ?? []).length > 0).map((category) => (
          <ToolGroup key={category} category={category} tools={toolGroups[category] ?? []} />
        ))}
      </CardContent>
    </Card>
  );
}

function ToolGroup({ category, tools }: { category: string; tools: ProviderToolStatus[] }) {
  return (
    <section className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="font-mono text-xs font-semibold text-slate-200">{category}</h4>
        <Badge variant={tools.length ? 'outline' : 'secondary'}>{tools.length}</Badge>
      </div>
      <div className="space-y-2">
        {tools.length === 0 ? <p className="text-xs text-slate-500">No discovered tools.</p> : null}
        {tools.map((tool) => (
          <div key={`${tool.provider_id}:${tool.tool_name}`} className="rounded border border-slate-900 bg-slate-950 px-2 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-mono text-xs text-slate-100">{tool.tool_name}</p>
                <p className="text-[0.68rem] text-slate-500">{tool.server_name}</p>
              </div>
              <div className="flex flex-wrap gap-1">
                <Badge variant={tool.blocked ? 'destructive' : tool.allowed ? 'success' : 'secondary'}>{tool.blocked ? 'blocked' : tool.allowed ? 'allowed' : 'not allowed'}</Badge>
                {tool.requires_hil ? <Badge variant="warning">HIL</Badge> : null}
              </div>
            </div>
            <div className="mt-2 grid gap-1 sm:grid-cols-2">
              <MiniFlag label="execution eligible" value={tool.execution_eligible} />
              <MiniFlag label="evidence supported" value={tool.source_evidence_supported} />
            </div>
            {tool.blocked_reason ? <p className="mt-1 font-mono text-[0.68rem] text-amber-300">{tool.blocked_reason}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function MiniFlag({ label, value }: { label: string; value: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 text-[0.68rem] text-slate-400">
      <span>{label}</span>
      <span className={cn('font-mono', value ? 'text-emerald-300' : 'text-slate-500')}>{value ? 'yes' : 'no'}</span>
    </div>
  );
}

function Field({ label, children, help }: { label: string; children: ReactNode; help?: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5">
        <Label>{label}</Label>
        {help ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" className="text-slate-500 hover:text-slate-300" aria-label={`${label} help`}>
                <HelpCircle className="h-3.5 w-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-72">{help}</TooltipContent>
          </Tooltip>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' ? value : null;
}

function arrayLength(value: unknown): number | null {
  return Array.isArray(value) ? value.length : null;
}
