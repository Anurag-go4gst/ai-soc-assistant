import { BookOpen, ClipboardCopy, DatabaseZap, Download, FileCheck2, GitBranch, Search, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  getKnowledgeCollections,
  getKnowledgeDocuments,
  getKnowledgeEntries,
  getKnowledgeImportPrompt,
  getKnowledgeMappingSummary,
  getDetectionCoverage,
  type DetectionCoverage,
  getAtlasCoverage,
  type AtlasCoverageGap,
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
  KnowledgeMappingSummary,
  SettingsStatus,
} from '@/types/api';
import { ARCHITECTURE_QUERY_FLOW_DOC_HREF } from '@/lib/architectureDoc';

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
  const [mappingSummary, setMappingSummary] = useState<KnowledgeMappingSummary | null>(null);
  const [detectionCoverage, setDetectionCoverage] = useState<DetectionCoverage | null>(null);
  const [atlasCoverage, setAtlasCoverage] = useState<AtlasCoverageGap | null>(null);
  const [ragStatus, setRagStatus] = useState<SettingsStatus['rag'] | null>(null);
  const [query, setQuery] = useState('failed login spike brute force');
  const [retrieval, setRetrieval] = useState<Record<string, unknown> | null>(null);
  const [promptText, setPromptText] = useState('');
  const [importText, setImportText] = useState('{"documents":[],"entries":[]}');
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [actionNote, setActionNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getKnowledgeCollections(),
      getKnowledgeDocuments(),
      getKnowledgeEntries(),
      getKnowledgeMappingSummary(),
      getSettingsStatus(),
      getDetectionCoverage(),
      getAtlasCoverage(),
    ])
      .then(([collectionPayload, documentPayload, entryPayload, summary, settings, coverage, atlas]) => {
        setCollections(collectionPayload.collections);
        setDocuments(documentPayload.documents);
        setEntries(entryPayload.entries);
        setMappingSummary(summary);
        setRagStatus(settings.rag);
        setDetectionCoverage(coverage);
        setAtlasCoverage(atlas);
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
  const githubSkillRows = mappingSummary?.row_counts.github_skill_rows ?? 12;
  const questionRows = mappingSummary?.row_counts.question_rows ?? 105;
  const useCaseRows = mappingSummary?.row_counts.use_case_rows ?? 49;
  const catalogUseCases = mappingSummary?.row_counts.catalog_use_cases ?? 46;
  const liveRouteSkills = mappingSummary?.live_route_skills ?? [];
  const allowedExecutionSkills = mappingSummary?.allowed_live_execution_skills ?? [];

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="soc-eyebrow text-cyan-400">Knowledge</p>
            <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
              <DatabaseZap className="h-4 w-4 text-cyan-400" />
              Governed SOC KB Operations
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Admin-managed JSON lifecycle for governed retrieval. Runtime uses only current approved documents. LLM-extracted content is draft-only until human publish.
            </p>
          </div>
          <Button variant="outline" size="sm" asChild className="shrink-0">
            <a href={ARCHITECTURE_QUERY_FLOW_DOC_HREF} target="_blank" rel="noopener noreferrer">
              <BookOpen className="h-3.5 w-3.5" />
              Query flow guide
            </a>
          </Button>
        </header>
        {error ? <Badge variant="destructive">{error}</Badge> : null}

        {mappingSummary ? (
          <Card className="soc-panel border-cyan-900/40">
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Mapping spine snapshot</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-slate-300">
              <p className="text-slate-400">
                Live counts from governed artifacts backing runtime routing and Knowledge exports. Generated{' '}
                {mappingSummary.generated_at ? new Date(mappingSummary.generated_at).toLocaleString() : 'from repo snapshot'}.
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{questionRows} questions</Badge>
                <Badge variant="outline">{useCaseRows} crosswalk use-case rows</Badge>
                <Badge variant="outline">{catalogUseCases} catalog use cases</Badge>
                <Badge variant="outline">{githubSkillRows} GitHub skill rows</Badge>
                <Badge variant="outline">{mappingSummary.questions_with_use_case_id} questions with curated use-case id</Badge>
              </div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <SummaryBlock
                  title="105 question routes (live_execution_skill)"
                  items={mappingSummary.question_skill_distribution}
                />
                <SummaryBlock title="Question mapping status" items={mappingSummary.question_mapping_status} />
                <SummaryBlock
                  title="Question runtime support"
                  items={mappingSummary.question_runtime_support_status}
                />
              </div>
              <div className="rounded border border-slate-800 bg-slate-950 p-3">
                <p className="font-medium text-slate-100">Live route skills (5)</p>
                <p className="mt-1 font-mono text-[0.7rem] text-cyan-200">{liveRouteSkills.join(' · ')}</p>
                <p className="mt-2 font-medium text-slate-100">Catalog execution skills (4)</p>
                <p className="mt-1 font-mono text-[0.7rem] text-cyan-200">{allowedExecutionSkills.join(' · ')}</p>
                <p className="mt-2 text-slate-500">
                  <code>guided_investigation</code> is rescue-only and is excluded from catalog execution skills.
                  <code>spl_generation</code> appears on catalog rows but not in the 105-question taxonomy distribution above.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {detectionCoverage ? (
          <Card className="soc-panel border-cyan-900/40">
            <CardHeader className="py-3">
              <CardTitle className="text-sm">MITRE detection coverage &amp; gaps</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-slate-300">
              <p className="text-slate-400">
                Governed MITRE techniques mapped to the use cases that detect them. Techniques with no covering
                use case are detection gaps. Deterministic, read-only ({detectionCoverage.mitre_metadata_role}).
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{detectionCoverage.technique_count} techniques</Badge>
                <Badge variant="outline">{detectionCoverage.covered_count} covered</Badge>
                <Badge variant={detectionCoverage.gap_count > 0 ? 'destructive' : 'outline'}>
                  {detectionCoverage.gap_count} gaps
                </Badge>
              </div>
              {detectionCoverage.gaps.length > 0 ? (
                <div className="rounded border border-amber-900/50 bg-amber-950/20 p-3">
                  <p className="font-medium text-amber-200">Detection gaps (no covering use case)</p>
                  <ul className="mt-2 space-y-1">
                    {detectionCoverage.gaps.map((gap) => (
                      <li key={gap.technique_id} className="font-mono text-[0.7rem] text-amber-100/90">
                        {gap.technique_id} · {gap.name} <span className="text-slate-500">({gap.tactic})</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-emerald-300">No detection gaps in the governed technique subset.</p>
              )}
            </CardContent>
          </Card>
        ) : null}

        {atlasCoverage ? (
          <Card className="soc-panel border-fuchsia-900/40">
            <CardHeader className="py-3">
              <CardTitle className="text-sm">MITRE ATLAS — AI/LLM threat coverage gap</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-slate-300">
              <p className="text-slate-400">
                ATLAS is the AI/ML threat taxonomy (AML.Txxxx), a separate matrix from enterprise ATT&CK.
                The SOC catalogue shares no IDs with it, so AI/LLM/MCP threats are uncovered today.
                Deterministic, read-only ({atlasCoverage.atlas_source_status}).
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{atlasCoverage.technique_count} AML techniques</Badge>
                <Badge variant="outline">{atlasCoverage.covered_count} covered</Badge>
                <Badge variant={atlasCoverage.gap_count > 0 ? 'destructive' : 'outline'}>
                  {atlasCoverage.gap_count} gaps
                </Badge>
              </div>
              {Object.keys(atlasCoverage.ai_only_tactics).length > 0 ? (
                <div className="rounded border border-fuchsia-900/50 bg-fuchsia-950/20 p-3">
                  <p className="font-medium text-fuchsia-200">AI-only tactics (no enterprise analogue)</p>
                  <ul className="mt-2 space-y-1">
                    {Object.entries(atlasCoverage.ai_only_tactics).map(([tactic, count]) => (
                      <li key={tactic} className="font-mono text-[0.7rem] text-fuchsia-100/90">
                        {tactic} <span className="text-slate-500">({count} techniques)</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {atlasCoverage.top_techniques_by_case_study_frequency.length > 0 ? (
                <div>
                  <p className="font-medium text-slate-200">Top AML techniques by real-world case-study frequency</p>
                  <ul className="mt-2 space-y-1">
                    {atlasCoverage.top_techniques_by_case_study_frequency.slice(0, 5).map((t) => (
                      <li key={t.technique_id} className="font-mono text-[0.7rem] text-slate-300">
                        {t.technique_id} <span className="text-slate-500">· score {t.score} · {t.tactics.join(', ')}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <p className="text-[0.7rem] text-slate-500">{atlasCoverage.limitation}</p>
            </CardContent>
          </Card>
        ) : null}

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
                description={`Canonical Phase 0 mapping spine: ${questionRows} questions, ${useCaseRows} use-case export rows, ${githubSkillRows} GitHub skill rows (enrichment/provenance only), runtime_support_status, validation_status, and MITRE metadata role.`}
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
                title={`Validation — GitHub Enrichment (${githubSkillRows})`}
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

function SummaryBlock({ title, items }: { title: string; items: Record<string, number> }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950 p-3">
      <p className="font-medium text-slate-100">{title}</p>
      <ul className="mt-2 space-y-1 font-mono text-[0.7rem] text-slate-400">
        {Object.entries(items).map(([key, value]) => (
          <li key={key}>
            {key}: {value}
          </li>
        ))}
      </ul>
    </div>
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
