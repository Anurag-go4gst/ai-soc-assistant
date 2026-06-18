import { useCallback, useEffect, useState } from 'react';
import { Plus, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { getAssetRegistry, saveAssetRegistry } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import type { AssetRegistryRecord } from '@/types/api';

const EMPTY_ASSET: AssetRegistryRecord = {
  ip: '',
  asset_name: '',
  asset_type: '',
  purdue_layer: '',
  criticality: '',
  substation_id: '',
  region: '',
  is_master_station: false,
  expected_firmware: '',
  notes: '',
};

export function AssetRegistryPanel() {
  const [assets, setAssets] = useState<AssetRegistryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getAssetRegistry();
      setAssets(response.assets);
      setUpdatedAt(response.updated_at ?? null);
    } catch (err) {
      toast.error(`Asset registry unavailable: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const updateAsset = (index: number, patch: Partial<AssetRegistryRecord>) => {
    setAssets((prev) => prev.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  };

  const onSave = async () => {
    setSaving(true);
    try {
      const response = await saveAssetRegistry(assets);
      setAssets(response.assets);
      setUpdatedAt(response.updated_at ?? null);
      toast.success(`Asset registry saved (${response.asset_count} asset${response.asset_count === 1 ? '' : 's'})`);
    } catch (err) {
      toast.error(`Asset registry save failed: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="space-y-1">
          <p className="soc-eyebrow text-cyan-400">Asset Registry</p>
          {updatedAt ? <p className="text-xs text-slate-500">Last saved {new Date(updatedAt).toLocaleString()}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => setAssets((prev) => [...prev, { ...EMPTY_ASSET }])}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add
          </Button>
          <Button type="button" size="sm" disabled={saving || loading} onClick={() => void onSave()}>
            <Save className="mr-1.5 h-3.5 w-3.5" />
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
      <p className="rounded-md border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs text-slate-400">
        Asset records are local COE knowledge for review-only enrichment and placeholder lists. They do not write Splunk lookups.
      </p>
      {loading ? (
        <Badge variant="secondary">Loading assets…</Badge>
      ) : (
        <div className="overflow-x-auto rounded-md border border-slate-800">
          <div className="grid min-w-[980px] grid-cols-[120px_160px_100px_80px_110px_130px_120px_90px_1fr_48px] gap-px bg-slate-800 text-xs">
            {['IP', 'Name', 'Type', 'Purdue', 'Criticality', 'Substation', 'Region', 'Master', 'Notes', ''].map((header) => (
              <div key={header} className="bg-slate-950 px-2 py-2 font-medium text-slate-300">
                {header}
              </div>
            ))}
            {assets.map((asset, index) => (
              <div key={`${asset.ip || 'new'}-${index}`} className="contents">
                <Input value={asset.ip} onChange={(event) => updateAsset(index, { ip: event.target.value })} className="h-9 rounded-none border-0 font-mono text-xs" />
                <Input value={asset.asset_name} onChange={(event) => updateAsset(index, { asset_name: event.target.value })} className="h-9 rounded-none border-0 text-xs" />
                <Input value={asset.asset_type ?? ''} onChange={(event) => updateAsset(index, { asset_type: event.target.value })} className="h-9 rounded-none border-0 text-xs" />
                <Input value={asset.purdue_layer ?? ''} onChange={(event) => updateAsset(index, { purdue_layer: event.target.value })} className="h-9 rounded-none border-0 text-xs" />
                <Input value={asset.criticality ?? ''} onChange={(event) => updateAsset(index, { criticality: event.target.value })} className="h-9 rounded-none border-0 text-xs" />
                <Input value={asset.substation_id ?? ''} onChange={(event) => updateAsset(index, { substation_id: event.target.value })} className="h-9 rounded-none border-0 text-xs" />
                <Input value={asset.region ?? ''} onChange={(event) => updateAsset(index, { region: event.target.value })} className="h-9 rounded-none border-0 text-xs" />
                <label className="flex h-9 items-center justify-center bg-slate-950">
                  <input
                    type="checkbox"
                    checked={Boolean(asset.is_master_station)}
                    onChange={(event) => updateAsset(index, { is_master_station: event.target.checked })}
                    className="h-4 w-4 accent-cyan-500"
                  />
                </label>
                <Input value={asset.notes ?? ''} onChange={(event) => updateAsset(index, { notes: event.target.value })} className="h-9 rounded-none border-0 text-xs" />
                <Button type="button" variant="ghost" size="icon" className="h-9 rounded-none bg-slate-950" onClick={() => setAssets((prev) => prev.filter((_, idx) => idx !== index))}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

