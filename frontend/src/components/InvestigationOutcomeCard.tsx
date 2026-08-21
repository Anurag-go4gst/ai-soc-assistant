import { useState, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, CircleSlash2, SearchCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type {
  InvestigationOutcomeEnvelope,
  InvestigationProgressEvent,
  InvestigationRunStatus,
} from '@/types/api';

interface InvestigationOutcomeCardProps {
  outcome: InvestigationOutcomeEnvelope;
  progress?: InvestigationProgressEvent[] | null;
  runStatus?: InvestigationRunStatus | null;
}

export function InvestigationOutcomeCard({ outcome, progress = [], runStatus }: InvestigationOutcomeCardProps) {
  const [remediationChoice, setRemediationChoice] = useState<'yes' | 'not_now' | null>(null);
  if (!outcome.investigation_status) return null;

  const progressItems = asArray<InvestigationProgressEvent>(progress);
  const findings = asArray<string>(outcome.findings);
  const supportedHypotheses = asArray<string>(outcome.supported_hypotheses);
  const unconfirmedHypotheses = asArray<string>(outcome.unconfirmed_hypotheses);
  const missingEvidence = asArray<string>(outcome.missing_evidence);
  const limitations = asArray<string>(outcome.limitations);
  const supported = [...findings, ...supportedHypotheses];
  const isEmptyCompletion = outcome.investigation_status === 'completed' && supported.length === 0;

  return (
    <section
      aria-label="Investigation conclusion"
      className="max-w-[68ch] rounded-xl border border-cyan-400/25 bg-slate-950/70 p-4 text-sm text-slate-100 shadow-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <SearchCheck className="h-4 w-4 text-cyan-300" />
        <h3 className="font-semibold text-cyan-100">Investigation conclusion</h3>
        <Badge variant={statusVariant(outcome.investigation_status)}>
          status: {humanize(outcome.investigation_status)}
        </Badge>
        <Badge variant={dispositionVariant(outcome.disposition)}>
          disposition: {humanize(outcome.disposition)}
        </Badge>
      </div>

      {progressItems.length ? (
        <div className="mt-4" aria-label="Operational progress">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-300">Operational progress</h4>
          <ol className="mt-2 space-y-2">
            {progressItems.map((step, index) => (
              <li key={step.step_id || `${step.purpose}-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={step.status === 'failed' ? 'destructive' : 'secondary'}>{humanize(step.status)}</Badge>
                  <span className="font-medium">{humanize(step.purpose)}</span>
                  {step.source ? <span className="font-mono text-[0.68rem] text-slate-500">{step.source}</span> : null}
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-300">
                  {step.evidence_summary || emptyStepCopy(step)}
                </p>
                {step.failure ? <p className="mt-1 text-xs text-amber-200">Failure: {step.failure}</p> : null}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <ConclusionList
        icon={<CheckCircle2 className="h-4 w-4 text-emerald-300" />}
        title="Supported by governed evidence"
        items={supported}
        emptyCopy={isEmptyCompletion ? 'No matching governed evidence was found for the approved scope.' : undefined}
      />
      <ConclusionList
        icon={<AlertTriangle className="h-4 w-4 text-amber-300" />}
        title="Not confirmed"
        items={unconfirmedHypotheses}
        tone="warning"
      />
      <ConclusionList title="Important missing evidence" items={missingEvidence} />
      <ConclusionList title="Limitations" items={limitations} />

      {(outcome.recommended_next_action || runStatus?.next_action) ? (
        <div className="mt-4 rounded-lg border border-cyan-500/20 bg-cyan-500/[0.06] px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-cyan-200">Recommended next action</p>
          <p className="mt-1 text-sm text-slate-200">{humanize(outcome.recommended_next_action ?? runStatus?.next_action ?? '')}</p>
        </div>
      ) : null}

      {outcome.remediation_offer_required ? (
        <div className="mt-4 border-t border-slate-800 pt-4">
          <p className="font-medium">Create remediation plan?</p>
          {remediationChoice === null ? (
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                className="rounded-md bg-cyan-400 px-3 py-1.5 text-xs font-semibold text-slate-950"
                onClick={() => setRemediationChoice('yes')}
              >
                Yes
              </button>
              <button
                type="button"
                className="rounded-md border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200"
                onClick={() => setRemediationChoice('not_now')}
              >
                Not now
              </button>
            </div>
          ) : remediationChoice === 'yes' ? (
            <p className="mt-2 text-xs text-cyan-100">Remediation planning requires a separately reviewed and approved plan.</p>
          ) : (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
              <CircleSlash2 className="h-3.5 w-3.5" /> No remediation plan was created.
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function asArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function ConclusionList({
  title,
  items,
  icon,
  tone = 'default',
  emptyCopy,
}: {
  title: string;
  items: string[];
  icon?: ReactNode;
  tone?: 'default' | 'warning';
  emptyCopy?: string;
}) {
  if (!items.length && !emptyCopy) return null;
  return (
    <div className={`mt-4 ${tone === 'warning' ? 'rounded-lg border border-amber-400/20 bg-amber-500/[0.06] p-3' : ''}`}>
      <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-300">
        {icon}{title}
      </h4>
      {items.length ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-200">
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-300">{emptyCopy}</p>
      )}
    </div>
  );
}

function emptyStepCopy(step: InvestigationProgressEvent): string {
  if (['completed', 'executed', 'fallback_taken'].includes(step.status)) {
    return 'No matching governed evidence was found for this step.';
  }
  return 'No governed evidence was produced by this step.';
}

function humanize(value: string): string {
  return value.replace(/_/g, ' ').trim();
}

function statusVariant(status: string): 'success' | 'warning' | 'destructive' | 'secondary' {
  if (status === 'completed') return 'success';
  if (status === 'blocked') return 'destructive';
  if (status === 'incomplete') return 'warning';
  return 'secondary';
}

function dispositionVariant(disposition: string): 'success' | 'warning' | 'destructive' {
  if (disposition === 'benign') return 'success';
  if (disposition === 'suspicious') return 'destructive';
  return 'warning';
}
