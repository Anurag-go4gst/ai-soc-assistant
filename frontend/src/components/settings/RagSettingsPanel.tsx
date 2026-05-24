import { Database } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SettingsStatus } from '@/types/api';
import { BoolPill, ModeBadge, PanelMockBanner, PlaceholderConnectorBanner, SettingRow } from './SettingRow';

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
        {status.implemented === false ? <PlaceholderConnectorBanner fallback={status.fallback} /> : null}
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
          <SettingRow label="Repository backend" value={status.repository_backend_type ?? status.soc_kb?.repository_backend_type ?? 'json'} mono />
          <SettingRow label="Retrieval mode" value={status.retrieval_mode ?? status.soc_kb?.retrieval_mode ?? status.mode} mono />
          <SettingRow label="Vector backend" value={status.vector_backend ?? status.soc_kb?.vector_backend ?? status.vector_store} mono />
          <SettingRow label="BM25 / keyword index" value={status.keyword_index} mono />
          <SettingRow label="Knowledge graph" value={status.knowledge_graph} mono />
          <SettingRow label="Chunk size" value={status.chunk_size} mono />
          <SettingRow label="Chunk overlap" value={status.chunk_overlap} mono />
          <SettingRow label="Embedding model" value={status.embedding_model} mono />
          <SettingRow label="Reranker model" value={status.reranker_model ?? status.soc_kb?.reranker_model ?? 'BAAI/bge-reranker-v2-m3'} mono />
          <SettingRow label="Embedding indexing" value={<BoolPill value={status.embedding_indexing_enabled ?? status.soc_kb?.embedding_indexing_enabled ?? false} />} />
          <SettingRow label="Reranker enabled" value={<BoolPill value={status.reranker_enabled ?? status.soc_kb?.reranker_enabled ?? false} />} />
          <SettingRow label="Graph expansion" value={<BoolPill value={status.graph_expansion_enabled ?? status.soc_kb?.graph_expansion_enabled ?? false} />} />
          <SettingRow label="Last ingestion" value={status.last_ingestion_status} mono />
          <SettingRow label="SOC KB retrieval" value={<BoolPill value={status.soc_kb_retrieval_enabled ?? false} />} />
          <SettingRow label="SOC KB environment" value={status.environment ?? status.soc_kb?.environment ?? 'coe'} mono />
          <SettingRow label="Collections configured" value={status.collections_configured_count ?? status.soc_kb?.collections_configured_count ?? 0} mono />
          <SettingRow label="Documents total" value={status.documents_total_count ?? status.soc_kb?.documents_total_count ?? 0} mono />
          <SettingRow label="Eligible approved current docs" value={status.eligible_current_approved_document_count ?? status.soc_kb?.eligible_current_approved_document_count ?? 0} mono />
          <SettingRow label="Draft docs" value={status.draft_count ?? status.soc_kb?.draft_count ?? 0} mono />
          <SettingRow label="Retired/rejected docs" value={status.retired_rejected_count ?? status.soc_kb?.retired_rejected_count ?? 0} mono />
          <SettingRow label="Superseded docs" value={status.superseded_count ?? status.soc_kb?.superseded_count ?? 0} mono />
          <SettingRow label="Validation warnings" value={status.validation_warning_count ?? status.soc_kb?.validation_warning_count ?? 0} mono />
          <SettingRow label="Import batches" value={status.import_batch_count ?? status.soc_kb?.import_batch_count ?? 0} mono />
          <SettingRow label="Direct RAG to LLM" value={<BoolPill value={status.direct_to_llm ?? false} />} />
          <SettingRow label="LLM source selection" value={<BoolPill value={status.llm_selection_enabled ?? false} />} />
          <SettingRow label="LLM ambiguity assist" value={<BoolPill value={status.llm_ambiguity_assist_enabled ?? false} />} />
          <SettingRow label="Hybrid placeholder" value={<BoolPill value={status.hybrid_placeholder_enabled ?? true} />} />
          <SettingRow label="Graph placeholder" value={<BoolPill value={status.graph_placeholder_enabled ?? true} />} />
        </div>
        <Button type="button" variant="outline" size="sm" disabled className="w-full">
          Ingest sources (disabled in mock mode)
        </Button>
      </CardContent>
    </Card>
  );
}
