import { Plug } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, SettingRow } from './SettingRow';

export function McpSettingsPanel({ status }: { status: SettingsStatus['mcp'] }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Plug className="h-4 w-4 text-cyan-400" /> MCP — Splunk
          </CardTitle>
          <ModeBadge mode={status.mode} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {!status.enabled ? <PanelMockBanner /> : null}
        <div>
          <SettingRow label="MCP enabled" value={<BoolPill value={status.enabled} />} />
          <SettingRow
            label="Base URL"
            value={<BoolPill value={status.base_url_configured} trueLabel="configured" falseLabel="not configured" />}
          />
          <SettingRow
            label="Token"
            value={<BoolPill value={status.token_configured} trueLabel="configured" falseLabel="not configured" />}
          />
          <SettingRow label="Query timeout" value={`${status.timeout_seconds}s`} mono />
          <SettingRow label="Max rows" value={status.max_rows.toLocaleString()} mono />
          <SettingRow label="Last check" value={status.last_check_status} mono />
        </div>
        <SettingList label="Allowed tools" items={status.allowed_tools} />
        <SettingList label="Allowed indexes" items={status.allowed_indexes} />
        <SettingList label="Allowed sourcetypes" items={status.allowed_sourcetypes} />
        <Button type="button" variant="outline" size="sm" disabled className="w-full">
          Test connection (disabled in mock mode)
        </Button>
      </CardContent>
    </Card>
  );
}

function SettingList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="space-y-1.5">
      <p className="soc-eyebrow">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <Badge key={item} variant="outline" className="font-mono text-[0.65rem]">
            {item}
          </Badge>
        ))}
      </div>
    </div>
  );
}
