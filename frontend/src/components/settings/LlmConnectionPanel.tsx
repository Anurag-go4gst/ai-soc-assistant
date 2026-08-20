import { useEffect, useState } from 'react';
import { Plug, Save } from 'lucide-react';
import { toast } from 'sonner';
import { getLlmConnection, saveLlmConnection, verifyLlmConnection } from '@/api/client';
import type { LlmConnectionConfig, LlmConnectionPreset } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const HUMAN_ERROR: Record<string, string> = {
  invalid_mode: 'Mode is not supported.',
  timeout_seconds_must_be_positive: 'Timeout must be greater than 0.',
  base_url_required: 'Base URL is required when enabled.',
  base_url_should_end_with_v1: 'Base URL must end with /v1 (e.g. http://host:8000/v1).',
  model_required: 'Model id is required when enabled.',
  reasoning_base_url_should_end_with_v1: 'Reasoning base URL must end with /v1.',
  reasoning_model_required: 'Reasoning model id is required when a reasoning URL is set.',
};

/**
 * Editable LLM connection: persists to the backend override store and applies
 * live (no redeploy). The api key is write-only — never returned by the API.
 */
export function LlmConnectionPanel({ supportedModes }: { supportedModes: string[] }) {
  const [conn, setConn] = useState<LlmConnectionConfig | null>(null);
  const [modes, setModes] = useState<string[]>(supportedModes);
  const [presets, setPresets] = useState<LlmConnectionPreset[]>([]);
  const [presetId, setPresetId] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const load = () => {
    void getLlmConnection()
      .then((r) => {
        setConn(r.connection);
        setModes(r.supported_modes ?? supportedModes);
        setPresets(r.presets ?? []);
      })
      .catch(() => setConn(null));
  };

  useEffect(load, []);

  const patch = (p: Partial<LlmConnectionConfig>) => setConn((c) => (c ? { ...c, ...p } : c));

  // Presets only pre-fill the form — the operator still reviews, tests and saves.
  // Applying one always writes the reasoning fields (blank included) so switching
  // deployments cannot leave the previous site's reasoning endpoint in the chain.
  const applyPreset = (id: string) => {
    setPresetId(id);
    const preset = presets.find((p) => p.id === id);
    if (!preset) return;
    patch({
      mode: preset.mode,
      base_url: preset.base_url,
      model: preset.model,
      reasoning_base_url: preset.reasoning_base_url,
      reasoning_model: preset.reasoning_model,
      timeout_seconds: preset.timeout_seconds,
    });
  };

  const onSave = async () => {
    if (!conn || saving) return;
    setSaving(true);
    try {
      const result = await saveLlmConnection({
        enabled: conn.enabled,
        mode: conn.mode,
        base_url: conn.base_url,
        model: conn.model,
        api_key: apiKey,
        timeout_seconds: conn.timeout_seconds,
        reasoning_base_url: conn.reasoning_base_url ?? '',
        reasoning_model: conn.reasoning_model ?? '',
      });
      if (result.saved) {
        setConn(result.connection);
        setApiKey('');
        toast.success('LLM connection saved and applied.');
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

  const onTest = async () => {
    setTesting(true);
    try {
      const result = await verifyLlmConnection('test');
      toast[result.reachable ? 'success' : 'warning'](result.failure_reason);
    } catch (err) {
      toast.error(`Test failed: ${(err as Error).message}`);
    } finally {
      setTesting(false);
    }
  };

  if (!conn) {
    return null;
  }

  return (
    <Card className="soc-panel border-cyan-500/20">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Plug className="h-4 w-4 text-cyan-400" /> Connection
          </CardTitle>
          <Badge variant="secondary" className="text-[0.65rem]">
            source: {conn.source}
          </Badge>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Set the on-prem model endpoint here — saved values persist and apply live (no redeploy).
          Drives every governed role <em>and</em> the Ask LLM lab.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {presets.length > 0 ? (
          <div className="space-y-1 rounded border border-cyan-500/20 bg-slate-950/40 p-2">
            <Label className="text-xs">Deployment preset</Label>
            <select
              value={presetId}
              onChange={(e) => applyPreset(e.target.value)}
              className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40"
            >
              <option value="">Custom / current values</option>
              {presets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </select>
            <p className="text-[0.7rem] text-slate-500">
              {presets.find((preset) => preset.id === presetId)?.description ??
                'Fills the fields below only — review, then Save & apply.'}
            </p>
          </div>
        ) : null}

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
              <span className="text-xs text-slate-400">Turn the governed LLM layer on</span>
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Mode</Label>
            <select
              value={conn.mode}
              onChange={(e) => patch({ mode: e.target.value })}
              className="w-full rounded bg-slate-950/60 px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-cyan-500/40"
            >
              {modes.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Base URL (must end with /v1)</Label>
          <Input
            value={conn.base_url}
            onChange={(e) => patch({ base_url: e.target.value })}
            placeholder="http://host.docker.internal:8081/v1"
            className="text-sm"
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label className="text-xs">Model id</Label>
            <Input
              value={conn.model}
              onChange={(e) => patch({ model: e.target.value })}
              placeholder="foundation-sec-1.1-8b-instruct-q8_0"
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

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label className="text-xs">Reasoning base URL (optional)</Label>
            <Input
              value={conn.reasoning_base_url ?? ''}
              onChange={(e) => patch({ reasoning_base_url: e.target.value })}
              placeholder="blank = reasoning roles use the endpoint above"
              className="text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Reasoning model id</Label>
            <Input
              value={conn.reasoning_model ?? ''}
              onChange={(e) => patch({ reasoning_model: e.target.value })}
              placeholder="foundation-sec-reasoning"
              className="text-sm"
            />
          </div>
        </div>
        <p className="text-[0.7rem] text-slate-500">
          Used only by the reasoning roles (pattern, MITRE, missing-evidence, risk rationale).
          Leave both blank when the deployment serves one model — a reasoning URL that is not
          reachable costs a full timeout before failover on every such call.
        </p>

        <div className="space-y-1">
          <Label className="text-xs">API key {conn.api_key_configured ? '(configured — leave blank to keep)' : '(optional)'}</Label>
          <Input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={conn.api_key_configured ? '•••••• stored' : 'blank if the server has no auth'}
            className="text-sm"
          />
        </div>

        <div className="flex items-center gap-2 pt-1">
          <Button size="sm" disabled={saving} onClick={() => void onSave()} className="gap-1">
            <Save className="h-3.5 w-3.5" />
            {saving ? 'Saving…' : 'Save & apply'}
          </Button>
          <Button size="sm" variant="secondary" disabled={testing} onClick={() => void onTest()}>
            {testing ? 'Testing…' : 'Test connection'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
