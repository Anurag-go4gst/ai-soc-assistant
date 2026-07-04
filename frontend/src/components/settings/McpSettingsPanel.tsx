import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Pencil, Plug, Radar, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { deleteOtherMcpServer, getOtherMcpServers, saveOtherMcpServer, verifyOtherMcpServer } from '@/api/client';
import type { OtherMcpServerConfig } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { McpConnectionVerificationResult, SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, SettingRow } from './SettingRow';

const INITIAL_FORM = {
  server_id: 'asset_inventory',
  display_name: 'Asset inventory',
  provider_type: 'asset_inventory',
  enabled: true,
  transport: 'streamable_http',
  auth_method: 'none',
  url: '',
  bearer_token: '',
  timeout_seconds: 10,
  execution_enabled: false,
};

const HUMAN_ERROR: Record<string, string> = {
  server_id_is_required: 'Server id is required.',
  splunk_server_managed_on_providers_tab: 'Splunk is configured on Providers/MCP.',
  provider_kind_is_not_supported: 'Provider type is not supported.',
  mcp_url_is_required: 'MCP URL is required.',
  mcp_url_is_not_valid: 'MCP URL must be an http(s) URL.',
  bearer_token_is_required: 'Bearer token is required.',
  timeout_seconds_must_be_positive: 'Timeout must be greater than 0.',
};

