import { Activity, ShieldCheck, Database, Gauge, ArrowRight, Cpu, FileSearch, ListChecks, Route, ShieldAlert } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { CopyButton } from '@/components/CopyButton';
import { cn } from '@/lib/utils';
import type { PlaceholderResponse } from '@/types/api';

type Variant = 'success' | 'warning' | 'destructive' | 'secondary';

const DOT: Record<Variant, string> = {
  success: 'bg-emerald-400',
  warning: 'bg-amber-400',
  destructive: 'bg-red-400',
  secondary: 'bg-slate-500',
};

const VALUE_TEXT: Record<Variant, string> = {
  success: 'text-emerald-100',
  warning: 'text-amber-100',
  destructive: 'text-red-100',
  secondary: 'text-slate-200',
};

// Human-readable labels for raw sufficiency / execution codes. Raw codes stay
// visible inside the technical trace; this surface is analyst-first.
const SUFFICIENCY_LABEL: Record<string, { label: string; variant: Variant }> = {
  full_answer: { label: 'Ready for synthesis', variant: 'success' },
  partial_answer: { label: 'Partial evidence', variant: 'warning' },
  knowledge_only_answer: { label: 'Knowledge answer', variant: 'success' },
  analyst_review_required: { label: 'Analyst review required', variant: 'warning' },
  spl_review_only: { label: 'SPL review only', variant: 'warning' },
  blocked_by_policy: { label: 'Blocked by policy', variant: 'destructive' },
  insufficient_evidence: { label: 'Insufficient evidence', variant: 'destructive' },
};

const EXECUTION_LABEL: Record<string, { label: string; variant: Variant }> = {
  executed: { label: 'Executed (mock)', variant: 'success' },
  blocked: { label: 'Execution blocked', variant: 'warning' },
  requires_human_review: { label: 'Awaiting review', variant: 'warning' },
  failed: { label: 'Execution failed', variant: 'destructive' },
  skipped: { label: 'Not required', variant: 'secondary' },
};

const BLOCK_REASON_LABEL: Record<string, string> = {
  mcp_global_execution_disabled: 'Execution disabled',
  mcp_server_execution_disabled: 'Execution disabled (server)',
  validated_spl_only_to_mcp: 'Needs validated SPL',
};

function sufficiency(status?: string): { label: string; variant: Variant } {
  if (!status) return { label: 'No assessment', variant: 'secondary' };
  return SUFFICIENCY_LABEL[status] ?? { label: status.replace(/_/g, ' '), variant: 'secondary' };
}

function executionState(trace: PlaceholderResponse): { label: string; variant: Variant } {
  const status = trace.execution?.status;
  const reason = trace.execution?.block_reason;
  if (reason && BLOCK_REASON_LABEL[reason]) return { label: BLOCK_REASON_LABEL[reason], variant: 'warning' };
  if (!status) return { label: 'Not required', variant: 'secondary' };
  return EXECUTION_LABEL[status] ?? { label: status.replace(/_/g, ' '), variant: 'secondary' };
}

function evidenceState(trace: PlaceholderResponse): { label: string; variant: Variant } {
  const evidence = trace.source_evidence ?? [];
  const collected = evidence.filter((e) => e.collection_status === 'collected').length;
  if (collected > 0) return { label: `${collected} source${collected > 1 ? 's' : ''} collected`, variant: 'success' };
  if (evidence.some((e) => e.collection_status === 'blocked')) return { label: 'Collection blocked', variant: 'warning' };
  if (evidence.some((e) => e.collection_status === 'ambiguous')) return { label: 'Ambiguous knowledge', variant: 'warning' };
  return { label: 'No evidence collected', variant: 'secondary' };
}

function splTemplateState(trace: PlaceholderResponse): { label: string; variant: Variant } {
  const status =
    trace.spl_template_status ??
    trace.spl_validation?.spl_template_status ??
    trace.candidate_spl?.spl_template_status ??
    'unavailable';
  if (status === 'active') return { label: 'Active template', variant: 'success' };
  if (status === 'planned') return { label: 'Template planned', variant: 'warning' };
  if (status === 'unavailable') return { label: 'Template unavailable', variant: 'secondary' };
  return { label: status.replace(/_/g, ' '), variant: 'secondary' };
}

function mitreState(trace: PlaceholderResponse): { label: string; variant: Variant } {
  const statuses = Object.values(trace.mitre_evidence_status ?? {});
  if (!statuses.length) return { label: 'No MITRE status', variant: 'secondary' };
  if (statuses.includes('evidence_supported')) return { label: 'Evidence supported', variant: 'success' };
  if (statuses.includes('requires_validation')) return { label: 'Requires validation', variant: 'warning' };
  if (statuses.includes('candidate')) return { label: 'Candidate', variant: 'warning' };
  if (statuses.includes('ruled_out')) return { label: 'Ruled out', variant: 'secondary' };
  if (statuses.includes('not_claimed')) return { label: 'Not claimed', variant: 'secondary' };
  return { label: statuses[0].replace(/_/g, ' '), variant: 'secondary' };
}

