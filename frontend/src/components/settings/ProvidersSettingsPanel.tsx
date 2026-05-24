import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Boxes, Eye, HelpCircle, PlugZap, Plus, Radar, SlidersHorizontal, Wrench } from 'lucide-react';
import { toast } from 'sonner';
import { checkProviderDraft } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { ProviderDraftCheckResult, ProviderRegistryItem, ProviderSettingsStatus, ProviderToolStatus, ProviderTypeValue } from '@/types/api';
import { BoolPill, SettingRow } from './SettingRow';

const PROVIDER_TYPE_OPTIONS: ProviderTypeValue[] = ['splunk_mcp', 'asset_inventory'];
const TOOL_GROUP_ORDER = ['discovery', 'context_lookup', 'event_query', 'asset_lookup', 'candidate_generation', 'explanation', 'optimization', 'execution', 'saved_search_execution', 'write_action', 'admin_action', 'unknown'];

export function ProvidersSettingsPanel({ status }: { status: ProviderSettingsStatus }) {
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
        <AddProviderDialog providerTypes={status.provider_types?.length ? status.provider_types : PROVIDER_TYPE_OPTIONS} />
      </header>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <SplunkCapabilityCard status={status} />
        <SaiaPanel status={status} />
      </div>

      <Card className="soc-panel">
        <CardHeader className="py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <Boxes className="h-4 w-4 text-cyan-400" /> Provider Registry
            </CardTitle>
            <div className="flex gap-1.5">
              <Badge variant="outline">{activeProviders.length} connected</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ProviderTable providers={providers} />
        </CardContent>
      </Card>

      <ToolDiscoveryPanel toolGroups={toolGroups} />

      <div className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
        {status.notes?.join(' ')}
      </div>
    </div>
  );
}

