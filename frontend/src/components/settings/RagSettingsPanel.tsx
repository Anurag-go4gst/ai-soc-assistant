import { Database } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, SettingRow } from './SettingRow';

export function RagSettingsPanel({ status }: { status: SettingsStatus['rag'] }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Database className="h-4 w-4 text-cyan-400" /> RAG / Knowledge Vault
          </CardTitle>
          <ModeBadge mode={status.mode} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {!status.enabled ? <PanelMockBanner /> : null}
        <div>
          <SettingRow label="RAG enabled" value={<BoolPill value={status.enabled} />} />
          <SettingRow label="Configured" value={<BoolPill value={status.configured} />} />
          <SettingRow label="Available" value={<BoolPill value={status.available} />} />
          <SettingRow label="Connector status" value={status.status_detail} mono />
          <SettingRow label="Vault path" value={status.vault_path} mono />
          <SettingRow label="Approved documents" value={status.approved_documents} mono />
          <SettingRow label="Draft documents" value={status.draft_documents} mono />
          <SettingRow label="Vector store" value={status.vector_store} mono />
          <SettingRow label="BM25 / keyword index" value={status.keyword_index} mono />
          <SettingRow label="Knowledge graph" value={status.knowledge_graph} mono />
          <SettingRow label="Chunk size" value={status.chunk_size} mono />
          <SettingRow label="Chunk overlap" value={status.chunk_overlap} mono />
          <SettingRow label="Embedding model" value={status.embedding_model} mono />
          <SettingRow label="Last ingestion" value={status.last_ingestion_status} mono />
        </div>
        <Button type="button" variant="outline" size="sm" disabled className="w-full">
          Ingest sources (disabled in mock mode)
        </Button>
      </CardContent>
    </Card>
  );
}
