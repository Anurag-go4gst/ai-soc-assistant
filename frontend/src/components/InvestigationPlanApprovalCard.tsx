import { useMemo, useState } from 'react';
import { CheckCircle2, PencilLine, ShieldCheck, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { ChatInvestigationReviewOptions, InvestigationApprovalState } from '@/types/api';

interface InvestigationPlanApprovalCardProps {
  approval: InvestigationApprovalState;
  busy?: boolean;
  originalQuery?: string | null;
  onReview?: (payload: ChatInvestigationReviewOptions, label: string, originalQuery: string) => void;
}

export function InvestigationPlanApprovalCard({
  approval,
  busy = false,
  originalQuery,
  onReview,
}: InvestigationPlanApprovalCardProps) {
  const [editing, setEditing] = useState(false);
  const initialEvidence = useMemo(
    () => approval.plan_summary.what_will_be_checked.join('\n'),
    [approval.plan_summary.what_will_be_checked],
  );
  const [evidenceText, setEvidenceText] = useState(initialEvidence);
  const actionable = approval.allowed_actions.length > 0 && Boolean(onReview) && Boolean(originalQuery);

  const review = (payload: ChatInvestigationReviewOptions, label: string) => {
    if (!onReview || !originalQuery) return;
    onReview(payload, label, originalQuery);
  };

  return (
    <section className="w-full min-w-0 rounded-xl border border-cyan-400/35 bg-slate-950/80 p-4 text-sm text-slate-100 shadow-sm" aria-label="Investigation plan approval">
      <div className="flex flex-wrap items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-cyan-300" />
        <h3 className="font-semibold text-cyan-100">Investigation plan ready</h3>
        <Badge variant={approval.status === 'approved' ? 'success' : approval.status === 'cancelled' ? 'secondary' : 'warning'}>
          {approval.status.replace(/_/g, ' ')}
        </Badge>
        <Badge variant="outline">v{approval.handoff_version}</Badge>
      </div>

      <p className="mt-3 leading-6 text-slate-200">{approval.safe_message}</p>

      <PlanSection title="What will be checked" values={approval.plan_summary.what_will_be_checked} />
      <div className="mt-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Why</p>
        <p className="mt-1 leading-6 text-slate-200">{approval.plan_summary.why_it_matters}</p>
      </div>
      <PlanSection title="Scope and time" values={approval.plan_summary.scope_and_time} />
      <PlanSection title="Useful resources and capabilities" values={approval.plan_summary.resources_and_capabilities} />

      {approval.approved_envelope ? (
        <div className="mt-4 rounded-lg border border-emerald-400/25 bg-emerald-500/[0.07] px-3 py-2 text-xs text-emerald-100">
          <div className="flex items-center gap-2 font-semibold">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Immutable read-only envelope v{approval.approved_envelope.envelope_version}
          </div>
          <p className="mt-1">Writes and remediation remain prohibited. Approval did not itself execute a tool.</p>
        </div>
      ) : null}

      {editing && actionable ? (
        <div className="mt-4 rounded-lg border border-slate-700 bg-slate-900/80 p-3">
          <label className="text-xs font-semibold text-slate-300" htmlFor={`investigation-edit-${approval.handoff_id}`}>
            Evidence checks, one per line
          </label>
          <textarea
            id={`investigation-edit-${approval.handoff_id}`}
            value={evidenceText}
            onChange={(event) => setEvidenceText(event.target.value)}
            rows={5}
            className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400"
          />
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => review({
                investigation_review_action: 'edit',
                investigation_handoff_id: approval.handoff_id,
                investigation_handoff_version: approval.handoff_version,
                investigation_plan_edits: {
                  evidence_needed: evidenceText.split('\n').map((item) => item.trim()).filter(Boolean),
                },
              }, 'Submit edited investigation plan')}
              className="rounded-md bg-cyan-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
            >
              Revalidate edit
            </button>
            <button type="button" disabled={busy} onClick={() => setEditing(false)} className="rounded-md border border-slate-700 px-3 py-2 text-xs text-slate-200 disabled:opacity-50">
              Keep current plan
            </button>
          </div>
        </div>
      ) : null}

      {actionable && !editing ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => review({
              investigation_review_action: 'run',
              investigation_handoff_id: approval.handoff_id,
              investigation_handoff_version: approval.handoff_version,
            }, 'Approve investigation plan')}
            className="inline-flex items-center gap-1.5 rounded-md bg-cyan-400 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
          >
            <CheckCircle2 className="h-3.5 w-3.5" /> Approve
          </button>
          <button type="button" disabled={busy} onClick={() => setEditing(true)} className="inline-flex items-center gap-1.5 rounded-md border border-slate-600 px-3 py-2 text-xs text-slate-100 disabled:opacity-50">
            <PencilLine className="h-3.5 w-3.5" /> Edit
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => review({
              investigation_review_action: 'cancel',
              investigation_handoff_id: approval.handoff_id,
              investigation_handoff_version: approval.handoff_version,
            }, 'Cancel investigation')}
            className="inline-flex items-center gap-1.5 rounded-md border border-rose-400/40 px-3 py-2 text-xs text-rose-100 disabled:opacity-50"
          >
            <XCircle className="h-3.5 w-3.5" /> Cancel
          </button>
        </div>
      ) : null}
    </section>
  );
}

function PlanSection({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="mt-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-200">
        {values.map((value) => <li key={value}>{value}</li>)}
      </ul>
    </div>
  );
}
