import { AlertTriangle, CheckCircle2, ListChecks, Route, SearchCode, ShieldAlert, TerminalSquare, Wrench } from 'lucide-react';
import type React from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ExecutionEnvelope, HumanReviewEnvelope, PlaceholderResponse, SplValidationEnvelope, WorkflowPlan } from '@/types/api';

interface Stage3DTracePanelProps {
  trace: PlaceholderResponse;
}

export function Stage3DTracePanel({ trace }: Stage3DTracePanelProps) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-300">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">Stage 3D trace</Badge>
        <Badge>{trace.trace_id.slice(0, 8)}</Badge>
        <Badge variant={trace.execution?.status === 'executed' ? 'success' : trace.human_review?.required ? 'warning' : 'secondary'}>
          {trace.execution?.status ?? 'not evaluated'}
        </Badge>
      </div>

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
      {trace.candidate_spl || trace.spl_validation ? <SplSection candidate={trace.candidate_spl?.candidate_spl} validation={trace.spl_validation ?? null} /> : null}
      {trace.execution ? <McpSection execution={trace.execution} /> : null}
      {trace.human_review?.required ? <HumanReviewSection review={trace.human_review} /> : null}
      {trace.execution ? <ExecutionSection execution={trace.execution} /> : null}
    </div>
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
      </div>
      {candidate ? (
        <CodeBlock label="candidate SPL" value={candidate} tone="cyan" />
      ) : null}
      {approved && validation?.normalized_spl ? (
        <CodeBlock label="normalized SPL" value={validation.normalized_spl} tone="emerald" />
      ) : null}
      {validation?.reject_reasons.length ? <ChipLine label="reject reasons" values={validation.reject_reasons} variant="destructive" /> : null}
      {validation?.warnings.length ? <ChipLine label="warnings" values={validation.warnings} variant="warning" /> : null}
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

function HumanReviewSection({ review }: { review: HumanReviewEnvelope }) {
  return (
    <TraceSection icon={<ShieldAlert className="h-3.5 w-3.5 text-amber-300" />} title="Human Review">
      <div className="rounded-md border border-amber-400/30 bg-amber-500/10 p-3 text-amber-50">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="warning">{review.review_type}</Badge>
          <Badge variant="secondary">{review.reviewer_role}</Badge>
        </div>
        <p className="mt-2">{safeText(review.safe_message_for_user)}</p>
        <p className="mt-1 font-mono text-[0.7rem] text-amber-100">{safeText(review.reason)}</p>
        <ChipLine label="allowed actions" values={review.allowed_actions} variant="outline" />
        {review.sop_reference ? <KeyValue label="SOP reference" value={review.sop_reference} /> : null}
        {review.sop_excerpt ? <p className="mt-2 text-amber-100">{safeText(review.sop_excerpt)}</p> : null}
        {review.sop_action_hint ? <Badge className="mt-2" variant="warning">{safeText(review.sop_action_hint)}</Badge> : null}
      </div>
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
      <p className="mt-2 text-slate-400">Final LLM synthesis is not enabled yet.</p>
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
