import { Blocks } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, SettingRow } from './SettingRow';

export function EmbeddingsSettingsPanel({ status }: { status: SettingsStatus['embeddings'] }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Blocks className="h-4 w-4 text-cyan-400" /> Embeddings
          </CardTitle>
          <ModeBadge mode={status.mode} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {!status.enabled ? <PanelMockBanner /> : null}
        <div>
          <SettingRow label="Embeddings enabled" value={<BoolPill value={status.enabled} />} />
          <SettingRow label="Configured" value={<BoolPill value={status.configured} />} />
          <SettingRow label="Available" value={<BoolPill value={status.available} />} />
          <SettingRow label="Model" value={status.model} mono />
          <SettingRow label="Connector status" value={status.detail} mono />
        </div>
      </CardContent>
    </Card>
  );
}
