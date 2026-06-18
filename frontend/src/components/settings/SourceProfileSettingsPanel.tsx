import { useCallback, useEffect, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { Database, RefreshCw, Save } from 'lucide-react';
import { toast } from 'sonner';
import {
  discoverSourceProfilesFromMcp,
  getSourceProfileSettings,
  saveSourceProfileSettings,
} from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { SourceProfileSettingsResponse } from '@/types/api';
import { AssetRegistryPanel } from './AssetRegistryPanel';
import { IocRegistryPanel } from './IocRegistryPanel';
import { SettingRow } from './SettingRow';

export function SourceProfileSettingsPanel() {
  const [data, setData] = useState<SourceProfileSettingsResponse | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [discovering, setDiscovering] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getSourceProfileSettings();
      setData(response);
      setDraft({ ...response.values });
    } catch (err) {
      toast.error(`Source profiles unavailable: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onSave = async () => {
    setSaving(true);
    try {
      const result = await saveSourceProfileSettings(draft);
      toast.success('Source profile map saved');
      setDraft({ ...result.values });
      await load();
    } catch (err) {
      toast.error(`Save failed: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const onDiscover = async () => {
    setDiscovering(true);
    try {
      const result = await discoverSourceProfilesFromMcp();
      toast.success(`MCP discovery mapped ${result.discovered_slots.length} slot(s)`);
      setDraft({ ...result.values });
      await load();
    } catch (err) {
      toast.error(`MCP discovery failed: ${(err as Error).message}`);
    } finally {
      setDiscovering(false);
    }
  };

  const slots = data?.slots ?? [];
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Database className="h-4 w-4 text-cyan-400" /> Environment Knowledge (COE)
          </CardTitle>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" disabled={discovering || loading} onClick={() => void onDiscover()}>
              <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${discovering ? 'animate-spin' : ''}`} />
              {discovering ? 'Discovering…' : 'Discover from MCP'}
            </Button>
            <Button type="button" size="sm" disabled={saving || loading} onClick={() => void onSave()}>
              <Save className="mr-1.5 h-3.5 w-3.5" />
              {saving ? 'Saving…' : 'Save map'}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="rounded-md border border-cyan-400/25 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-50">
          Enter your environment&apos;s Splunk index, sourcetype, zone, network, and asset knowledge. SPL placeholders like{' '}
          <code className="text-cyan-200">&lt;auth_index&gt;</code> resolve through this map at chat time.
          COE-entered values win over discovery; missing slots trigger analyst review (HIL).
        </p>
        {data ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3 text-xs">
            <SettingRow
              label="Orchestration order"
              value={data.orchestration_order.join(' → ')}
              mono
            />
            <SettingRow label="Conflict preference" value={data.conflict_preference} mono />
            {data.updated_at ? (
              <SettingRow
                label="Last saved"
                value={`${new Date(data.updated_at).toLocaleString()} (${data.updated_by ?? 'unknown'})`}
                mono
              />
            ) : null}
            {data.mcp_discovery_trace?.tools_called?.length ? (
              <SettingRow
                label="MCP preview"
                value={`${data.mcp_discovery_trace.tools_called.join(', ')} · ${(data.mcp_discovery_preview && Object.keys(data.mcp_discovery_preview).length) || 0} mapped slot(s)`}
                mono
              />
            ) : null}
          </div>
        ) : null}
        {loading ? (
          <Badge variant="secondary">Loading slot definitions…</Badge>
        ) : (
          <>
            <Tabs defaultValue="telemetry">
              <TabsList className="flex w-full justify-start overflow-x-auto">
                <TabsTrigger value="telemetry">Telemetry Routing</TabsTrigger>
                <TabsTrigger value="environment">Slots</TabsTrigger>
                <TabsTrigger value="assets">Asset Registry</TabsTrigger>
                <TabsTrigger value="ioc">IOC Registry</TabsTrigger>
              </TabsList>
              <TabsContent value="telemetry" className="mt-3 space-y-3">
                {(['index', 'sourcetype', 'cisco_index', 'cisco_sourcetype'] as const).map((category) => (
                  <SlotSection key={category} category={category} slots={slots.filter((s) => s.category === category)} draft={draft} setDraft={setDraft} data={data} />
                ))}
              </TabsContent>
              <TabsContent value="environment" className="mt-3 space-y-3">
                {(['zone', 'network', 'ot', 'compliance'] as const).map((category) => (
                  <SlotSection key={category} category={category} slots={slots.filter((s) => s.category === category)} draft={draft} setDraft={setDraft} data={data} />
                ))}
              </TabsContent>
              <TabsContent value="assets" className="mt-3">
                <AssetRegistryPanel />
              </TabsContent>
              <TabsContent value="ioc" className="mt-3">
                <IocRegistryPanel />
              </TabsContent>
            </Tabs>
          </>
        )}
      </CardContent>
    </Card>
  );
}

type SlotSectionProps = {
  category: string;
  slots: SourceProfileSettingsResponse['slots'];
  draft: Record<string, string>;
  setDraft: Dispatch<SetStateAction<Record<string, string>>>;
  data: SourceProfileSettingsResponse | null;
};

function SlotSection({ category, slots, draft, setDraft, data }: SlotSectionProps) {
  if (!slots.length) return null;
  const label = category.replace(/_/g, ' ');
  return (
    <div className="space-y-3">
      <p className="soc-eyebrow text-cyan-400">{label}</p>
      <div className="grid gap-3 md:grid-cols-2">
        {slots.map((slot) => (
          <div key={slot.slot_id} className="space-y-1.5 rounded-md border border-slate-800 bg-slate-950/40 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Label htmlFor={slot.slot_id} className="text-sm font-medium text-slate-100">
                {slot.label}
              </Label>
              <span className="font-mono text-[0.65rem] text-slate-500">&lt;{slot.slot_id}&gt;</span>
            </div>
            <p className="text-[0.7rem] text-slate-500">{slot.description}</p>
            <Input
              id={slot.slot_id}
              value={draft[slot.slot_id] ?? ''}
              placeholder={slot.example}
              className="font-mono text-xs"
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  [slot.slot_id]: event.target.value,
                }))
              }
            />
            {data?.field_sources?.[slot.slot_id] ? (
              <p className="text-[0.65rem] text-slate-500">
                Source: <span className="text-slate-300">{data.field_sources[slot.slot_id]}</span>
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
