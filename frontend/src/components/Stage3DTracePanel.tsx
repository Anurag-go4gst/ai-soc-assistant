import { AlertTriangle, Boxes, CheckCircle2, FileSearch, Library, ListChecks, Route, SearchCode, TerminalSquare, Wrench } from 'lucide-react';
import type React from 'react';
import { Badge } from '@/components/ui/badge';
import { CopyButton } from '@/components/CopyButton';
import { cn } from '@/lib/utils';
import type { ExecutionEnvelope, HumanReviewEnvelope, PlaceholderResponse, SourceEvidenceEnvelope, SplValidationEnvelope, StructuredContextPackage, WorkflowPlan } from '@/types/api';

interface Stage3DTracePanelProps {
  trace: PlaceholderResponse;
}

export function Stage3DTracePanel({ trace }: Stage3DTracePanelProps) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-300">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">Stage 3D trace</Badge>
        <Badge>{trace.trace_id.slice(0, 8)}</Badge>
        {trace.demo_mode ? <Badge variant="outline">{trace.demo_badge ?? 'COE synthetic demo'}</Badge> : null}
        {trace.evidence_origin ? <Badge variant="secondary">{safeText(trace.evidence_origin)}</Badge> : null}
        <Badge variant={trace.execution?.status === 'executed' ? 'success' : trace.human_review?.required ? 'warning' : 'secondary'}>
          {trace.execution?.status ?? 'not evaluated'}
        </Badge>
      </div>
      {trace.trace_explanation?.length ? <ChipLine label="demo trace" values={trace.trace_explanation} variant="outline" /> : null}

      <TraceSection icon={<SearchCode className="h-3.5 w-3.5 text-cyan-300" />} title="Query Received">
        <p className="break-words text-slate-100">{safeText(trace.user_query ?? '') || 'No query text returned.'}</p>
      </TraceSection>

      <TraceSection icon={<Route className="h-3.5 w-3.5 text-cyan-300" />} title="Skill Routing">
        <div className="grid gap-2 sm:grid-cols-2">
          <KeyValue label="selected skill" value={trace.selected_skill} />
          <KeyValue label="confidence" value={formatNumber(trace.confidence)} />
          <KeyValue label="routing mode" value={trace.routing_mode} />
          <KeyValue label="comparison" value={typeof trace.disagreement === 'boolean' ? (trace.disagreement ? 'disagree' : 'agree') : trace.routing_trace?.comparison_status} badgeVariant={trace.disagreement ? 'warning' : 'success'} />
          <KeyValue label="deterministic result" value={trace.routing_trace?.deterministic_skill ?? trace.selected_skill} />
          <KeyValue label="LLM shadow result" value={trace.routing_trace?.llm_shadow_skill ?? 'not exposed in response'} />
        </div>
        {trace.tool_plan?.length ? <ChipLine label="tool plan" values={trace.tool_plan} /> : null}
        {trace.disagreement_reason ? <Badge variant="warning">{trace.disagreement_reason}</Badge> : null}
      </TraceSection>

      {trace.workflow_plan ? <WorkflowSection workflow={trace.workflow_plan} /> : null}
      {trace.candidate_spl?.capability_profile || trace.spl_validation?.capability_profile ? <SplunkCapabilitySection profile={(trace.spl_validation?.capability_profile ?? trace.candidate_spl?.capability_profile) as Record<string, unknown>} validation={trace.spl_validation ?? null} /> : null}
      {trace.candidate_spl || trace.spl_validation ? <SplSection candidate={trace.candidate_spl?.candidate_spl} validation={trace.spl_validation ?? null} /> : null}
      {trace.execution ? <McpSection execution={trace.execution} /> : null}
      {trace.execution ? <ExecutionSection execution={trace.execution} /> : null}
      {trace.source_evidence?.some((item) => item.source_type === 'rag') ? <GovernedKnowledgeSection evidence={trace.source_evidence.filter((item) => item.source_type === 'rag')} review={trace.human_review ?? null} /> : null}
      {trace.source_evidence?.length ? <SourceEvidenceSection evidence={trace.source_evidence} /> : null}
      {trace.structured_context ? <StructuredContextSection context={trace.structured_context} sufficiency={trace.context_sufficiency ?? null} /> : null}
    </div>
  );
}