function SplunkCapabilityCard({ status }: { status: ProviderSettingsStatus }) {
  const splunk = status.splunk_capability ?? {};
  const coreCount = arrayLength(splunk.available_core_tools) ?? numberValue(splunk.discovered_core_tool_count) ?? 0;
  const saiaCount = arrayLength(splunk.available_saia_tools) ?? numberValue(splunk.discovered_saia_tool_count) ?? 0;

  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <PlugZap className="h-4 w-4 text-cyan-400" /> Splunk MCP Capability
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-x-5 md:grid-cols-2">
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
            <th className="py-2 pl-3 font-medium">Actions</th>
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
              <td className="py-2 pl-3">
                <div className="flex gap-1">
                  <Button type="button" variant="ghost" size="sm" className="h-8 px-2" title="View provider">
                    <Eye className="h-3.5 w-3.5" />
                  </Button>
                  <Button type="button" variant="ghost" size="sm" className="h-8 px-2" disabled title="Discover disabled in this stage">
                    <Radar className="h-3.5 w-3.5" />
                  </Button>
                  <Button type="button" variant="ghost" size="sm" className="h-8 px-2" disabled title="Edit disabled in this stage">
                    <SlidersHorizontal className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </td>
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

function AddProviderDialog({ providerTypes }: { providerTypes: ProviderTypeValue[] }) {
  const [providerType, setProviderType] = useState<ProviderTypeValue>('splunk_mcp');
  const [providerId, setProviderId] = useState('splunk_soc');
  const [displayName, setDisplayName] = useState('Splunk MCP');
  const [environmentMode, setEnvironmentMode] = useState('coe');
  const [enabled, setEnabled] = useState(true);
  const [discoveryMode, setDiscoveryMode] = useState('restricted');
  const [transport, setTransport] = useState('streamable_http');
  const [authMode, setAuthMode] = useState('bearer');
  const [baseUrl, setBaseUrl] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [notes, setNotes] = useState('');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<ProviderDraftCheckResult | null>(null);

  const handleProviderTypeChange = (value: string) => {
    setProviderType(value);
    setCheckResult(null);
    if (value === 'asset_inventory') {
      setProviderId('mock_asset_inventory');
      setDisplayName('Mock Asset Inventory');
      setTransport('mock');
      setAuthMode('none');
      setBaseUrl('');
      setAuthToken('');
      setUsername('');
      setPassword('');
      return;
    }
    setProviderId('splunk_soc');
    setDisplayName('Splunk MCP');
    setTransport('streamable_http');
    setAuthMode('bearer');
  };

  const handleCheck = async () => {
    setChecking(true);
    setCheckResult(null);
    try {
      const result = await checkProviderDraft({
        provider_id: providerId,
        display_name: displayName,
        provider_type: providerType,
        environment_mode: environmentMode,
        enabled,
        discovery_mode: discoveryMode,
        transport,
        auth_mode: authMode,
        base_url: baseUrl,
        auth_token: authToken,
        username,
        password,
        notes,
      });
      setCheckResult(result);
      if (result.validation_status === 'pass' && ['pass', 'reachable'].includes(result.connection_check.status)) {
        toast.success('Provider draft checked. Endpoint is reachable or mock-ready.');
      } else {
        toast.warning('Provider draft checked. Review validation or connection status.');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Provider check failed');
    } finally {
      setChecking(false);
    }
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button type="button" size="sm" className="gap-2">
          <Plus className="h-4 w-4" />
          Add Provider
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add / Check MCP Connection</DialogTitle>
          <DialogDescription>Enter the MCP endpoint details. Credentials are used only for this check and are not stored.</DialogDescription>
        </DialogHeader>
        <form className="mt-4 grid gap-3" onSubmit={(event) => event.preventDefault()}>
          <Field label="Connection name" help="Readable name shown in settings and traces.">
            <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Splunk MCP" />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="MCP URL" help="The endpoint URL supplied by the MCP server deployment.">
              <Input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://splunk-mcp.example.invalid/mcp" disabled={transport === 'mock' || transport === 'stdio'} />
            </Field>
            <Field label="MCP transport" help="How AI-SOC talks to the MCP server. Most URL-based MCP deployments use streamable_http.">
              <select value={transport} onChange={(event) => setTransport(event.target.value)} className="flex h-10 w-full rounded-lg border border-input bg-slate-950/70 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <option value="streamable_http">streamable_http</option>
                <option value="sse">sse</option>
                <option value="stdio">stdio</option>
                <option value="mock">mock</option>
              </select>
            </Field>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-950/55 p-3">
            <Field label="Authentication method" help="Select the authentication scheme required by this MCP server. The matching credential fields appear below.">
              <select value={authMode} onChange={(event) => setAuthMode(event.target.value)} className="flex h-10 w-full rounded-lg border border-input bg-slate-950/70 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <option value="none">none</option>
                <option value="bearer">bearer token</option>
                <option value="basic">username and password</option>
              </select>
            </Field>
            {authMode === 'bearer' ? (
              <div className="mt-3">
                <Field label="Bearer token" help="Sent as Authorization bearer token for this check only. It is not saved.">
                  <Input type="password" value={authToken} onChange={(event) => setAuthToken(event.target.value)} placeholder="not stored" />
                </Field>
              </div>
            ) : null}
            {authMode === 'basic' ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <Field label="Username">
                  <Input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="not stored" />
                </Field>
                <Field label="Password">
                  <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="not stored" />
                </Field>
              </div>
            ) : null}
            {authMode === 'none' ? <p className="mt-2 text-xs text-slate-500">No credential will be sent for the connection check.</p> : null}
          </div>
          <button type="button" onClick={() => setAdvancedOpen((value) => !value)} className="text-left text-xs font-medium text-cyan-300 hover:text-cyan-200">
            {advancedOpen ? 'Hide advanced connection settings' : 'Show advanced connection settings'}
          </button>
          {advancedOpen ? (
            <div className="grid gap-3 rounded-md border border-slate-800 bg-slate-950/45 p-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Internal provider key" help="Stable backend key for policies and traces. Keep unique.">
                  <Input value={providerId} onChange={(event) => setProviderId(event.target.value)} placeholder="splunk_soc" />
                </Field>
                <Field label="Provider kind" help="Only connected provider kinds are shown in this stage.">
                  <select value={providerType} onChange={(event) => handleProviderTypeChange(event.target.value)} className="flex h-10 w-full rounded-lg border border-input bg-slate-950/70 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    {providerTypes.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Deployment mode" help="Controls deployment safety behavior such as air-gapped fallback handling.">
                  <select value={environmentMode} onChange={(event) => setEnvironmentMode(event.target.value)} className="flex h-10 w-full rounded-lg border border-input bg-slate-950/70 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    <option value="coe">coe</option>
                    <option value="customer_test">customer_test</option>
                    <option value="production">production</option>
                    <option value="air_gapped">air_gapped</option>
                  </select>
                </Field>
                <Field label="Discovery policy" help="How AI-SOC treats MCP tool discovery metadata.">
                  <select value={discoveryMode} onChange={(event) => setDiscoveryMode(event.target.value)} className="flex h-10 w-full rounded-lg border border-input bg-slate-950/70 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    <option value="dynamic">dynamic</option>
                    <option value="restricted">restricted</option>
                    <option value="static_only">static_only</option>
                  </select>
                </Field>
                <Field label="Connection state">
                  <select value={String(enabled)} onChange={(event) => setEnabled(event.target.value === 'true')} className="flex h-10 w-full rounded-lg border border-input bg-slate-950/70 px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    <option value="false">disabled</option>
                    <option value="true">enabled</option>
                  </select>
                </Field>
              </div>
              <Field label="Notes">
                <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Operational notes, owner, or rollout assumptions." />
              </Field>
            </div>
          ) : null}
          {checkResult ? (
            <div className="rounded-md border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-300">
              <div className="flex flex-wrap gap-2">
                <Badge variant={checkResult.validation_status === 'pass' ? 'success' : 'destructive'}>validation {checkResult.validation_status}</Badge>
                <Badge variant={['pass', 'reachable'].includes(checkResult.connection_check.status) ? 'success' : 'warning'}>connection {checkResult.connection_check.status}</Badge>
                <Badge variant="secondary">not persisted</Badge>
              </div>
              <p className="mt-2 font-mono text-slate-400">{checkResult.connection_check.reason}</p>
              {checkResult.validation_errors.length ? <p className="mt-1 text-amber-200">{checkResult.validation_errors.join(', ')}</p> : null}
            </div>
          ) : null}
          <Button type="button" className="mt-1" onClick={handleCheck} disabled={checking}>
            {checking ? 'Checking…' : 'Save draft & check connection'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
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