export function McpSettingsPanel({ status, onStatusChange }: { status: SettingsStatus['mcp']; onStatusChange?: () => void }) {
  const [servers, setServers] = useState<OtherMcpServerConfig[]>([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [editingServerId, setEditingServerId] = useState<string | null>(null);
  const [editingUrlConfigured, setEditingUrlConfigured] = useState(false);
  const [editingTokenConfigured, setEditingTokenConfigured] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyServer, setBusyServer] = useState<string | null>(null);
  const [verification, setVerification] = useState<Record<string, McpConnectionVerificationResult>>({});

  const loadServers = () => {
    void getOtherMcpServers()
      .then((payload) => setServers(payload.servers ?? []))
      .catch((err: Error) => toast.error(`MCP servers unavailable: ${err.message}`));
  };

  useEffect(loadServers, []);

  const patch = (partial: Partial<typeof INITIAL_FORM>) => setForm((current) => ({ ...current, ...partial }));

  const resetForm = () => {
    setForm({ ...INITIAL_FORM, bearer_token: '' });
    setEditingServerId(null);
    setEditingUrlConfigured(false);
    setEditingTokenConfigured(false);
  };

  const saveServer = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const result = await saveOtherMcpServer(form);
      if (result.saved) {
        toast.success('MCP server saved.');
        resetForm();
        loadServers();
        onStatusChange?.();
      } else {
        toast.error(result.validation_errors.map((error) => HUMAN_ERROR[error] ?? error).join(' ') || 'Validation failed.');
      }
    } catch (err) {
      toast.error(`Save failed: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const runServerCheck = async (serverId: string, action: 'test' | 'discover') => {
    setBusyServer(`${serverId}:${action}`);
    try {
      const payload = await verifyOtherMcpServer(serverId, action);
      setVerification((current) => ({ ...current, [serverId]: payload.result }));
      if (payload.server) {
        setServers((current) => current.map((server) => (server.server_id === serverId ? payload.server! : server)));
      }
      onStatusChange?.();
      toast[payload.result.status === 'Connected' ? 'success' : 'warning'](payload.result.failure_reason);
    } catch (err) {
      toast.error(`MCP ${action} failed: ${(err as Error).message}`);
    } finally {
      setBusyServer(null);
    }
  };

  const removeServer = async (serverId: string) => {
    try {
      const result = await deleteOtherMcpServer(serverId);
      if (result.deleted) {
        toast.success('MCP server removed.');
        loadServers();
        onStatusChange?.();
      }
    } catch (err) {
      toast.error(`Remove failed: ${(err as Error).message}`);
    }
  };

  const editServer = (server: OtherMcpServerConfig) => {
    setEditingServerId(server.server_id);
    setEditingUrlConfigured(server.url_configured);
    setEditingTokenConfigured(server.bearer_token_configured);
    setForm({
      server_id: server.server_id,
      display_name: server.display_name,
      provider_type: server.provider_type,
      enabled: server.enabled,
      transport: server.transport,
      auth_method: server.auth_method,
      url: '',
      bearer_token: '',
      timeout_seconds: server.timeout_seconds,
      execution_enabled: server.execution_enabled,
    });
  };

  const isEditing = editingServerId !== null;

  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Plug className="h-4 w-4 text-cyan-400" /> MCP Registry
          </CardTitle>
          <ModeBadge mode={status.mode} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-cyan-500/20 bg-slate-950/50 p-3">
          <div>
            <p className="soc-eyebrow">Splunk provider</p>
            <p className="text-xs text-slate-400">Save Splunk URL, token, tests, tools, and live-search policy on Providers/MCP.</p>
          </div>
          <Button asChild size="sm" variant="outline" className="gap-1">
            <Link to="/settings/providers">
              Configure Splunk <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>

        <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="soc-eyebrow">{isEditing ? 'Edit other MCP' : 'Add other MCP'}</p>
              <p className="text-xs text-slate-500">
                {isEditing
                  ? 'URL and bearer token are write-only. Leave blank to keep the stored values.'
                  : 'Other MCP servers can be saved and tested here. Live chat search is Splunk-only today.'}
              </p>
            </div>
            <Badge variant={status.global_execution_enabled ? 'warning' : 'secondary'}>{status.global_execution_enabled ? 'global execution on' : 'global execution off'}</Badge>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Server id">
              <Input value={form.server_id} onChange={(event) => patch({ server_id: event.target.value })} disabled={isEditing} className="text-sm" />
            </Field>
            <Field label="Display name">
              <Input value={form.display_name} onChange={(event) => patch({ display_name: event.target.value })} className="text-sm" />
            </Field>
            <Field label="Provider type">
              <select value={form.provider_type} onChange={(event) => patch({ provider_type: event.target.value })} className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40">
                {['generic', 'asset_inventory', 'ticketing', 'knowledge'].map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Transport">
              <select value={form.transport} onChange={(event) => patch({ transport: event.target.value })} className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40">
                {['streamable_http', 'sse'].map((transport) => (
                  <option key={transport} value={transport}>
                    {transport}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`MCP URL${isEditing && editingUrlConfigured ? ' (configured — leave blank to keep)' : ''}`}>
              <Input
                value={form.url}
                onChange={(event) => patch({ url: event.target.value })}
                placeholder={isEditing && editingUrlConfigured ? 'stored endpoint URL' : 'https://mcp.example.invalid/mcp'}
                className="text-sm"
              />
            </Field>
            <Field label="Authentication">
              <select value={form.auth_method} onChange={(event) => patch({ auth_method: event.target.value })} className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40">
                {['none', 'bearer'].map((auth) => (
                  <option key={auth} value={auth}>
                    {auth}
                  </option>
                ))}
              </select>
            </Field>
            {form.auth_method === 'bearer' ? (
              <Field label={`Bearer token${isEditing && editingTokenConfigured ? ' (configured — leave blank to keep)' : ''}`}>
                <Input
                  type="password"
                  value={form.bearer_token}
                  onChange={(event) => patch({ bearer_token: event.target.value })}
                  placeholder={isEditing && editingTokenConfigured ? 'stored token' : 'write-only token'}
                  className="text-sm"
                />
              </Field>
            ) : null}
            <Field label="Timeout (s)">
              <Input type="number" value={form.timeout_seconds} onChange={(event) => patch({ timeout_seconds: Number(event.target.value) || 0 })} className="text-sm" />
            </Field>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input type="checkbox" checked={form.enabled} onChange={(event) => patch({ enabled: event.target.checked })} className="h-4 w-4 accent-cyan-500" />
              Store this MCP server as configured
            </label>
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input type="checkbox" checked={form.execution_enabled} onChange={(event) => patch({ execution_enabled: event.target.checked })} className="h-4 w-4 accent-cyan-500" />
              Registry execution flag only
            </label>
          </div>
          <p className="mt-2 text-xs text-slate-500">Live chat search is Splunk-only today; this flag records readiness for non-Splunk MCP servers.</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={saving} onClick={() => void saveServer()} className="gap-1">
              <Save className="h-3.5 w-3.5" />
              {saving ? 'Saving...' : isEditing ? 'Save changes' : 'Save other MCP'}
            </Button>
            {isEditing ? (
              <Button type="button" size="sm" variant="ghost" onClick={resetForm}>
                Cancel edit
              </Button>
            ) : null}
          </div>
        </div>

        <div className="space-y-2">
          {servers.length === 0 ? <p className="rounded-md border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs text-slate-500">No other MCP servers saved.</p> : null}
          {servers.map((server) => (
            <ServerCard
              key={server.server_id}
              server={server}
              result={verification[server.server_id]}
              busyServer={busyServer}
              onEdit={editServer}
              onRemove={(serverId) => void removeServer(serverId)}
              onCheck={(serverId, action) => void runServerCheck(serverId, action)}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ServerCard({
  server,
  result,
  busyServer,
  onEdit,
  onRemove,
  onCheck,
}: {
  server: OtherMcpServerConfig;
  result?: McpConnectionVerificationResult;
  busyServer: string | null;
  onEdit: (server: OtherMcpServerConfig) => void;
  onRemove: (serverId: string) => void;
  onCheck: (serverId: string, action: 'test' | 'discover') => void;
}) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-100">{server.display_name}</p>
          <p className="font-mono text-xs text-slate-500">
            {server.server_id} · {server.provider_type} · {server.transport}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <BoolPill value={server.enabled} trueLabel="configured" falseLabel="disabled" />
          <BoolPill value={server.auth_configured} trueLabel="auth configured" falseLabel="auth missing" />
          <Badge variant={server.last_check_status === 'Connected' ? 'success' : server.last_check_status ? 'warning' : 'secondary'}>{server.last_check_status ?? 'not checked'}</Badge>
        </div>
      </div>
      <div className="mt-3 grid gap-1 text-xs sm:grid-cols-2">
        <SettingRow label="URL" value={<BoolPill value={server.url_configured} trueLabel="configured" falseLabel="not configured" />} />
        <SettingRow label="Auth" value={`${server.auth_method} / ${server.auth_configured ? 'configured' : 'not configured'}`} mono />
        <SettingRow label="Execution" value={<BoolPill value={server.execution_enabled} trueLabel="registry flag on" falseLabel="chat unavailable" />} />
        <SettingRow label="Tools" value={server.discovered_tools.length} mono />
      </div>
      {server.last_error ? (
        <div className="mt-3 rounded border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
          <p>{server.last_error}</p>
          {server.last_technical_detail ? (
            <details className="mt-2">
              <summary className="cursor-pointer text-amber-200">Error details</summary>
              <p className="mt-2 break-words font-mono text-[0.65rem] text-amber-100/80">{server.last_technical_detail}</p>
            </details>
          ) : null}
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" disabled={!!busyServer} onClick={() => onCheck(server.server_id, 'test')}>
          {busyServer === `${server.server_id}:test` ? 'Testing...' : 'Test'}
        </Button>
        <Button type="button" variant="outline" size="sm" disabled={!!busyServer} onClick={() => onCheck(server.server_id, 'discover')} className="gap-1">
          <Radar className="h-3.5 w-3.5" />
          {busyServer === `${server.server_id}:discover` ? 'Discovering...' : 'Discover'}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => onEdit(server)} className="gap-1">
          <Pencil className="h-3.5 w-3.5" />
          Edit
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => onRemove(server.server_id)} className="gap-1 text-red-300 hover:text-red-200">
          <Trash2 className="h-3.5 w-3.5" />
          Remove
        </Button>
      </div>
      {result ? <McpVerificationResult result={result} /> : null}
      <SettingList label="Discovered tools" items={server.discovered_tools.map((tool) => (typeof tool === 'string' ? tool : tool.name)).filter(Boolean)} />
    </div>
  );
}

function McpVerificationResult({ result }: { result: McpConnectionVerificationResult }) {
  return (
    <div data-testid="mcp-connection-result" className="mt-3 space-y-3 text-xs">
      <p className={result.status === 'Connected' ? 'text-emerald-200' : 'text-amber-100'}>{result.failure_reason}</p>
      <div className="grid gap-1 sm:grid-cols-2">
        <SettingRow label="Reachable" value={result.reachable === null ? 'not tested' : <BoolPill value={result.reachable} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Authenticated" value={result.authenticated === null ? 'not tested' : <BoolPill value={result.authenticated} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Server handshake" value={result.mcp_handshake} mono />
        <SettingRow label="Tools discovered" value={result.tools_discovered_count} mono />
      </div>
      <details className="rounded border border-slate-800 bg-slate-950/60 px-2 py-1.5">
        <summary className="cursor-pointer text-slate-400">Technical details</summary>
        <p className="mt-2 break-words font-mono text-[0.65rem] text-slate-500">{result.technical_error_detail || 'none'}</p>
      </details>
    </div>
  );
}

function SettingList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="mt-3 space-y-1.5">
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

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}