function SplunkCapabilitySection({ profile, validation }: { profile: Record<string, unknown>; validation: SplValidationEnvelope | null }) {
  return (
    <TraceSection icon={<Wrench className="h-3.5 w-3.5 text-cyan-300" />} title="Splunk MCP Capability">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={profile.mcp_available ? 'success' : 'warning'}>Core MCP</Badge>
        <Badge variant={profile.saia_available ? 'success' : 'secondary'}>{profile.saia_available ? 'SAIA available' : 'SAIA unavailable'}</Badge>
        <Badge variant={profile.saia_usable ? 'success' : 'warning'}>{profile.saia_usable ? 'SAIA usable' : 'Fallback active'}</Badge>
        <Badge variant={validation?.approved ? 'success' : 'destructive'}>{validation?.approved ? 'Validation passed' : 'Validation failed'}</Badge>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <KeyValue label="environment" value={String(profile.environment_mode ?? 'unknown')} />
        <KeyValue label="discovery mode" value={String(profile.discovery_mode ?? 'unknown')} />
        <KeyValue label="SAIA mode" value={String(profile.saia_configured_mode ?? 'unknown')} />
        <KeyValue label="fallback required" value={String(profile.fallback_required ?? false)} badgeVariant={profile.fallback_required ? 'warning' : 'success'} />
      </div>
      {Array.isArray(profile.available_core_tools) ? <ChipLine label="core tools" values={profile.available_core_tools.map(String)} variant="outline" /> : null}
      {Array.isArray(profile.available_saia_tools) ? <ChipLine label="SAIA tools" values={profile.available_saia_tools.map(String)} variant={profile.available_saia_tools.length ? 'success' : 'secondary'} /> : null}
      {validation ? (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <KeyValue label="SPL generation" value={validation.selected_candidate_spl_provider ?? 'unknown'} />
          <KeyValue label="SPL explanation" value={validation.spl_explanation_provider ?? 'unknown'} />
          <KeyValue label="SPL optimization" value={validation.spl_optimization_provider ?? 'unknown'} />
          <KeyValue label="Splunk guidance" value={validation.spl_guidance_provider ?? 'unknown'} />
        </div>
      ) : null}
    </TraceSection>
  );
}

