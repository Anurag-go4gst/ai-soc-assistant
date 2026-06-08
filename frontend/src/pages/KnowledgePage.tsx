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
import type {
  KnowledgeCollection,
  KnowledgeDocument,
  KnowledgeEntry,
  KnowledgeExportArtifact,
  SettingsStatus,
} from '@/types/api';

const EXPORT_FILENAMES: Record<KnowledgeExportArtifact, string> = {
  question_runtime_map: 'ai_soc_question_runtime_map_105',
  use_case_catalog: 'ai_soc_use_case_catalog',
  soc_capability_crosswalk: 'ai_soc_soc_capability_crosswalk',
  skill_coverage_matrix: 'ai_soc_skill_coverage_matrix_105',
  github_skill_discovery_index: 'ai_soc_github_skill_discovery_index',
  github_skill_triage_scores: 'ai_soc_github_skill_triage_scores',
  github_skill_intake_register: 'ai_soc_github_skill_intake_register',
  proposed_use_cases_from_github: 'ai_soc_proposed_use_cases_from_github',
  skill_enrichment_status_matrix: 'ai_soc_skill_enrichment_status_matrix',
  rejected_github_skills: 'ai_soc_rejected_github_skills',
  pending_skill_enrichment_backlog: 'ai_soc_pending_skill_enrichment_backlog',
  soc_validation_use_cases: 'ai_soc_soc_validation_use_cases',
  soc_validation_spl_templates: 'ai_soc_soc_validation_spl_templates',
  soc_validation_mitre: 'ai_soc_soc_validation_mitre',
  soc_validation_questions: 'ai_soc_soc_validation_questions',
  soc_validation_github_enrichment: 'ai_soc_soc_validation_github_enrichment',
  soc_validation_github_batch_intake: 'ai_soc_soc_validation_github_batch_intake',
  soc_validation_rag_sop: 'ai_soc_soc_validation_rag_sop',
  soc_validation_pending_backlog: 'ai_soc_soc_validation_pending_backlog',
  soc_validation_combination_matrix: 'ai_soc_soc_validation_combination_matrix',
  soc_validation_demo_scenarios: 'ai_soc_soc_validation_demo_scenarios',
};

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

  const downloadExport = async (artifact: KnowledgeExportArtifact, fileFormat: 'json' | 'csv') => {
    try {
      const blob = await downloadKnowledgeExport(artifact, fileFormat);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${EXPORT_FILENAMES[artifact]}.${fileFormat}`;
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
          <CardContent className="space-y-4">
            <div className="rounded border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-100/90">
              <p className="font-medium text-amber-200">Export governance notes</p>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-slate-300">
                <li>
                  <span className="text-amber-200">mitre_permitted</span> and registry fields are metadata only — not
                  observed evidence.
                </li>
                <li>MITRE evidence status is a runtime decision from live /chat, not a static export claim.</li>
                <li>GitHub references are provenance only and are not runtime authority.</li>
                <li>GitHub SKILL.md files are not loaded into prompts or governed retrieval.</li>
                <li>
                  GitHub <span className="text-amber-200">accept</span> means accepted for curated enrichment
                  only — not runtime_active and not a live execution skill.
                </li>
                <li>Skill enrichment metadata does not automatically enable live routing or execution.</li>
              </ul>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <ExportBlock
                title="SOC Capability Crosswalk"
                description="Canonical Phase 0 mapping spine: 105 questions, 49 use-case export rows, 7 GitHub enrichments, runtime_support_status, validation_status, and MITRE metadata role."
                badge="recommended"
                onJson={() => downloadExport('soc_capability_crosswalk', 'json')}
                onCsv={() => downloadExport('soc_capability_crosswalk', 'csv')}
              />
              <ExportBlock
                title="105 Question Coverage Matrix"
                description="Legacy 105-question coverage view: live skill, planning skill, mapping status, SPL template status, GitHub references, enrichment status, and MITRE metadata."
                onJson={() => downloadExport('skill_coverage_matrix', 'json')}
                onCsv={() => downloadExport('skill_coverage_matrix', 'csv')}
              />
              <ExportBlock
                title="105 question runtime map (legacy base)"
                description="Stage 3L runtime operation map: question, routing status, and governed MITRE registry metadata. Use the coverage matrix for enrichment joins."
                onJson={() => downloadExport('question_runtime_map', 'json')}
                onCsv={() => downloadExport('question_runtime_map', 'csv')}
              />
              <ExportBlock
                title="Use-case catalog (with enrichment join)"
                description="Catalog rows joined with content_enrichment metadata: domain, GitHub refs, evidence, workflow, SPL status, and preserved mitre_registry."
                onJson={() => downloadExport('use_case_catalog', 'json')}
                onCsv={() => downloadExport('use_case_catalog', 'csv')}
              />
              <ExportBlock
                title="GitHub Skill Discovery Index"
                description="Phase 0B factory scan of local reference clone metadata (no raw SKILL.md bodies). Merges intake-register decisions."
                badge="factory"
                onJson={() => downloadExport('github_skill_discovery_index', 'json')}
                onCsv={() => downloadExport('github_skill_discovery_index', 'csv')}
              />
              <ExportBlock
                title="GitHub Skill Triage Scores"
                description="Advisory triage scores for discovered skills. Does not auto-accept skills or enable runtime activation."
                badge="factory"
                onJson={() => downloadExport('github_skill_triage_scores', 'json')}
                onCsv={() => downloadExport('github_skill_triage_scores', 'csv')}
              />
              <ExportBlock
                title="GitHub Skill Intake Register"
                description="Tracks accepted-for-enrichment, rejected, deferred, and pending external GitHub skills used as reference/provenance only."
                onJson={() => downloadExport('github_skill_intake_register', 'json')}
                onCsv={() => downloadExport('github_skill_intake_register', 'csv')}
              />
              <ExportBlock
                title="Proposed Use Cases from GitHub"
                description="Enrichment-only / proposed internal use cases derived from GitHub references. Never runtime_active until catalog promotion and SOC approval."
                onJson={() => downloadExport('proposed_use_cases_from_github', 'json')}
                onCsv={() => downloadExport('proposed_use_cases_from_github', 'csv')}
              />
              <ExportBlock
                title="Skill Enrichment Status Matrix"
                description="JSON-backed enrichment implementation status per internal use case (MITRE metadata, evidence, workflow, SPL, tests)."
                onJson={() => downloadExport('skill_enrichment_status_matrix', 'json')}
                onCsv={() => downloadExport('skill_enrichment_status_matrix', 'csv')}
              />
              <ExportBlock
                title="Rejected GitHub Skills"
                description="Documents skills or sections rejected for safety, offensive content, unsupported execution, or non-demo suitability."
                jsonOnly
                onJson={() => downloadExport('rejected_github_skills', 'json')}
              />
              <ExportBlock
                title="Pending Skill Enrichment Backlog"
                description="JSON-backed advisory backlog of discovered GitHub skills awaiting human review (bounded export)."
                onJson={() => downloadExport('pending_skill_enrichment_backlog', 'json')}
                onCsv={() => downloadExport('pending_skill_enrichment_backlog', 'csv')}
              />
            </div>
            <div className="rounded border border-cyan-900/40 bg-cyan-950/10 p-3 text-xs text-cyan-100/90">
              <p className="font-medium text-cyan-200">SOC validation package (Phase 10/11)</p>
              <p className="mt-1 text-slate-400">
                Crosswalk-derived review sheets for SOC/COE sign-off. Validation only — not runtime activation.
                Demo flags: docs/demo/flag_cutover_matrix.md
              </p>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <ExportBlock
                title="Validation — Use Cases (49)"
                description="runtime_support_status, validation_status, SPL/RAG/enrichment joins. review_decision blank for SOC."
                badge="recommended"
                onJson={() => downloadExport('soc_validation_use_cases', 'json')}
                onCsv={() => downloadExport('soc_validation_use_cases', 'csv')}
              />
              <ExportBlock
                title="Validation — 105 Questions"
                description="Question rows with crosswalk authority fields for coverage and routing review."
                onJson={() => downloadExport('soc_validation_questions', 'json')}
                onCsv={() => downloadExport('soc_validation_questions', 'csv')}
              />
              <ExportBlock
                title="Validation — SPL Templates"
                description="Review-only SPL template sheet. no_execution=true on every row."
                onJson={() => downloadExport('soc_validation_spl_templates', 'json')}
                onCsv={() => downloadExport('soc_validation_spl_templates', 'csv')}
              />
              <ExportBlock
                title="Validation — MITRE"
                description="MITRE metadata_not_evidence labels. SOC review notes blank."
                onJson={() => downloadExport('soc_validation_mitre', 'json')}
                onCsv={() => downloadExport('soc_validation_mitre', 'csv')}
              />
              <ExportBlock
                title="Validation — GitHub Enrichment (7)"
                description="GitHub skills as enrichment/provenance only — never runtime_active."
                onJson={() => downloadExport('soc_validation_github_enrichment', 'json')}
                onCsv={() => downloadExport('soc_validation_github_enrichment', 'csv')}
              />
              <ExportBlock
                title="Validation — RAG / SOP"
                description="RAG and SOP coverage status per use case for KB gap review."
                onJson={() => downloadExport('soc_validation_rag_sop', 'json')}
                onCsv={() => downloadExport('soc_validation_rag_sop', 'csv')}
              />
              <ExportBlock
                title="Validation — GitHub Batch Intake"
                description="Batch 1 factory intake summary. JSON only (nested row)."
                jsonOnly
                onJson={() => downloadExport('soc_validation_github_batch_intake', 'json')}
              />
              <ExportBlock
                title="Validation — Pending Backlog (Phase 10)"
                description="Crosswalk-derived backlog review sheet (distinct from legacy skills backlog export)."
                jsonOnly
                onJson={() => downloadExport('soc_validation_pending_backlog', 'json')}
              />
              <ExportBlock
                title="Validation — Combination Matrix A–H"
                description="Planner runtime behavior per crosswalk combination case."
                jsonOnly
                onJson={() => downloadExport('soc_validation_combination_matrix', 'json')}
              />
              <ExportBlock
                title="Validation — Demo Scenarios"
                description="Demo-safe flags per scenario. See docs/demo/demo_scenarios_readiness.md."
                jsonOnly
                onJson={() => downloadExport('soc_validation_demo_scenarios', 'json')}
              />
            </div>
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
  badge,
  jsonOnly = false,
  onJson,
  onCsv,
}: {
  title: string;
  description: string;
  badge?: 'recommended' | 'factory';
  jsonOnly?: boolean;
  onJson: () => void;
  onCsv?: () => void;
}) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium text-slate-100">{title}</p>
        {badge === 'recommended' ? (
          <Badge variant="success" className="text-[0.65rem]">
            recommended
          </Badge>
        ) : null}
        {badge === 'factory' ? (
          <Badge variant="secondary" className="text-[0.65rem]">
            factory
          </Badge>
        ) : null}
      </div>
      <p className="mt-1 text-slate-400">{description}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {!jsonOnly && onCsv ? (
          <Button type="button" size="sm" variant="outline" onClick={onCsv}>
            <Download className="mr-1 h-3 w-3" /> CSV
          </Button>
        ) : null}
        <Button type="button" size="sm" variant="outline" onClick={onJson}>
          <Download className="mr-1 h-3 w-3" /> JSON
        </Button>
      </div>
    </div>
  );
}
