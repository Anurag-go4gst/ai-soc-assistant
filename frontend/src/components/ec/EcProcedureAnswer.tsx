import { useState } from 'react';
import { ArrowUpRight, ChevronRight, FileText } from 'lucide-react';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcRagTrace } from '@/components/ec/EcRagTrace';
import { EcActionRecordToggle } from '@/components/ec/EcResponseRecords';
import type {
  EcProcedureAnswer as EcProcedureAnswerPayload,
  EcProcedureStep,
  EcRagTrace as EcRagTracePayload,
} from '@/components/ec/types';
import { cn } from '@/lib/utils';

function RefChips({
  step,
  openRef,
  onToggle,
}: {
  step: EcProcedureStep;
  openRef: string | null;
  onToggle: (key: string) => void;
}) {
  return (
    <span className="flex shrink-0 flex-wrap gap-1">
      {step.refs.map((ref) => {
        const key = `${step.text}|${ref.ref}`;
        return (
          <button
            key={key}
            type="button"
            aria-expanded={openRef === key}
            title={`${ref.doc_id} ${ref.section}`}
            onClick={() => onToggle(key)}
            className={cn(
              'rounded border px-1.5 py-0 font-mono text-[11px]',
              openRef === key
                ? 'border-violet-300 bg-violet-500/30 text-violet-50'
                : 'border-violet-400/40 text-violet-200 hover:bg-violet-500/20',
            )}
            data-ec-ref={ref.ref}
          >
            {ref.ref}
          </button>
        );
      })}
    </span>
  );
}

const STATUS_CLASS: Record<NonNullable<EcProcedureStep['status']>, string> = {
  done: 'border-emerald-500/40 text-emerald-100',
  requested: 'border-cyan-500/40 text-cyan-100',
  pending: 'border-amber-500/40 text-amber-100',
  conditional: 'border-slate-600 text-slate-300',
  not_done: 'border-rose-500/40 text-rose-100',
};

function StepStatus({ step }: { step: EcProcedureStep }) {
  if (!step.status) return null;
  return (
    <span
      className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[11px]', STATUS_CLASS[step.status])}
      data-ec-step-status={step.status}
    >
      {step.status_label}
    </span>
  );
}

export interface EcProcedureOutcome {
  title?: string;
  in_progress?: string[];
  deferred?: string[];
  risk_note?: string;
}

function ProgressSummary({
  summary,
  outcome,
}: {
  summary: NonNullable<EcProcedureAnswerPayload['progress_summary']>;
  outcome?: EcProcedureOutcome | null;
}) {
  const rows: Array<[string, string[]]> = [
    ['Done', summary.done],
    ['Requested', summary.requested],
    ['Pending', summary.pending],
  ];
  return (
    <div className="space-y-1.5 rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm" data-ec-section="procedure-summary">
      {outcome?.title ? <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{outcome.title}</p> : null}
      {rows
        .filter(([, items]) => items.length)
        .map(([label, items]) => (
          <p key={label} className="text-slate-200">
            <span className="font-medium text-slate-50">{label}:</span> {items.join(' · ')}
          </p>
        ))}
      {outcome?.in_progress?.length ? (
        <p className="text-amber-100">Waiting on: {outcome.in_progress.join(' · ')}</p>
      ) : null}
      {outcome?.risk_note ? <p className="text-slate-300">Next: {outcome.risk_note}</p> : null}
    </div>
  );
}

function OpenExcerpt({ step, openRef }: { step: EcProcedureStep; openRef: string | null }) {
  const ref = step.refs.find((item) => `${step.text}|${item.ref}` === openRef);
  if (!ref) return null;
  return (
    <p className="mt-1 border-l-2 border-violet-400/40 pl-2 text-xs text-slate-300" data-ec-excerpt={ref.ref}>
      “{ref.excerpt}” <span className="text-slate-500">— {ref.doc_id} {ref.section}</span>
    </p>
  );
}

/**
 * A knowledge-base procedure answer, kept to one screen: a short opening, the source document and its
 * approval date, the procedure's steps (one line each, with the section each comes from), and the
 * escalation rule. How the passages were retrieved is available, collapsed.
 */