function GovernedKnowledgeSection({ evidence, review }: { evidence: SourceEvidenceEnvelope[]; review: HumanReviewEnvelope | null }) {
  const rows = evidence.flatMap((item) => item.preview_rows.map((row) => ({ evidence: item, row })));
  const warnings = evidence.flatMap((item) => item.warnings);
  return (
    <TraceSection icon={<Library className="h-3.5 w-3.5 text-cyan-300" />} title="Governed Knowledge / RAG">
      <div className="flex flex-wrap items-center gap-2">
        {evidence.map((item) => (
          <Badge key={item.evidence_id} variant={item.collection_status === 'collected' ? 'success' : item.collection_status === 'ambiguous' ? 'warning' : 'secondary'}>
            {safeText(item.collection_status)}
          </Badge>
        ))}
      </div>
      {warnings.length ? <ChipLine label="warnings" values={warnings} variant="warning" /> : null}
      {rows.length ? (
        <div className="mt-2 space-y-2">
          {rows.slice(0, 8).map(({ row }, index) => (
            <div key={`${String(row.entry_id)}-${index}`} className="rounded border border-slate-800 bg-slate-950 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{safeText(String(row.collection_id ?? 'collection'))}</Badge>
                <Badge variant="outline">{safeText(String(row.document_type ?? 'document'))}</Badge>
                <Badge variant="secondary">v{safeText(String(row.doc_version ?? 'n/a'))}</Badge>
                <Badge variant="secondary">{safeText(String(row.status ?? 'status'))}</Badge>
                <Badge variant="success">{safeText(String(row.approval_status ?? 'approval'))}</Badge>
                <Badge variant="secondary">{safeText(String(row.environment ?? 'env'))}</Badge>
                <Badge variant="outline">{safeText(String(row.retrieval_mode ?? 'deterministic'))}</Badge>
                {row.graph_expanded ? <Badge variant="warning">graph expanded</Badge> : null}
                {row.reranked ? <Badge variant="warning">reranked</Badge> : null}
                <Badge>{typeof row.confidence === 'number' ? row.confidence.toFixed(2) : safeText(String(row.confidence ?? ''))}</Badge>
              </div>
              <p className="mt-2 font-medium text-slate-100">{safeText(String(row.doc_title ?? 'Untitled document'))}</p>
              <p className="mt-1 text-cyan-100">{safeText(String(row.entry_title ?? 'Untitled entry'))}</p>
              <p className="mt-2 text-slate-300">{safeText(String(row.source_excerpt ?? ''), 420)}</p>
              {Array.isArray(row.allowed_use) ? <ChipLine label="allowed use" values={row.allowed_use.map(String)} variant="outline" /> : null}
              {Array.isArray(row.source_refs) ? <ChipLine label="source refs" values={row.source_refs.map(String)} variant="secondary" /> : null}
              {row.retrieval_stage_scores && typeof row.retrieval_stage_scores === 'object' ? <ChipLine label="stage scores" values={Object.entries(row.retrieval_stage_scores as Record<string, unknown>).map(([key, value]) => `${key}:${String(value)}`)} variant="outline" /> : null}
              {row.citation ? <KeyValue label="citation" value={String(row.citation)} /> : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-slate-400">No approved governed knowledge entries were collected for this query.</p>
      )}
      {review?.sop_reference ? (
        <div className="mt-2 rounded border border-amber-400/30 bg-amber-500/10 p-2">
          <Badge variant="warning">HIL SOP guidance</Badge>
          <p className="mt-2 text-amber-100">{safeText(review.sop_reference)}</p>
          {review.sop_action_hint ? <p className="mt-1 text-amber-50">{safeText(review.sop_action_hint)}</p> : null}
        </div>
      ) : null}
    </TraceSection>
  );
}

function WorkflowSection({ workflow }: { workflow: WorkflowPlan }) {
  return (
    <TraceSection icon={<ListChecks className="h-3.5 w-3.5 text-cyan-300" />} title="Workflow Plan">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{workflow.status}</Badge>
        <Badge variant={workflow.execution_enabled ? 'success' : 'warning'}>
          execution {workflow.execution_enabled ? 'enabled' : 'disabled'}
        </Badge>
      </div>
      <ol className="mt-2 space-y-2">
        {workflow.steps.map((step) => (
          <li key={`${step.order}-${step.name}`} className="rounded border border-slate-800 bg-slate-950 p-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-slate-500">{step.order}.</span>
              <span className="font-medium text-slate-100">{step.name}</span>
              <Badge variant="secondary">{step.status}</Badge>
            </div>
            {step.safety_gates.length ? <ChipLine label="safety gates" values={step.safety_gates} /> : null}
            {step.required_connectors.length ? <ChipLine label="connectors" values={step.required_connectors} /> : null}
          </li>
        ))}
      </ol>
      {workflow.safety_gates.length ? <ChipLine label="plan gates" values={workflow.safety_gates} /> : null}
      {workflow.required_sources?.length ? <ChipLine label="required sources" values={workflow.required_sources} /> : null}
      {workflow.missing_sources?.length ? <ChipLine label="missing sources" values={workflow.missing_sources} variant="warning" /> : null}
    </TraceSection>
  );
}

function SplSection({ candidate, validation }: { candidate?: string; validation: SplValidationEnvelope | null }) {
  const approved = validation?.approved === true;
  return (
    <TraceSection icon={<TerminalSquare className="h-3.5 w-3.5 text-cyan-300" />} title="SPL Validation">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={approved ? 'success' : 'destructive'}>{approved ? 'approved' : 'rejected'}</Badge>
        {validation?.policy_version ? <Badge variant="secondary">{validation.policy_version}</Badge> : null}
        {validation?.selected_candidate_spl_provider ? <Badge variant="outline">{safeText(validation.selected_candidate_spl_provider)}</Badge> : null}
        {validation?.fallback_required ? <Badge variant="warning">Fallback active</Badge> : null}
        {candidate ? <CopyButton value={candidate} label="copy SPL" className="ml-auto" /> : null}
      </div>
      {candidate ? (
        <CodeBlock label="candidate SPL" value={candidate} tone="cyan" />
      ) : null}
      {approved && validation?.normalized_spl ? (
        <CodeBlock label="normalized SPL" value={validation.normalized_spl} tone="emerald" />
      ) : null}
      {validation?.reject_reasons.length ? <ChipLine label="reject reasons" values={validation.reject_reasons} variant="destructive" /> : null}
      {validation?.warnings.length ? <ChipLine label="warnings" values={validation.warnings} variant="warning" /> : null}
      {validation?.candidate_provider_reason ? <p className="mt-2 text-slate-400">{safeText(validation.candidate_provider_reason)}</p> : null}
    </TraceSection>
  );
}

function McpSection({ execution }: { execution: ExecutionEnvelope }) {
  return (
    <TraceSection icon={<Wrench className="h-3.5 w-3.5 text-cyan-300" />} title="MCP Tool Discovery / Selection">
      <div className="grid gap-2 sm:grid-cols-2">
        <KeyValue label="selected server" value={execution.selected_mcp_server ?? 'none'} />
        <KeyValue label="selected tool" value={execution.selected_mcp_tool ?? 'none'} />
        <KeyValue label="intent" value={execution.execution_intent} />
        <KeyValue label="selection status" value={execution.tool_selection_status} badgeVariant={execution.tool_selection_status === 'selected' ? 'success' : 'warning'} />
      </div>
      <p className="mt-2 text-slate-400">{safeText(execution.tool_selection_reason)}</p>
      {execution.block_reason ? <Badge className="mt-2" variant="warning">{safeText(execution.block_reason)}</Badge> : null}
    </TraceSection>
  );
}

function ExecutionSection({ execution }: { execution: ExecutionEnvelope }) {
  const executed = execution.status === 'executed';
  return (
    <TraceSection icon={executed ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" /> : <AlertTriangle className="h-3.5 w-3.5 text-amber-300" />} title="Execution Gate">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={executed ? 'success' : execution.status === 'failed' ? 'destructive' : 'warning'}>{execution.status}</Badge>
        <Badge variant="secondary">{execution.duration_ms} ms</Badge>
        <Badge variant="secondary">{execution.result_count} rows</Badge>
      </div>
      {execution.block_reason ? <Badge className="mt-2" variant="warning">{safeText(execution.block_reason)}</Badge> : null}
      {executed && execution.executed_spl ? <CodeBlock label="executed normalized SPL" value={execution.executed_spl} tone="emerald" /> : null}
      {executed ? <PreviewRows rows={execution.results_preview} /> : null}
    </TraceSection>
  );
}

function SourceEvidenceSection({ evidence }: { evidence: SourceEvidenceEnvelope[] }) {
  return (
    <TraceSection icon={<FileSearch className="h-3.5 w-3.5 text-cyan-300" />} title="Source Evidence">
      <div className="space-y-2">
        {evidence.slice(0, 6).map((item) => (
          <div key={item.evidence_id} className="rounded border border-slate-800 bg-slate-950 p-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={item.collection_status === 'collected' ? 'success' : item.collection_status === 'failed' ? 'destructive' : 'warning'}>
                {safeText(item.collection_status)}
              </Badge>
              <Badge variant="secondary">{safeText(item.source_type)}</Badge>
              <Badge variant="secondary">{safeText(item.source_name)}</Badge>
              {item.tool_name ? <Badge variant="outline">{safeText(item.tool_name)}</Badge> : null}
              {item.provider_used ? <Badge variant="outline">{safeText(item.provider_used)}</Badge> : null}
              {item.tool_category ? <Badge variant="secondary">{safeText(item.tool_category)}</Badge> : null}
              <Badge variant="secondary">{item.result_count} rows</Badge>
            </div>
            {item.executed_spl ? <CodeBlock label="executed normalized SPL" value={item.executed_spl} tone="emerald" /> : null}
            {item.fields_returned.length ? <ChipLine label="fields" values={item.fields_returned} /> : null}
            {item.warnings.length ? <ChipLine label="warnings" values={item.warnings} variant="warning" /> : null}
            {item.sensitivity_flags.length ? <ChipLine label="sensitivity" values={item.sensitivity_flags} variant="destructive" /> : null}
            {item.preview_rows.length ? <PreviewRows rows={item.preview_rows} /> : null}
          </div>
        ))}
      </div>
    </TraceSection>
  );
}

function sufficiencyVariant(status: string): 'success' | 'warning' | 'destructive' {
  if (status === 'full_answer' || status === 'partial_answer' || status === 'knowledge_only_answer') return 'success';
  if (status === 'blocked_by_policy' || status === 'insufficient_evidence') return 'destructive';
  return 'warning';
}

function StructuredContextSection({ context, sufficiency }: { context: StructuredContextPackage; sufficiency: PlaceholderResponse['context_sufficiency'] }) {
  return (
    <TraceSection icon={<Boxes className="h-3.5 w-3.5 text-cyan-300" />} title="Structured Context">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={context.context_quality === 'blocked' || context.context_quality === 'insufficient' ? 'warning' : 'secondary'}>
          quality {safeText(context.context_quality)}
        </Badge>
        <Badge variant={context.synthesis_allowed ? 'success' : 'warning'}>synthesis {context.synthesis_allowed ? 'allowed' : 'disabled'}</Badge>
        {sufficiency ? <Badge variant={sufficiencyVariant(sufficiency.status)}>{safeText(sufficiency.status)}</Badge> : null}
        {sufficiency ? <Badge variant={sufficiency.synthesis_readiness ? 'success' : 'secondary'}>readiness {sufficiency.synthesis_readiness ? 'ready' : 'not ready'}</Badge> : null}
      </div>
      {context.structured_facts.length ? (
        <div className="mt-2 space-y-1">
          {context.structured_facts.slice(0, 8).map((fact) => (
            <div key={fact.fact_id} className="rounded border border-slate-800 bg-slate-950 px-2 py-1.5">
              <p className="text-slate-100">{safeText(fact.statement)}</p>
              <ChipLine label="source refs" values={fact.source_refs} variant="outline" />
              <Badge className="mt-1" variant="secondary">{safeText(fact.derivation)}</Badge>
            </div>
          ))}
        </div>
      ) : null}
      {context.missing_evidence.length ? <ChipLine label="missing evidence" values={context.missing_evidence} variant="warning" /> : null}
      {context.policy_context_refs.length ? <ChipLine label="policy refs" values={context.policy_context_refs} variant="outline" /> : null}
      {context.answer_constraints?.length ? <ChipLine label="answer constraints" values={context.answer_constraints} variant="warning" /> : null}
      {context.mitre_grounding_refs?.length ? <ChipLine label="MITRE grounding" values={context.mitre_grounding_refs} /> : null}
      {context.splunk_context_refs?.length ? <ChipLine label="Splunk context" values={context.splunk_context_refs} /> : null}
      {context.tool_policy_refs?.length ? <ChipLine label="tool policy" values={context.tool_policy_refs} /> : null}
      {sufficiency?.reasons.length ? <ChipLine label="sufficiency reasons" values={sufficiency.reasons} variant="warning" /> : null}
    </TraceSection>
  );
}

function PreviewRows({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) {
    return null;
  }
  return (
    <div className="mt-2 overflow-hidden rounded border border-slate-800">
      <div className="bg-slate-900 px-2 py-1 font-mono text-[0.65rem] uppercase text-slate-500">capped preview rows</div>
      <div className="max-h-44 overflow-auto bg-slate-950 p-2 font-mono text-[0.7rem] text-cyan-100">
        {JSON.stringify(rows.slice(0, 5), null, 2)}
      </div>
    </div>
  );
}

function TraceSection({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section className="mt-3 border-t border-slate-800 pt-3">
      <div className="mb-2 flex items-center gap-2 text-[0.7rem] font-semibold uppercase tracking-[0.08em] text-slate-400">
        {icon}
        {title}
      </div>
      {children}
    </section>
  );
}

function KeyValue({ label, value, badgeVariant }: { label: string; value?: string | number | null; badgeVariant?: 'default' | 'secondary' | 'destructive' | 'warning' | 'success' | 'outline' }) {
  const display = value === undefined || value === null || value === '' ? '—' : String(value);
  return (
    <div className="rounded border border-slate-800 bg-slate-950 px-2 py-1.5">
      <div className="font-mono text-[0.62rem] uppercase text-slate-500">{label}</div>
      <Badge className="mt-1 max-w-full break-all" variant={badgeVariant ?? 'secondary'}>{safeText(display)}</Badge>
    </div>
  );
}

function ChipLine({ label, values, variant = 'secondary' }: { label: string; values: string[]; variant?: 'default' | 'secondary' | 'destructive' | 'warning' | 'success' | 'outline' }) {
  if (!values.length) {
    return null;
  }
  return (
    <div className="mt-2">
      <span className="mr-2 font-mono text-[0.62rem] uppercase text-slate-500">{label}</span>
      <span className="inline-flex flex-wrap gap-1.5">
        {values.slice(0, 12).map((value) => (
          <Badge key={value} variant={variant}>{safeText(value)}</Badge>
        ))}
      </span>
    </div>
  );
}

function CodeBlock({ label, value, tone }: { label: string; value: string; tone: 'cyan' | 'emerald' }) {
  return (
    <div className="mt-2">
      <div className="mb-1 font-mono text-[0.62rem] uppercase text-slate-500">{label}</div>
      <code
        className={cn(
          'block max-h-36 overflow-auto rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[0.7rem]',
          tone === 'emerald' ? 'text-emerald-100' : 'text-cyan-100',
        )}
      >
        {safeText(value, 1200)}
      </code>
    </div>
  );
}

function formatNumber(value?: number | null) {
  return typeof value === 'number' ? value.toFixed(2) : undefined;
}

function safeText(value: string, max = 240) {
  return value
    .replace(/bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer [redacted]')
    .replace(/(password|passwd|secret|token|api[_-]?key|credential)=\S+/gi, '$1=[redacted]')
    .slice(0, max);
}
