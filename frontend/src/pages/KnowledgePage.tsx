import { ClipboardCopy, DatabaseZap, Download, FileCheck2, GitBranch, Search, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  getKnowledgeCollections,
  getKnowledgeDocuments,
  getKnowledgeEntries,
  getKnowledgeImportPrompt,
  getSettingsStatus,
  downloadKnowledgeExport,
  publishKnowledgeImport,
  saveKnowledgeDraft,
  testKnowledgeRetrieval,
  validateKnowledgeImport,
} from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import type { KnowledgeCollection, KnowledgeDocument, KnowledgeEntry, SettingsStatus } from '@/types/api';

export function KnowledgePage() {
  const [collections, setCollections] = useState<KnowledgeCollection[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [ragStatus, setRagStatus] = useState<SettingsStatus['rag'] | null>(null);
  const [query, setQuery] = useState('failed login spike brute force');
  const [retrieval, setRetrieval] = useState<Record<string, unknown> | null>(null);
  const [promptText, setPromptText] = useState('');
  const [importText, setImportText] = useState('{"documents":[],"entries":[]}');
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [actionNote, setActionNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getKnowledgeCollections(), getKnowledgeDocuments(), getKnowledgeEntries(), getSettingsStatus()])
      .then(([collectionPayload, documentPayload, entryPayload, settings]) => {
        setCollections(collectionPayload.collections);
        setDocuments(documentPayload.documents);
        setEntries(entryPayload.entries);
        setRagStatus(settings.rag);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const entriesByDoc = useMemo(() => {
    const grouped = new Map<string, number>();
    entries.forEach((entry) => grouped.set(entry.doc_id, (grouped.get(entry.doc_id) ?? 0) + 1));
    return grouped;
  }, [entries]);

  const validationValid = validation?.valid === true;

  const runRetrieval = async () => {
    setRetrieval(await testKnowledgeRetrieval(query));
  };

  const loadPrompt = async () => {
    const result = await getKnowledgeImportPrompt();
    setPromptText(String(result.prompt ?? ''));
  };

  const copyPrompt = async () => {
    if (!promptText) await loadPrompt();
    await navigator.clipboard?.writeText(promptText);
    setActionNote('Extraction prompt copied to clipboard.');
  };

  const importPayload = () => ({
    raw_json: importText,
    source_file_name: 'pasted_knowledge.json',
    generated_by: 'llm_extraction',
    checksum_sha256: 'llm-extraction-placeholder',
  });

  const runValidation = async () => {
    setActionNote(null);
    setValidation(await validateKnowledgeImport(importPayload()));
  };

  const saveDraft = async () => {
    try {
      const result = await saveKnowledgeDraft(importPayload());
      setActionNote(`Saved as draft only (does not affect runtime). batch ${String((result.import_batch as Record<string, unknown>)?.import_batch_id ?? '')}`);
    } catch (err) {
      setActionNote(`Save draft failed: ${(err as Error).message}`);
    }
  };

  const publish = async () => {
    try {
      const result = await publishKnowledgeImport({ ...importPayload(), approved_by: 'admin' });
      const published = (result.published_documents as unknown[]) ?? [];
      setActionNote(`Published ${published.length} document(s) as current approved.`);
      const refreshed = await getKnowledgeDocuments();
      setDocuments(refreshed.documents);
    } catch (err) {
      setActionNote(`Publish failed: ${(err as Error).message}`);
    }
  };

  const downloadExport = async (
    artifact: 'question_runtime_map' | 'use_case_catalog',
    fileFormat: 'json' | 'csv',
  ) => {
    try {
      const blob = await downloadKnowledgeExport(artifact, fileFormat);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${artifact === 'question_runtime_map' ? 'ai_soc_question_runtime_map_105' : 'ai_soc_use_case_catalog'}.${fileFormat}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setActionNote(`Downloaded ${artifact.replace(/_/g, ' ')} as ${fileFormat.toUpperCase()}.`);
    } catch (err) {
      setActionNote(`Download failed: ${(err as Error).message}`);
    }
  };

  const reranker = ragStatus?.reranker;
  const assist = ragStatus?.ambiguity_assist;

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header>
          <p className="soc-eyebrow text-cyan-400">Knowledge</p>
          <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
            <DatabaseZap className="h-4 w-4 text-cyan-400" />
            Governed SOC KB Operations
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Admin-managed JSON lifecycle for governed retrieval. Runtime uses only current approved documents. LLM-extracted content is draft-only until human publish.
          </p>
        </header>
        {error ? <Badge variant="destructive">{error}</Badge> : null}

        <Card className="soc-panel">
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Download className="h-4 w-4 text-cyan-400" /> Mapping Exports
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 lg:grid-cols-2">
            <ExportBlock
              title="105 question runtime map"
              description="Question, runtime operation, routing status, and governed MITRE metadata."
              onJson={() => downloadExport('question_runtime_map', 'json')}
              onCsv={() => downloadExport('question_runtime_map', 'csv')}
            />
            <ExportBlock
              title="Use-case catalog"
              description="Use-case routing patterns, source requirements, templates, and MITRE candidates."
              onJson={() => downloadExport('use_case_catalog', 'json')}
              onCsv={() => downloadExport('use_case_catalog', 'csv')}
            />
          </CardContent>
        </Card>

        <Card className="soc-panel">
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Sparkles className="h-4 w-4 text-cyan-400" /> RAG Connector Status
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 text-xs">
            <Badge variant={reranker?.enabled ? 'success' : 'secondary'}>reranker {reranker?.enabled ? 'on' : 'off'}</Badge>
            <Badge variant="outline">provider {reranker?.provider ?? 'n/a'}</Badge>
            <Badge variant={reranker?.available ? 'success' : 'secondary'}>reranker {reranker?.available ? 'available' : 'unavailable'}</Badge>
            <Badge variant={assist?.enabled ? 'success' : 'secondary'}>ambiguity assist {assist?.enabled ? 'on' : 'off'}</Badge>
            <Badge variant="outline">assist provider {assist?.provider ?? 'none'}</Badge>
            <Badge variant={assist?.available ? 'success' : 'secondary'}>assist {assist?.available ? 'available' : 'unavailable'}</Badge>
            <Badge variant={ragStatus?.direct_to_llm ? 'destructive' : 'success'}>direct_to_llm {String(ragStatus?.direct_to_llm ?? false)}</Badge>
            <Badge variant={ragStatus?.final_synthesis_enabled ? 'destructive' : 'success'}>final_synthesis {String(ragStatus?.final_synthesis_enabled ?? false)}</Badge>
          </CardContent>
        </Card>

        <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <Card className="soc-panel">
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Collections</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {collections.map((collection) => (
                <div key={collection.collection_id} className="rounded border border-slate-800 bg-slate-950 p-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={collection.enabled ? 'success' : 'secondary'}>{collection.collection_id}</Badge>
                    <Badge variant="outline">{collection.purpose}</Badge>
                    <Badge variant="secondary">{collection.environment}</Badge>
                    <Badge variant="secondary">priority {collection.priority}</Badge>
                  </div>
                  <p className="mt-2 font-medium text-slate-100">{collection.name}</p>
                  <p className="mt-1 text-slate-400">{collection.description}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="soc-panel">
            <CardHeader className="py-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Search className="h-4 w-4 text-cyan-400" /> Retrieval Test
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input value={query} onChange={(event) => setQuery(event.target.value)} />
              <Button type="button" size="sm" onClick={runRetrieval}>Run deterministic retrieval</Button>
              {retrieval ? (
                <pre className="max-h-72 overflow-auto rounded bg-slate-950 p-2 text-[0.7rem] text-slate-300">
                  {JSON.stringify(retrieval, null, 2)}
                </pre>
              ) : null}
            </CardContent>
          </Card>
        </div>

        <Card className="soc-panel">
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <FileCheck2 className="h-4 w-4 text-cyan-400" /> Documents
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 lg:grid-cols-2">
            {documents.map((doc) => (
              <div key={doc.doc_id} className="rounded border border-slate-800 bg-slate-950 p-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={doc.is_current_version ? 'success' : 'secondary'}>{doc.is_current_version ? 'current' : 'not current'}</Badge>
                  <Badge variant={doc.status === 'published' || doc.status === 'active' ? 'success' : doc.status === 'draft' ? 'warning' : 'secondary'}>{doc.status}</Badge>
                  <Badge variant={doc.approval_status?.includes('approved') || doc.approval_status?.includes('reviewed') ? 'success' : 'warning'}>{doc.approval_status}</Badge>
                  <Badge variant="outline">{doc.document_type}</Badge>
                  <Badge variant="secondary">v{doc.version}</Badge>
                  <Badge variant="secondary">{doc.environment}</Badge>
                </div>
                <p className="mt-2 font-medium text-slate-100">{doc.title}</p>
                <p className="mt-1 font-mono text-slate-500">{doc.doc_id}</p>
                <div className="mt-2 grid gap-1 sm:grid-cols-2">
                  <Meta label="collection" value={doc.collection_id} />
                  <Meta label="risk" value={doc.risk_level ?? 'n/a'} />
                  <Meta label="checksum" value={doc.checksum_sha256 ?? 'n/a'} />
                  <Meta label="entries" value={String(entriesByDoc.get(doc.doc_id) ?? 0)} />
                </div>
                {doc.superseded_by_doc_id ? <Badge className="mt-2" variant="warning">superseded by {doc.superseded_by_doc_id}</Badge> : null}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="soc-panel">
          <CardHeader className="py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <GitBranch className="h-4 w-4 text-cyan-400" /> LLM Import Assist
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="outline" onClick={loadPrompt}>Load LLM Extraction Prompt</Button>
              <Button type="button" size="sm" variant="outline" onClick={copyPrompt}>
                <ClipboardCopy className="mr-1 h-3 w-3" /> Copy Prompt
              </Button>
            </div>
            {promptText ? (
              <Textarea readOnly className="min-h-32 font-mono text-[0.7rem]" value={promptText} />
            ) : (
              <p className="text-xs text-slate-500">Step A: load/copy the prompt → run it with your source doc in an external LLM → paste the returned JSON below.</p>
            )}
            <p className="text-[0.7rem] uppercase text-slate-500">Extracted KB JSON (editable before publish)</p>
            <Textarea className="min-h-32 font-mono text-xs" value={importText} onChange={(event) => setImportText(event.target.value)} />
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" onClick={runValidation}>Validate JSON</Button>
              <Button type="button" size="sm" variant="outline" onClick={saveDraft} disabled={!validationValid}>Save Draft</Button>
              <Button type="button" size="sm" onClick={publish} disabled={!validationValid}>{validationValid ? 'Publish' : 'Publish (requires valid JSON)'}</Button>
            </div>
            {actionNote ? <Badge variant="outline">{actionNote}</Badge> : null}
            {validation ? (
              <pre className="max-h-72 overflow-auto rounded bg-slate-950 p-2 text-[0.7rem] text-slate-300">
                {JSON.stringify(validation, null, 2)}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </ScrollArea>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[0.65rem] uppercase text-slate-500">{label}</p>
      <p className="break-words font-mono text-slate-300">{value}</p>
    </div>
  );
}

function ExportBlock({
  title,
  description,
  onJson,
  onCsv,
}: {
  title: string;
  description: string;
  onJson: () => void;
  onCsv: () => void;
}) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950 p-3 text-xs">
      <p className="font-medium text-slate-100">{title}</p>
      <p className="mt-1 text-slate-400">{description}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" onClick={onCsv}>
          <Download className="mr-1 h-3 w-3" /> CSV
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onJson}>
          <Download className="mr-1 h-3 w-3" /> JSON
        </Button>
      </div>
    </div>
  );
}