function hasDraftPreview(trace: PlaceholderResponse): boolean {
  return Boolean(
    trace.analyst_response?.spl_draft_preview || trace.analyst_response?.draft_spl_code,
  );
}

function reviewState(trace: PlaceholderResponse): { label: string; variant: Variant } {
  if (
    hasDraftPreview(trace) ||
    trace.analyst_response?.hil_status === 'required' ||
    trace.human_review?.required
  ) {
    return { label: 'Human review required', variant: 'warning' };
  }
  return { label: 'No approval to execute', variant: 'secondary' };
}

function draftPreviewSummary(trace: PlaceholderResponse): string | null {
  if (!hasDraftPreview(trace)) return null;
  return trace.analyst_response?.direct_answer_summary ?? trace.message ?? null;
}

function sessionState(trace: PlaceholderResponse): { label: string; variant: Variant } {
  const session = trace.session_context_status;
  if (!session) return { label: 'No session context', variant: 'secondary' };
  if (session.clarification_required) return { label: 'Needs clarification', variant: 'warning' };
  if (session.used_previous_context) return { label: `Context ${session.staleness ?? 'used'}`, variant: 'success' };
  return { label: `Context ${session.staleness ?? 'current'}`, variant: 'secondary' };
}

function nodeTraceState(trace: PlaceholderResponse): { label: string; variant: Variant } {
  const nodes = trace.node_trace ?? [];
  if (!nodes.length) return { label: 'No node trace', variant: 'secondary' };
  const reviewNodes = nodes.filter((node) => node.human_review_required === true).length;
  const failedNodes = nodes.filter((node) => String(node.status ?? '').toLowerCase().includes('fail')).length;
  if (failedNodes) return { label: `${failedNodes}/${nodes.length} failed`, variant: 'destructive' };
  if (reviewNodes) return { label: `${reviewNodes}/${nodes.length} need review`, variant: 'warning' };
  return { label: `${nodes.length} nodes traced`, variant: 'success' };
}

type ComposerTrace = {
  composer_is_enabled?: boolean;
  provider_configured?: boolean;
  provider_skip_reason?: string | null;
  llm_composer_used?: boolean;
  llm_guard_status?: string;
  llm_fallback_used?: boolean;
  composer_attempted?: boolean;
  composer_skipped_reason?: string | null;
};

function composerFootnote(trace: PlaceholderResponse): string {
  const composer = (trace.control_plane_trace?.llm_composer ?? null) as ComposerTrace | null;
  if (!composer) {
    return 'Final LLM synthesis and answer guard are not enabled yet.';
  }
  if (!composer.composer_is_enabled) {
    const flags = [
      trace.control_plane_trace ? 'control plane trace present' : null,
      composer.provider_skip_reason ? `provider: ${composer.provider_skip_reason}` : 'composer flags off',
    ].filter(Boolean);
    return `Phase 9 composer inactive (${flags.join('; ')}).`;
  }
  if (!composer.provider_configured) {
    return `Composer enabled but skipped: ${composer.provider_skip_reason ?? 'no_provider_configured'}.`;
  }
  if (composer.llm_composer_used) {
    return `Phase 9 composer narrated prose (guard: ${composer.llm_guard_status ?? 'unknown'}).`;
  }
  if (composer.composer_skipped_reason) {
    return `Composer skipped: ${composer.composer_skipped_reason}.`;
  }
  if (composer.llm_fallback_used) {
    return `Composer fell back to deterministic prose (guard: ${composer.llm_guard_status ?? 'unknown'}).`;
  }
  return `Composer ready; guard status: ${composer.llm_guard_status ?? 'pending'}.`;
}

function nextAction(trace: PlaceholderResponse): string {
  if (trace.human_review?.required) {
    if (trace.human_review.review_type === 'intent_clarification') return 'Provide the requested alert context, then resend.';
    return trace.human_review.safe_message_for_user || 'Route to the named reviewer before proceeding.';
  }
  const status = trace.context_sufficiency?.status;
  switch (status) {
    case 'full_answer':
      return 'Evidence is sufficient; synthesis stays gated until a later stage.';
    case 'partial_answer':
      return 'Collect the missing evidence to strengthen the answer.';
    case 'knowledge_only_answer':
      return 'Use the governed SOP/knowledge guidance below.';
    case 'spl_review_only':
      return 'Review the candidate SPL; it is advisory only and not executed.';
    case 'analyst_review_required':
      return 'An analyst must review before any conclusion is grounded.';
    case 'blocked_by_policy':
      return 'Resolve the policy block or escalate to a SOC lead.';
    case 'insufficient_evidence':
      return 'Provide more detail or enable a source so evidence can be collected.';
    default:
      return 'Review the technical trace for details.';
  }
}

