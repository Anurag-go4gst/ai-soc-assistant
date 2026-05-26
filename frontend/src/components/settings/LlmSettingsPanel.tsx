import { useState } from 'react';
import { Brain, Pencil } from 'lucide-react';
import { toast } from 'sonner';
import { checkLlmSettingsDraft, verifyLlmConnection } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { LlmConnectionVerificationResult, LlmGovernanceStatus, LlmSettingsDraftCheckResult, SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, PlaceholderConnectorBanner, SettingRow } from './SettingRow';

const LLM_MODES = ['mock', 'local', 'openai_compatible', 'cisco_foundation_sec', 'disabled'];

export function LlmSettingsPanel({ status }: { status: SettingsStatus['llm'] }) {
  const providers = status.providers ?? [];
  const roles = status.role_resolution ?? {};
  const governance = status.governance;
  const [verification, setVerification] = useState<LlmConnectionVerificationResult | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const runVerification = async (action: 'validate' | 'test' | 'models') => {
    setBusyAction(action);
    try {
      const result = await verifyLlmConnection(action);
      setVerification(result);
      toast[result.status === 'Connected' || result.status === 'Config valid, not tested' ? 'success' : 'warning'](result.failure_reason);
    } catch (err) {
      toast.error(`LLM ${action} failed: ${(err as Error).message}`);
    } finally {
      setBusyAction(null);
    }
  };
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
        {governance ? <LlmGovernanceSection governance={governance} /> : null}
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
              <Button type="button" variant="outline" size="sm" disabled={!!busyAction} onClick={() => runVerification('models')}>
                {busyAction === 'models' ? 'Listing...' : 'List models'}
              </Button>
            </div>
          </div>
          {verification ? <LlmVerificationResult result={verification} /> : null}
        </div>
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
      </CardContent>
    </Card>
  );
}

