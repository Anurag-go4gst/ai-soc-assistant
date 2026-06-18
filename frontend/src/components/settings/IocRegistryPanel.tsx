import { useCallback, useEffect, useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { getIocRegistrySettings } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import type { IocRegistrySettingsResponse } from '@/types/api';
import { SettingRow } from './SettingRow';

export function IocRegistryPanel() {
  const [data, setData] = useState<IocRegistrySettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getIocRegistrySettings();
      setData(response);
    } catch (err) {
      toast.error(`IOC registry unavailable: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <Badge variant="secondary">Loading IOC registry…</Badge>;
  }

  if (!data) {
    return <p className="text-xs text-slate-400">IOC registry settings could not be loaded.</p>;
  }

  return (
    <div className="space-y-4">
      <p className="rounded-md border border-amber-400/25 bg-amber-500/10 px-3 py-2 text-xs text-amber-50">
        <ShieldAlert className="mr-1 inline h-3.5 w-3.5" />
        Read-only hash preview from the local CERT-In / COE IOC bundle. Replace the JSON file at the import path below;
        enable <code className="text-amber-100">IOC_REGISTRY_ENABLED=true</code> in deployment env to activate lookups.
      </p>
      <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3 text-xs">
        <SettingRow label="Registry enabled" value={data.enabled ? 'true' : 'false'} mono />
        <SettingRow label="Import path" value={data.import_path_hint} mono />
        <SettingRow label="Resolved path" value={data.registry_path} mono />
        <SettingRow label="Advisory / source id" value={data.advisory_id ?? '—'} mono />
        <SettingRow label="Imported at" value={data.imported_at ? new Date(data.imported_at).toLocaleString() : '—'} mono />
        <SettingRow label="Staleness" value={data.staleness_status ?? 'unknown'} mono />
        <SettingRow label="Hash count" value={String(data.hash_count)} mono />
        <SettingRow label="Total IOC count" value={String(data.ioc_count)} mono />
        {data.validation_errors?.length ? (
          <SettingRow label="Validation" value={data.validation_errors.join('; ')} mono />
        ) : null}
      </div>
      {data.import_instructions ? (
        <p className="text-[0.7rem] text-slate-400">{data.import_instructions}</p>
      ) : null}
      <Card className="border-slate-800 bg-slate-950/40">
        <CardContent className="space-y-2 p-3">
          <p className="soc-eyebrow text-amber-300">Hash list (read-only)</p>
          {!data.hashes.length ? (
            <p className="text-xs text-slate-500">No hash IOCs loaded.</p>
          ) : (
            <div className="max-h-64 overflow-y-auto rounded border border-slate-800">
              <table className="w-full text-left text-[0.7rem]">
                <thead className="sticky top-0 bg-slate-900 text-slate-400">
                  <tr>
                    <th className="px-2 py-1">Type</th>
                    <th className="px-2 py-1">Hash</th>
                    <th className="px-2 py-1">TLP</th>
                  </tr>
                </thead>
                <tbody>
                  {data.hashes.map((row) => (
                    <tr key={`${row.hash_type}:${row.value}`} className="border-t border-slate-800">
                      <td className="px-2 py-1 font-mono text-slate-400">{row.hash_type}</td>
                      <td className="px-2 py-1 font-mono text-slate-200">{row.value}</td>
                      <td className="px-2 py-1 text-slate-400">{row.tlp}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