function Stat({
  icon,
  label,
  value,
  variant,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  variant: Variant;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-slate-700/50 bg-slate-950/40 px-3 py-2.5">
      <span className="flex items-center gap-1 text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-slate-500">
        {icon}
        {label}
      </span>
      <div className="mt-1.5 flex items-start gap-1.5">
        <span className={cn('mt-1 h-2 w-2 shrink-0 rounded-full', DOT[variant])} />
        <span className={cn('break-words text-sm font-medium leading-tight', VALUE_TEXT[variant])}>{value}</span>
      </div>
    </div>
  );
}

export function AnalystSummaryCard({ trace }: { trace: PlaceholderResponse }) {
  const status = sufficiency(trace.context_sufficiency?.status);
  const exec = executionState(trace);
  const evidence = evidenceState(trace);
  const splTemplate = splTemplateState(trace);
  const mitre = mitreState(trace);
  const review = reviewState(trace);
  const session = sessionState(trace);
  const nodes = nodeTraceState(trace);
  const ready = trace.context_sufficiency?.synthesis_readiness ?? false;
  const reviewPending = trace.human_review?.required === true;
  const summaryParagraph = draftPreviewSummary(trace) ?? trace.analyst_summary;

  return (
    <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.04] p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-cyan-200">
            <ShieldCheck className="h-3.5 w-3.5" />
            Analyst summary
          </span>
          {trace.demo_mode ? <Badge variant="outline">{trace.demo_badge ?? 'COE synthetic demo'}</Badge> : null}
          {trace.no_live_customer_data ? <Badge variant="secondary">no live customer data</Badge> : null}
        </div>
        {trace.trace_id ? <CopyButton value={trace.trace_id} label={`trace ${trace.trace_id.slice(0, 8)}`} /> : null}
      </div>
      {summaryParagraph ? (
        <p className="mb-3 text-sm leading-6 text-slate-100">{summaryParagraph}</p>
      ) : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={<Activity className="h-3 w-3" />} label="Status" value={status.label} variant={status.variant} />
        <Stat icon={<Cpu className="h-3 w-3" />} label="Execution" value={exec.label} variant={exec.variant} />
        <Stat icon={<Database className="h-3 w-3" />} label="Evidence" value={evidence.label} variant={evidence.variant} />
        <Stat
          icon={<Gauge className="h-3 w-3" />}
          label="Readiness"
          value={ready ? 'Synthesis-ready' : 'Not ready'}
          variant={ready ? 'success' : 'secondary'}
        />
      </div>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat icon={<FileSearch className="h-3 w-3" />} label="SPL Template" value={splTemplate.label} variant={splTemplate.variant} />
        <Stat icon={<ShieldAlert className="h-3 w-3" />} label="MITRE" value={mitre.label} variant={mitre.variant} />
        <Stat icon={<ListChecks className="h-3 w-3" />} label="HIL" value={review.label} variant={review.variant} />
        <Stat icon={<Database className="h-3 w-3" />} label="Session" value={session.label} variant={session.variant} />
        <Stat icon={<Route className="h-3 w-3" />} label="Node Trace" value={nodes.label} variant={nodes.variant} />
      </div>
      {reviewPending ? (
        <p className="mt-3 text-xs text-slate-400">Action needed — see the review notice below.</p>
      ) : (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-slate-700/60 bg-slate-950/40 px-3 py-2 text-xs text-slate-200">
          <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-400" />
          <span>
            <span className="font-semibold text-slate-100">Next: </span>
            {nextAction(trace)}
          </span>
        </div>
      )}
      {trace.demo_mode && trace.source_evidence?.length ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {trace.source_evidence.slice(0, 4).map((item) => (
            <div key={item.evidence_id} className="rounded-lg border border-slate-700/60 bg-slate-950/40 px-3 py-2 text-xs">
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge variant={item.collection_status === 'collected' ? 'success' : 'warning'}>{item.collection_status}</Badge>
                <Badge variant="secondary">{item.source_type}</Badge>
              </div>
              <p className="mt-1 font-medium text-slate-100">{item.source_name}</p>
              <p className="mt-1 text-slate-500">{item.result_count} synthetic preview row{item.result_count === 1 ? '' : 's'}</p>
            </div>
          ))}
        </div>
      ) : null}
      <p className="mt-2 text-[0.65rem] text-slate-500">{composerFootnote(trace)}</p>
    </div>
  );
}