function LlmVerificationResult({ result }: { result: LlmConnectionVerificationResult }) {
  return (
    <div data-testid="llm-connection-result" className="mt-3 space-y-3 text-xs">
      <p className={result.status === 'Connected' ? 'text-emerald-200' : 'text-amber-100'}>{result.failure_reason}</p>
      <div className="grid gap-1 sm:grid-cols-2">
        <SettingRow label="Base URL configured" value={<BoolPill value={result.base_url_configured} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="API key configured" value={<BoolPill value={result.api_key_configured} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Default model configured" value={<BoolPill value={result.default_model_configured} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Reachable" value={result.reachable === null ? 'not tested' : <BoolPill value={result.reachable} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Authenticated" value={result.authenticated === null ? 'not tested' : <BoolPill value={result.authenticated} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Model available" value={typeof result.model_available === 'boolean' ? <BoolPill value={result.model_available} trueLabel="yes" falseLabel="no" /> : result.model_available} />
        <SettingRow label="Policy allowed" value={<BoolPill value={result.policy_allowed} trueLabel="yes" falseLabel="no" />} />
        <SettingRow label="Final synthesis" value={result.final_synthesis} mono />
        <SettingRow label="Answer Guard" value={result.answer_guard} mono />
        <SettingRow label="Provider" value={result.provider_type || 'unset'} mono />
        <SettingRow label="Model" value={result.model ?? 'unset'} mono />
      </div>
      {result.models.length ? (
        <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
          <p className="soc-eyebrow mb-2">Models</p>
          <div className="flex flex-wrap gap-1.5">
            {result.models.map((model) => (
              <Badge key={model} variant="outline" className="font-mono text-[0.65rem]">{model}</Badge>
            ))}
          </div>
        </div>
      ) : null}
      <details className="rounded border border-slate-800 bg-slate-950/60 px-2 py-1.5">
        <summary className="cursor-pointer text-slate-400">Technical details</summary>
        <p className="mt-2 break-words font-mono text-[0.65rem] text-slate-500">{result.technical_error_detail || 'none'}</p>
      </details>
    </div>
  );
}

function LlmGovernanceSection({ governance }: { governance: LlmGovernanceStatus }) {
  const [editing, setEditing] = useState(false);
  return (
    <div data-testid="llm-governance" className="space-y-3 rounded-md border border-cyan-500/25 bg-cyan-500/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="soc-eyebrow text-cyan-300">Governed LLM readiness</p>
        <div className="flex items-center gap-2">
          <ModeBadge mode={governance.llm_mode} />
          <Button type="button" variant="outline" size="sm" className="h-7 gap-1 text-xs" onClick={() => setEditing((v) => !v)}>
            <Pencil className="h-3 w-3" /> {editing ? 'Close editor' : 'Edit / validate'}
          </Button>
        </div>
      </div>
      {editing ? <LlmGovernanceEditor governance={governance} /> : null}
      <div className="flex flex-wrap gap-1.5">
        <Badge variant={governance.final_synthesis_enabled ? 'success' : 'secondary'}>
          final synthesis {governance.final_synthesis_enabled ? 'enabled' : 'disabled'}
        </Badge>
        <Badge variant={governance.answer_guard_enabled ? 'success' : 'secondary'}>
          answer guard {governance.answer_guard_enabled ? 'enabled' : 'disabled'}
        </Badge>
        <Badge variant={governance.context_sufficiency_required ? 'success' : 'warning'}>
          context sufficiency {governance.context_sufficiency_required ? 'required' : 'optional'}
        </Badge>
      </div>
      <div>
        <SettingRow label="Governed LLM" value={<BoolPill value={governance.llm_enabled} trueLabel="enabled" falseLabel="disabled" />} />
        <SettingRow label="Default provider" value={governance.default_provider ?? 'unset'} mono />
        <SettingRow label="Default model" value={governance.default_model ?? 'unset'} mono />
        <SettingRow label="Cloud allowed" value={<BoolPill value={governance.cloud_allowed} trueLabel="allowed" falseLabel="blocked" />} />
        <SettingRow label="Air-gap enforced" value={<BoolPill value={governance.airgap_enforced} trueLabel="enforced" falseLabel="off" />} />
        <SettingRow label="Max input tokens" value={governance.limits.max_input_tokens.toLocaleString()} mono />
        <SettingRow label="Max output tokens" value={governance.limits.max_output_tokens.toLocaleString()} mono />
      </div>
      {governance.warnings.length ? (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
          {governance.warnings.join(', ')}
        </div>
      ) : null}
      <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
        <p className="soc-eyebrow mb-2">Safety controls</p>
        <SettingRow label="Log prompts" value={<BoolPill value={governance.safety.log_prompts} />} />
        <SettingRow label="Log responses" value={<BoolPill value={governance.safety.log_responses} />} />
        <SettingRow label="Redact secrets" value={<BoolPill value={governance.safety.redact_secrets} />} />
        <SettingRow label="Require source refs" value={<BoolPill value={governance.safety.require_source_refs} />} />
        <SettingRow
          label="Allow insufficient-evidence answer"
          value={<BoolPill value={governance.safety.allow_insufficient_evidence_response} trueLabel="allowed" falseLabel="blocked" />}
        />
      </div>
      <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
        <p className="soc-eyebrow mb-2">Provider readiness</p>
        <div className="space-y-2">
          {governance.providers.map((provider) => (
            <div key={provider.provider_id} className="rounded border border-slate-800 px-2 py-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold text-slate-100">{provider.provider_id}</p>
                <Badge variant="outline" className="font-mono text-[0.65rem]">{provider.provider_type}</Badge>
              </div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                <BoolPill value={provider.base_url_configured} trueLabel="base URL set" falseLabel="no base URL" />
                <BoolPill value={provider.api_key_configured} trueLabel="API key set" falseLabel="no API key" />
                <BoolPill value={provider.default_model_configured} trueLabel="model set" falseLabel="no model" />
                <BoolPill value={provider.enabled} trueLabel="enabled" falseLabel="disabled" />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
        <p className="soc-eyebrow mb-2">Governed role mapping</p>
        {governance.role_mappings.map((role) => (
          <SettingRow
            key={role.role}
            label={role.role}
            value={
              <span className="flex items-center gap-2">
                <span className="font-mono">{role.provider ?? 'unset'}{role.model ? ` · ${role.model}` : ''}</span>
                <BoolPill value={role.enabled} trueLabel="set" falseLabel="unset" />
              </span>
            }
          />
        ))}
      </div>
      <p className="text-[0.65rem] text-slate-500">Endpoint URLs and API keys are never exposed by this surface.</p>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-3 border-b border-slate-800/60 py-1.5 text-xs last:border-b-0">
      <span className="text-slate-400">{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-cyan-500" />
    </label>
  );
}

interface ProviderDraftRow {
  provider_id: string;
  provider_type: string;
  base_url: string;
  api_key: string;
  model: string;
}

function LlmGovernanceEditor({ governance }: { governance: LlmGovernanceStatus }) {
  // Seed from non-secret status only. base_url/api_key/model are write-only and
  // start blank — existing secret values are never sent to the client.
  const [form, setForm] = useState({
    mode: governance.llm_mode,
    enabled: governance.llm_enabled,
    allow_cloud: governance.cloud_requested,
    airgap_enforced: governance.airgap_enforced,
    default_provider: governance.default_provider ?? '',
    default_model: governance.default_model ?? '',
    timeout_seconds: governance.limits.timeout_seconds,
    max_input_tokens: governance.limits.max_input_tokens,
    max_output_tokens: governance.limits.max_output_tokens,
    temperature: governance.limits.temperature,
    streaming: governance.limits.streaming,
    log_prompts: governance.safety.log_prompts,
    log_responses: governance.safety.log_responses,
    redact_secrets: governance.safety.redact_secrets,
    require_context_sufficiency: governance.context_sufficiency_required,
    require_source_refs: governance.safety.require_source_refs,
    allow_insufficient_evidence_response: governance.safety.allow_insufficient_evidence_response,
    final_synthesis_enabled: governance.final_synthesis_enabled,
    answer_guard_enabled: governance.answer_guard_enabled,
  });
  const [providers, setProviders] = useState<ProviderDraftRow[]>(
    governance.providers.map((p) => ({ provider_id: p.provider_id, provider_type: p.provider_type, base_url: '', api_key: '', model: '' })),
  );
  const [result, setResult] = useState<LlmSettingsDraftCheckResult | null>(null);
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));
  const setProvider = (i: number, key: keyof ProviderDraftRow, value: string) =>
    setProviders((rows) => rows.map((row, idx) => (idx === i ? { ...row, [key]: value } : row)));

  const validate = async () => {
    setBusy(true);
    try {
      const res = await checkLlmSettingsDraft({ ...form, providers });
      setResult(res);
      toast[res.validation_status === 'pass' ? 'success' : 'error'](
        res.validation_status === 'pass' ? 'Draft valid (not saved)' : 'Draft has validation errors',
      );
    } catch (err) {
      toast.error(`Validation failed: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 rounded-md border border-slate-700 bg-slate-950/60 p-3">
      <p className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[0.7rem] text-amber-100">
        Draft editor — validates only. Nothing is saved; apply real changes via environment variables. Existing secrets are never shown.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <Label className="text-xs">Mode</Label>
          <select
            value={form.mode}
            onChange={(e) => set('mode', e.target.value)}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-100"
          >
            {LLM_MODES.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
        <div>
          <Label className="text-xs">Default provider</Label>
          <Input className="mt-1 h-8 text-xs" value={form.default_provider} onChange={(e) => set('default_provider', e.target.value)} placeholder="e.g. local" />
        </div>
        <div>
          <Label className="text-xs">Default model</Label>
          <Input className="mt-1 h-8 text-xs" value={form.default_model} onChange={(e) => set('default_model', e.target.value)} placeholder="model name" />
        </div>
        <div>
          <Label className="text-xs">Temperature</Label>
          <Input className="mt-1 h-8 text-xs" type="number" step="0.1" value={form.temperature} onChange={(e) => set('temperature', Number(e.target.value))} />
        </div>
        <div>
          <Label className="text-xs">Max input tokens</Label>
          <Input className="mt-1 h-8 text-xs" type="number" value={form.max_input_tokens} onChange={(e) => set('max_input_tokens', Number(e.target.value))} />
        </div>
        <div>
          <Label className="text-xs">Max output tokens</Label>
          <Input className="mt-1 h-8 text-xs" type="number" value={form.max_output_tokens} onChange={(e) => set('max_output_tokens', Number(e.target.value))} />
        </div>
        <div>
          <Label className="text-xs">Timeout (s)</Label>
          <Input className="mt-1 h-8 text-xs" type="number" value={form.timeout_seconds} onChange={(e) => set('timeout_seconds', Number(e.target.value))} />
        </div>
      </div>
      <div className="rounded border border-slate-800 p-2">
        <p className="soc-eyebrow mb-1">Flags</p>
        <Toggle label="Governed LLM enabled" checked={form.enabled} onChange={(v) => set('enabled', v)} />
        <Toggle label="Allow cloud" checked={form.allow_cloud} onChange={(v) => set('allow_cloud', v)} />
        <Toggle label="Air-gap enforced" checked={form.airgap_enforced} onChange={(v) => set('airgap_enforced', v)} />
        <Toggle label="Streaming" checked={form.streaming} onChange={(v) => set('streaming', v)} />
        <Toggle label="Final synthesis (inert)" checked={form.final_synthesis_enabled} onChange={(v) => set('final_synthesis_enabled', v)} />
        <Toggle label="Answer guard (inert)" checked={form.answer_guard_enabled} onChange={(v) => set('answer_guard_enabled', v)} />
        <Toggle label="Require context sufficiency" checked={form.require_context_sufficiency} onChange={(v) => set('require_context_sufficiency', v)} />
        <Toggle label="Require source refs" checked={form.require_source_refs} onChange={(v) => set('require_source_refs', v)} />
        <Toggle label="Allow insufficient-evidence answer" checked={form.allow_insufficient_evidence_response} onChange={(v) => set('allow_insufficient_evidence_response', v)} />
        <Toggle label="Log prompts" checked={form.log_prompts} onChange={(v) => set('log_prompts', v)} />
        <Toggle label="Log responses" checked={form.log_responses} onChange={(v) => set('log_responses', v)} />
        <Toggle label="Redact secrets" checked={form.redact_secrets} onChange={(v) => set('redact_secrets', v)} />
      </div>
      <div className="rounded border border-slate-800 p-2">
        <p className="soc-eyebrow mb-1">Provider endpoints (write-only)</p>
        <div className="space-y-2">
          {providers.map((provider, i) => (
            <div key={provider.provider_id} className="rounded border border-slate-800 p-2">
              <p className="text-xs font-semibold text-slate-100">{provider.provider_id} <span className="font-mono text-[0.65rem] text-slate-500">{provider.provider_type}</span></p>
              <div className="mt-1 grid gap-1.5 sm:grid-cols-3">
                <Input className="h-8 text-xs" value={provider.base_url} onChange={(e) => setProvider(i, 'base_url', e.target.value)} placeholder="base URL" />
                <Input className="h-8 text-xs" type="password" value={provider.api_key} onChange={(e) => setProvider(i, 'api_key', e.target.value)} placeholder="API key (not stored)" />
                <Input className="h-8 text-xs" value={provider.model} onChange={(e) => setProvider(i, 'model', e.target.value)} placeholder="model" />
              </div>
            </div>
          ))}
        </div>
      </div>
      <Button type="button" size="sm" className="w-full" disabled={busy} onClick={validate}>
        {busy ? 'Validating…' : 'Validate draft (not saved)'}
      </Button>
      {result ? (
        <div data-testid="llm-draft-result" className="space-y-2 rounded border border-slate-800 bg-slate-900/60 p-2 text-xs">
          <div className="flex items-center gap-2">
            <Badge variant={result.validation_status === 'pass' ? 'success' : 'destructive'}>{result.validation_status}</Badge>
            <Badge variant="secondary">not persisted</Badge>
          </div>
          {result.validation_errors.length ? <p className="text-rose-300">errors: {result.validation_errors.join(', ')}</p> : null}
          {result.warnings.length ? <p className="text-amber-200">warnings: {result.warnings.join(', ')}</p> : null}
          <p className="text-slate-400">{result.safe_message}</p>
        </div>
      ) : null}
    </div>
  );
}