export function EcProcedureAnswer({
  answer,
  trace,
  outcome,
}: {
  answer: EcProcedureAnswerPayload;
  trace?: EcRagTracePayload | null;
  /** The response's closing state, once the approved actions have run. */
  outcome?: EcProcedureOutcome | null;
}) {
  const [openRef, setOpenRef] = useState<string | null>(null);
  const toggle = (key: string) => setOpenRef((current) => (current === key ? null : key));
  const [primary, ...related] = answer.documents;
  // Steps are numbered straight through the phases, as the procedure reads.
  const firstNumber: number[] = [];
  answer.phases.reduce((next, phase) => {
    firstNumber.push(next);
    return next + phase.steps.length;
  }, 1);

  return (
    <section className="space-y-4 rounded-lg border border-slate-800/70 bg-slate-900/35 p-4" data-ec-section="procedure-answer">
      <div className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p className="text-base font-semibold text-slate-50">{answer.title}</p>
          {answer.assessment ? (
            <span className="flex gap-1.5 text-xs" data-ec-section="assessment">
              <span
                className="rounded border border-amber-500/40 bg-amber-950/20 px-2 py-0.5 font-semibold text-amber-100"
                title={`${answer.assessment.priority_rule}: ${answer.assessment.priority_basis}`}
              >
                {answer.assessment.incident_priority}
              </span>
              <span className="rounded border border-slate-700 px-2 py-0.5 text-slate-200">
                {answer.assessment.threat_assessment}
              </span>
            </span>
          ) : null}
        </div>
        <p
          className="rounded-md border-l-2 border-cyan-400 bg-cyan-950/30 px-3 py-2 text-sm font-medium leading-relaxed text-cyan-50"
          data-ec-section="procedure-key-message"
        >
          {answer.opening}
        </p>
        {primary ? (
          <div className="space-y-0.5 text-xs text-slate-400" data-ec-section="procedure-source">
            <p className="flex gap-1.5">
              <FileText className="mt-px h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
              <span>
                <span className="font-medium text-slate-200">{primary.doc_id}</span>
                {` · ${primary.title} · v${primary.version} · approved ${primary.approved_on}`}
              </span>
            </p>
            {related.length ? (
              <p className="pl-5">
                Also used:{' '}
                {related.map((doc) => `${doc.title} v${doc.version} (${doc.approved_on})`).join(' · ')}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="space-y-3">
        <EcSectionHeading>What the procedure says</EcSectionHeading>
        {answer.phases.map((phase, phaseIndex) => (
          <div key={phase.name} className="space-y-1.5">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{phase.name}</p>
            <ol className="space-y-1.5">
              {phase.steps.map((step, stepIndex) => {
                const number = firstNumber[phaseIndex] + stepIndex;
                return (
                  <li key={step.text} className="text-sm text-slate-100" data-ec-procedure-step={number}>
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                      <span className="w-4 shrink-0 text-right text-xs text-slate-500">{number}</span>
                      <span className="min-w-0 flex-1">
                        {step.text}
                        {step.condition ? <span className="text-slate-400"> — {step.condition}</span> : null}
                      </span>
                      <span className="shrink-0 text-xs text-slate-400">{step.owner}</span>
                      <RefChips step={step} openRef={openRef} onToggle={toggle} />
                      <StepStatus step={step} />
                    </div>
                    <div className="pl-6">
                      <OpenExcerpt step={step} openRef={openRef} />
                      {step.ticket || step.email ? (
                        <EcActionRecordToggle ticket={step.ticket} email={step.email} delivery={step.email_delivery} />
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        ))}
        <div
          className="rounded-md border border-amber-500/25 bg-amber-950/10 px-3 py-2 text-sm text-amber-50"
          data-ec-section="procedure-escalation"
        >
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <ArrowUpRight className="h-3.5 w-3.5 shrink-0 self-center text-amber-300" aria-hidden="true" />
            <span className="min-w-0 flex-1">{answer.escalation.text}</span>
            <RefChips step={answer.escalation} openRef={openRef} onToggle={toggle} />
          </div>
          <OpenExcerpt step={answer.escalation} openRef={openRef} />
        </div>
        {answer.progress_summary ? <ProgressSummary summary={answer.progress_summary} outcome={outcome} /> : null}
      </div>

      {trace ? (
        <details className="group rounded-md border border-slate-800 bg-slate-950/30" data-ec-section="procedure-retrieval">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-xs text-slate-400">
            <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" aria-hidden="true" />
            How this was found — {answer.retrieval_summary}
          </summary>
          <div className="p-3 pt-0">
            <EcRagTrace trace={trace} showAnswer={false} />
          </div>
        </details>
      ) : null}
    </section>
  );
}
