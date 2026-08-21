import { useState } from 'react';
import { AlertTriangle, CheckCircle2, PencilLine, ShieldAlert, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { ChatRemediationReviewOptions, RemediationApprovalState } from '@/types/api';

interface RemediationPlanApprovalCardProps {
  approval: RemediationApprovalState;
  busy?: boolean;
  originalQuery?: string | null;
  onReview?: (payload: ChatRemediationReviewOptions, label: string, originalQuery: string) => void;
}

/**
 * P10/P11 remediation HIL. Approving produces the immutable envelope, then the
 * production action gate executes only its registered steps and returns receipts.
 * Steps that no registered connector can perform stay visible as manual work
 * rather than being hidden, so the analyst sees the whole job.
 */
export function RemediationPlanApprovalCard({
  approval,
  busy = false,
  originalQuery,
  onReview,
}: RemediationPlanApprovalCardProps) {
  const [removed, setRemoved] = useState<string[]>([]);
  const [editing, setEditing] = useState(false);
  const actionable = approval.allowed_actions.length > 0 && Boolean(onReview) && Boolean(originalQuery);
  const summary = approval.plan_summary;
  const steps = approval.validated_plan?.steps ?? [];

  const review = (payload: ChatRemediationReviewOptions, label: string) => {
    if (!onReview || !originalQuery) return;
    onReview(payload, label, originalQuery);
  };

  const toggleRemoved = (stepId: string) => {
    setRemoved((current) =>
      current.includes(stepId) ? current.filter((item) => item !== stepId) : [...current, stepId],
    );
  };

  const statusVariant =
    approval.status === 'approved' ? 'success' : approval.status === 'cancelled' || approval.status === 'declined' ? 'secondary' : 'warning';

  return (
    <section
      className="max-w-[72ch] rounded-xl border border-amber-400/35 bg-slate-950/80 p-4 text-sm text-slate-100 shadow-sm"
      aria-label="Remediation plan approval"
    >
      <div className="flex flex-wrap items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-amber-300" />
        <h3 className="font-semibold text-amber-100">
          {approval.status === 'offered' ? 'Remediation available' : 'Remediation plan'}
        </h3>
        <Badge variant={statusVariant}>{approval.status.replace(/_/g, ' ')}</Badge>
      </div>

      <p className="mt-3 leading-6 text-slate-200">{approval.safe_message}</p>

      {summary ? (
        <>
          <PlanList title="What will change" values={summary.what_will_change} />
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Why</p>
            <p className="mt-1 leading-6 text-slate-200">{summary.why_it_matters}</p>
          </div>
          {summary.what_stays_manual.length > 0 ? (
            <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-500/[0.07] px-3 py-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-200">
                <AlertTriangle className="h-3.5 w-3.5" /> Stays manual — no registered connector
              </div>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-amber-50">
                {summary.what_stays_manual.map((value) => <li key={value}>{value}</li>)}
              </ul>
            </div>
          ) : null}
          <PlanList title="How it is verified" values={summary.how_it_is_verified} />
        </>
      ) : null}

      {approval.approved_envelope ? (
        <div className="mt-4 rounded-lg border border-emerald-400/25 bg-emerald-500/[0.07] px-3 py-2 text-xs text-emerald-100">
          <div className="flex items-center gap-2 font-semibold">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Approved remediation envelope v{approval.approved_envelope.envelope_version}
          </div>
          <p className="mt-1">
            Execution was submitted through the governed action gate using this exact approved version.
          </p>
        </div>
      ) : null}

      {approval.execution_result ? (
        <div className="mt-3 rounded-lg border border-cyan-400/25 bg-cyan-500/[0.07] px-3 py-2 text-xs text-cyan-50">
          <p className="font-semibold">Action verification</p>
          {approval.execution_result.refused_reason ? (
            <p className="mt-1 text-rose-200">Refused: {approval.execution_result.refused_reason}</p>
          ) : null}
          <ul className="mt-1 space-y-1">
            {approval.execution_result.receipts.map((receipt) => (
              <li key={`${receipt.step_id}-${receipt.capability_id}`}>
                {receipt.step_id}: {receipt.status} · verification {receipt.verification_status}
                {receipt.reason ? ` · ${receipt.reason}` : ''}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {editing && actionable ? (
        <div className="mt-4 rounded-lg border border-slate-700 bg-slate-900/80 p-3">
          <p className="text-xs font-semibold text-slate-300">Deselect any step you do not want in the plan</p>
          <ul className="mt-2 space-y-1">
            {steps.map((step) => (
              <li key={step.step_id} className="flex items-start gap-2">
                <input
                  id={`remediation-step-${step.step_id}`}
                  type="checkbox"
                  className="mt-1"
                  checked={!removed.includes(step.step_id)}
                  onChange={() => toggleRemoved(step.step_id)}
                />
                <label htmlFor={`remediation-step-${step.step_id}`} className="text-slate-200">
                  {step.description}
                  {step.execution_mode === 'manual_or_alternate' ? (
                    <span className="ml-1 text-amber-200">(manual)</span>
                  ) : null}
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                review(
                  {
                    remediation_review_action: 'edit',
                    remediation_plan_edits: { removed_step_ids: removed },
                  },
                  'Submit edited remediation plan',
                )
              }
              className="rounded-md bg-amber-300 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
            >
              Revalidate edit
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setEditing(false)}
              className="rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-200 disabled:opacity-50"
            >
              Keep current plan
            </button>
          </div>
        </div>
      ) : null}

      {actionable && !editing ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {approval.allowed_actions.includes('create') ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => review({ remediation_review_action: 'create' }, 'Create remediation plan')}
              className="rounded-md bg-amber-300 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
            >
              Create remediation plan
            </button>
          ) : null}
          {approval.allowed_actions.includes('decline') ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => review({ remediation_review_action: 'decline' }, 'Not now')}
              className="rounded-md border border-slate-600 px-3 py-2 text-xs text-slate-100 disabled:opacity-50"
            >
              Not now
            </button>
          ) : null}
          {approval.allowed_actions.includes('approve') ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => review({ remediation_review_action: 'approve' }, 'Approve remediation plan')}
              className="inline-flex items-center gap-1.5 rounded-md bg-amber-300 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> Approve
            </button>
          ) : null}
          {approval.allowed_actions.includes('edit') ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-600 px-3 py-2 text-xs text-slate-100 disabled:opacity-50"
            >
              <PencilLine className="h-3.5 w-3.5" /> Edit
            </button>
          ) : null}
          {approval.allowed_actions.includes('cancel') ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => review({ remediation_review_action: 'cancel' }, 'Cancel remediation')}
              className="inline-flex items-center gap-1.5 rounded-md border border-rose-400/40 px-3 py-2 text-xs text-rose-100 disabled:opacity-50"
            >
              <XCircle className="h-3.5 w-3.5" /> Cancel
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function PlanList({ title, values }: { title: string; values: string[] }) {
  if (!values.length) return null;
  return (
    <div className="mt-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-200">
        {values.map((value) => <li key={value}>{value}</li>)}
      </ul>
    </div>
  );
}
