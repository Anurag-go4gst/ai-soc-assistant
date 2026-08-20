import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import type { EcAgentPlanStep, EcAgentWorkflowPayload } from '@/components/ec/types';
import type { ExperienceExecutionProgressView } from '@/lib/experienceCenterExecution';
import { ExperienceExecutionProgressPanel } from '@/components/experience-center/ExperienceExecutionProgressPanel';
import { EcInvestigationResultList, EcInvestigationSummaryStrip } from '@/components/ec/EcInvestigationResultList';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { scrollIntoScrollParent } from '@/lib/scrollIntoScrollParent';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

function statusBadgeClass(status: string): string {
  const token = status.toUpperCase();
  if (token === 'COMPLETE' || token === 'VERIFIED' || token === 'APPLIED' || token === 'CREATED' || token === 'SENT' || token === 'DEPLOYED' || token === 'ACTIVE') {
    return 'border-emerald-500/40 text-emerald-100';
  }
  if (token === 'NOT_REQUIRED') return 'border-slate-600 text-slate-300';
  if (token === 'RUNNING') return 'border-cyan-500/40 text-cyan-100';
  if (token === 'FAILED' || token === 'BLOCKED') return 'border-rose-500/40 text-rose-100';
  return 'border-slate-600 text-slate-300';
}

function splitLabeledPoint(point: string): { label: string | null; body: string } {
  const match = point.trim().match(/^([A-Za-z][A-Za-z0-9 /&-]{1,40}):\s+([\s\S]+)$/);
  if (!match) return { label: null, body: point.trim() };
  return { label: match[1], body: match[2].trim() };
}

function ConclusionPoints({ points }: { points: string[] }) {
  const items = points.filter((point) => point.trim());
  if (!items.length) return null;
  return (
    <ol className="mt-3 space-y-2" data-ec-section="conclusion-points">
      {items.map((point, index) => {
        const { label, body } = splitLabeledPoint(point);
        return (
          <li
            key={`${index}-${point.slice(0, 48)}`}
            className="flex gap-3 rounded-md border border-slate-800/80 bg-slate-950/45 px-3 py-2.5"
          >
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan-500/15 text-xs font-semibold text-cyan-100">
              {index + 1}
            </span>
            <div className="min-w-0 space-y-1">
              {label ? (
                <p className="text-sm font-semibold tracking-wide text-cyan-100">{label}</p>
              ) : null}
              <p className="text-sm leading-relaxed text-slate-300">{body}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ConnectionTrace({
  connector,
  steps,
}: {
  connector?: string;
  steps: Array<{ label: string; status: string }>;
}) {
  const visible = steps.filter((step) => step.label?.trim());
  if (!visible.length) return null;
  return (
    <div className="mt-4 rounded-lg border border-slate-800/80 bg-slate-950/50 p-3">
      {connector ? (
        <p className="text-xs font-semibold uppercase tracking-wide text-cyan-300/90">{connector}</p>
      ) : null}
      <ol className="mt-2 space-y-2">
        {visible.map((step) => {
          const status = step.status.toLowerCase();
          const dotClass =
            status === 'complete'
              ? 'bg-emerald-400'
              : status === 'active'
                ? 'bg-cyan-400 animate-pulse'
                : 'bg-slate-600';
          return (
            <li key={step.label} className="flex items-start gap-2 text-sm text-slate-300">
              <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', dotClass)} aria-hidden="true" />
              <span className={status === 'active' ? 'text-cyan-100' : undefined}>{step.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function RemediationProgressList({
  header,
  steps,
  anomalousAssetIds,
  scenarioId,
  sessionId,
  ecActions,
  onEcActionUpdate,
}: {
  header: string;
  steps: EcAgentPlanStep[];
  anomalousAssetIds: string[];
  scenarioId?: string;
  sessionId?: string | null;
  ecActions?: import('@/components/ec/types').EcActionRecord[];
  onEcActionUpdate?: (action: import('@/components/ec/types').EcActionRecord) => void;
}) {
  return (
    <EcInvestigationResultList
      header={header}
      steps={steps}
      anomalousAssetIds={anomalousAssetIds}
      variant="remediation"
      scenarioId={scenarioId}
      sessionId={sessionId}
      ecActions={ecActions}
      onActionUpdate={onEcActionUpdate}
    />
  );
}

function ProposedPlan({
  steps,
  summary,
  editable,
  selectedIds,
  onToggle,
}: {
  steps: EcAgentPlanStep[];
  summary?: string;
  editable: boolean;
  selectedIds: Set<string>;
  onToggle: (id: string, checked: boolean) => void;
}) {
  return (
    <div className="space-y-3">
      {summary ? <p className="text-sm leading-relaxed text-slate-300">{summary}</p> : null}
      <ul className="space-y-2">
        {steps.map((step) => (
          <li key={step.id} className="rounded-lg border border-slate-800/80 bg-slate-900/35 px-3 py-3">
            <div className="flex items-start gap-3">
              {editable ? (
                <input
                  id={`ec-plan-${step.id}`}
                  type="checkbox"
                  checked={selectedIds.has(step.id)}
                  onChange={(event) => onToggle(step.id, event.target.checked)}
                  className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500"
                />
              ) : (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400/80" aria-hidden="true" />
              )}
              <div className="min-w-0 flex-1">
                <label htmlFor={editable ? `ec-plan-${step.id}` : undefined} className="text-sm font-medium text-slate-100">
                  {step.title}
                </label>
                {step.summary ? <p className="mt-1 text-sm text-slate-400">{step.summary}</p> : null}
                {step.tools?.length ? (
                  <p className="mt-1 text-xs text-slate-500">{step.tools.join(' · ')}</p>
                ) : null}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EcAgentWorkflow({
  workflow,
  busy = false,
  executionProgress = null,
  onRunInvestigation,
  onRunRemediation,
  onHilApprove,
  onHilSkip,
  onCreateRemediationPlan,
  onDeclineRemediationPlan,
  onViewEvidence,
  scenarioId,
  sessionId,
  ecActions = [],
  onEcActionUpdate,
}: {
  workflow: EcAgentWorkflowPayload;
  busy?: boolean;
  executionProgress?: ExperienceExecutionProgressView | null;
  onRunInvestigation: (selectedStepIds: string[]) => void;
  onRunRemediation: (selectedStepIds: string[]) => void;
  onHilApprove: () => void;
  onHilSkip: () => void;
  onCreateRemediationPlan?: () => void;
  onDeclineRemediationPlan?: () => void;
  onViewEvidence?: () => void;
  scenarioId?: string;
  sessionId?: string | null;
  ecActions?: import('@/components/ec/types').EcActionRecord[];
  onEcActionUpdate?: (action: import('@/components/ec/types').EcActionRecord) => void;
}) {
  const phase = workflow.phase ?? 'plan';
  const invSteps = workflow.investigation_plan?.steps ?? [];
  const remSteps = workflow.remediation_plan?.steps ?? [];

  const defaultInvSelected = useMemo(
    () => invSteps.filter((step) => step.selected !== false).map((step) => step.id),
    [invSteps],
  );
  const defaultRemSelected = useMemo(
    () => remSteps.filter((step) => step.selected !== false).map((step) => step.id),
    [remSteps],
  );

  const [invSelected, setInvSelected] = useState<Set<string>>(() => new Set(defaultInvSelected));
  const [remSelected, setRemSelected] = useState<Set<string>>(() => new Set(defaultRemSelected));
  const [editingInv, setEditingInv] = useState(false);

  const remPlanStepIds = useMemo(
    () =>
      (workflow.remediation_results?.steps ?? remSteps)
        .filter((step) => step.selected !== false)
        .map((step) => step.id),
    [remSteps, workflow.remediation_results?.steps],
  );

  useEffect(() => {
    if (workflow.lifecycle !== 'REMEDIATION_PLAN_READY') return;
    const ids = defaultRemSelected.length ? defaultRemSelected : remPlanStepIds;
    if (!ids.length) return;
    setRemSelected((current) => (current.size ? current : new Set(ids)));
  }, [defaultRemSelected, remPlanStepIds, workflow.lifecycle]);

  const remExecuting =
    Boolean(executionProgress) ||
    workflow.lifecycle === 'REMEDIATING' ||
    workflow.lifecycle === 'VERIFYING';
  const remPlanReview = workflow.lifecycle === 'REMEDIATION_PLAN_READY' && !remExecuting;
  const remComplete = workflow.lifecycle === 'COMPLETE' || workflow.lifecycle === 'PARTIAL';

  useEffect(() => {
    if (
      !['REMEDIATION_PLAN_READY', 'REMEDIATING', 'VERIFYING', 'COMPLETE'].includes(workflow.lifecycle)
    ) {
      return;
    }
    const timer = window.setTimeout(() => {
      const panel = document.querySelector('[data-ec-section="recommended-remediation"]');
      scrollIntoScrollParent(panel instanceof HTMLElement ? panel : null, {
        block: 'start',
        behavior: 'smooth',
      });
    }, 60);
    return () => window.clearTimeout(timer);
  }, [workflow.lifecycle]);

  const remPlanReviewBanner = remPlanReview ? (
    <div className="flex items-start gap-2 rounded-lg border border-cyan-500/30 bg-cyan-950/20 px-4 py-3 text-sm text-cyan-50">
      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" aria-hidden="true" />
      <div>
        <p className="font-medium">Review remediation plan</p>
        <p className="mt-1 text-cyan-100/85">
          Expand each step to review SPL, tickets, and email drafts. Nothing runs until you approve.
        </p>
      </div>
    </div>
  ) : null;
  const artifactContext = {
    scenarioId,
    sessionId,
    ecActions,
    onActionUpdate: onEcActionUpdate,
  };

  const isPlanTurn = phase === 'plan';
  const isInvestigationCompleteTurn = phase === 'investigation_complete';
  const isRemediationTurn = phase === 'remediation';
  const showRemediationPlan = Boolean(workflow.remediation_plan?.visible && isRemediationTurn);
  const anomalousAssetIds = workflow.normalized_state?.anomalous_asset_ids ?? [];
  const progressSteps =
    workflow.execution_progress?.steps ??
    (workflow.execution_progress?.phase === 'investigation' ? invSteps : remSteps);
  const remScopedProgress = Boolean(executionProgress && remExecuting);
  const progressPanel = executionProgress ? (
    <section
      className="rounded-lg border border-cyan-500/25 bg-cyan-950/15 p-4"
      data-ec-section="agent-execution-progress"
    >
      <ExperienceExecutionProgressPanel state={executionProgress} />
    </section>
  ) : null;

  return (
    <div className="w-full max-w-none space-y-6" data-ec-section="agent-workflow">
      {workflow.opening_narrative ? (
        <section className="rounded-lg border border-slate-800/80 bg-slate-900/40 p-4">
          <p className="text-base leading-relaxed text-slate-100">{workflow.opening_narrative}</p>
        </section>
      ) : null}

      {workflow.brief && isPlanTurn ? (
        <section className="overflow-x-auto rounded-lg border border-slate-800/80">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/60">
                <th className="w-1/2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-cyan-100">Facts</th>
                <th className="w-1/2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-cyan-100">
                  Investigation objective
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="align-top">
                <td className="border-r border-slate-800/80 px-4 py-3">
                  <ul className="space-y-1.5 text-slate-300">
                    {(workflow.brief.what_i_know ?? []).map((item) => (
                      <li key={item} className="flex gap-2">
                        <span className="text-cyan-500/80">·</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="px-4 py-3">
                  <ol className="list-decimal space-y-1.5 pl-5 text-slate-300">
                    {(workflow.brief.objective ?? []).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ol>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      ) : null}

      {workflow.action_plan && isPlanTurn ? (
        <section className="rounded-lg border border-slate-800/80 bg-slate-900/35 p-4">
          <EcSectionHeading>Action plan</EcSectionHeading>
          {workflow.action_plan.summary ? (
            <p className="mt-2 text-sm leading-relaxed text-slate-300">{workflow.action_plan.summary}</p>
          ) : null}
          <ul className="mt-3 space-y-1.5 text-sm text-slate-200">
            {(workflow.action_plan.steps ?? []).map((item) => (
              <li key={item} className="flex gap-2">
                <span className="text-cyan-500/80">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {isPlanTurn ? (
        <section className="space-y-3">
          <EcSectionHeading>Proposed investigation</EcSectionHeading>
          <ProposedPlan
            steps={invSteps.filter((step) => !step.optional || editingInv)}
            summary={workflow.investigation_plan?.summary}
            editable={workflow.lifecycle === 'PLAN_READY' || editingInv}
            selectedIds={invSelected}
            onToggle={(id, checked) => {
              setInvSelected((current) => {
                const next = new Set(current);
                if (checked) next.add(id);
                else next.delete(id);
                return next;
              });
            }}
          />
          {workflow.lifecycle === 'PLAN_READY' ? (
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={busy || invSelected.size === 0}
                className="bg-cyan-600 hover:bg-cyan-600/90"
                onClick={() => onRunInvestigation([...invSelected])}
              >
                {workflow.investigation_plan?.primary_cta ?? 'Run investigation'}
              </Button>
              <Button type="button" variant="outline" disabled={busy} onClick={() => setEditingInv((v) => !v)}>
                {editingInv ? 'Done editing' : workflow.investigation_plan?.secondary_cta ?? 'Edit plan'}
              </Button>
            </div>
          ) : null}
        </section>
      ) : null}

      {executionProgress && !remScopedProgress ? progressPanel : null}

      {workflow.hil_prompt && isPlanTurn ? (
        <section className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-4" data-ec-section="agent-hil">
          <EcSectionHeading>{workflow.hil_prompt.title ?? 'Approval required'}</EcSectionHeading>
          <p className="mt-2 text-sm leading-relaxed text-slate-200">{workflow.hil_prompt.body}</p>
          {workflow.hil_prompt.connection_trace?.length ? (
            <ConnectionTrace
              connector={workflow.hil_prompt.connector}
              steps={workflow.hil_prompt.connection_trace}
            />
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" disabled={busy} onClick={onHilApprove}>
              {workflow.hil_prompt.approve_label ?? 'Approve'}
            </Button>
            <Button type="button" variant="outline" disabled={busy} onClick={onHilSkip}>
              {workflow.hil_prompt.skip_label ?? 'Skip'}
            </Button>
          </div>
        </section>
      ) : null}

      {!isPlanTurn && workflow.investigation_summary ? (
        <EcInvestigationSummaryStrip summary={workflow.investigation_summary} />
      ) : null}

      {!isPlanTurn && workflow.investigation_results?.steps?.length ? (
        <EcInvestigationResultList
          header={workflow.investigation_results.header ?? 'Investigation results'}
          steps={workflow.investigation_results.steps}
          anomalousAssetIds={anomalousAssetIds}
          {...artifactContext}
        />
      ) : null}

      {!isPlanTurn && workflow.execution_progress?.phase === 'investigation' && progressSteps.length ? (
        <EcInvestigationResultList
          header={workflow.execution_progress?.header ?? 'Investigation in progress'}
          steps={progressSteps}
          anomalousAssetIds={anomalousAssetIds}
          {...artifactContext}
        />
      ) : null}

      {!isPlanTurn && workflow.investigation_conclusion ? (
        <section
          className="rounded-lg border border-slate-800/70 bg-slate-900/35 px-4 py-3"
          data-ec-section="investigation-post-summary"
        >
          {workflow.investigation_conclusion.headline ? (
            <p className="text-sm font-semibold leading-snug text-slate-50">
              {workflow.investigation_conclusion.headline}
            </p>
          ) : null}
          {workflow.investigation_conclusion.narrative_points?.filter((point) => point.trim()).length ? (
            <ConclusionPoints points={workflow.investigation_conclusion.narrative_points} />
          ) : workflow.investigation_conclusion.narrative ? (
            <ConclusionPoints
              points={workflow.investigation_conclusion.narrative
                .split(/(?<=[.!?])\s+/)
                .filter((point) => point.trim())}
            />
          ) : null}
        </section>
      ) : null}

      {isInvestigationCompleteTurn && remScopedProgress ? progressPanel : null}

      {!isPlanTurn && workflow.executive_summary?.length && workflow.lifecycle !== 'COMPLETE' ? (
        <section
          className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-4"
          data-ec-section="executive-summary"
        >
          <EcSectionHeading>Executive summary</EcSectionHeading>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-slate-100">
            {workflow.executive_summary.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
          {onViewEvidence ? (
            <Button type="button" variant="outline" size="sm" className="mt-3" onClick={onViewEvidence}>
              View evidence
            </Button>
          ) : null}
        </section>
      ) : null}

      {isInvestigationCompleteTurn && workflow.remediation_offer && !showRemediationPlan ? (
        <section
          className="space-y-3 rounded-lg border border-cyan-500/25 bg-cyan-950/15 px-4 py-3"
          data-ec-section="remediation-offer"
        >
          <p className="text-sm font-semibold text-slate-50">
            {workflow.remediation_offer.title ?? 'Continue to remediation plan?'}
          </p>
          {workflow.remediation_offer.body ? (
            <p className="text-sm leading-relaxed text-slate-300">{workflow.remediation_offer.body}</p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={busy}
              className="bg-cyan-600 hover:bg-cyan-600/90"
              onClick={() => onCreateRemediationPlan?.()}
            >
              {workflow.remediation_offer.yes_label ?? 'Yes, create remediation plan'}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => onDeclineRemediationPlan?.()}
            >
              {workflow.remediation_offer.no_label ?? 'Not now'}
            </Button>
          </div>
        </section>
      ) : isInvestigationCompleteTurn && workflow.next_step_cta && !showRemediationPlan ? (
        <section className="flex flex-wrap gap-2" data-ec-section="investigation-next-step">
          <Button
            type="button"
            disabled={busy}
            className="bg-cyan-600 hover:bg-cyan-600/90"
            onClick={() => onCreateRemediationPlan?.()}
          >
            {workflow.next_step_cta.label ?? 'Continue to remediation plan'}
          </Button>
        </section>
      ) : null}

      {!isPlanTurn && workflow.unconfirmed?.filter((item) => item.trim()).length ? (
        <section className="rounded-lg border border-amber-500/20 bg-amber-950/10 p-4" data-ec-section="outstanding-uncertainty">
          <EcSectionHeading>Still unresolved</EcSectionHeading>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-200">
            {workflow.unconfirmed.filter((item) => item.trim()).map((item) => (
              <li key={item} className="flex gap-2 leading-relaxed">
                <span className="text-amber-400/80">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {!isPlanTurn && workflow.missing_evidence?.filter((item) => item.trim()).length ? (
        <section className="rounded-lg border border-slate-800/80 bg-slate-900/35 p-4">
          <EcSectionHeading>Optional evidence not collected</EcSectionHeading>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-300">
            {workflow.missing_evidence.filter((item) => item.trim()).map((item) => (
              <li key={item} className="flex gap-2">
                <span className="text-slate-500">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {(isRemediationTurn && showRemediationPlan) ? (
        <section className="space-y-4" data-ec-section="recommended-remediation">
          {remScopedProgress ? progressPanel : null}
          {remPlanReview && workflow.remediation_summary ? (
            <div data-ec-section="remediation-summary">
              <EcInvestigationSummaryStrip summary={workflow.remediation_summary} />
            </div>
          ) : null}

          {remPlanReview && workflow.remediation_conclusion ? (
            <section className="rounded-lg border border-slate-800/70 bg-slate-900/35 px-4 py-3">
              <EcSectionHeading>{workflow.remediation_conclusion.title ?? 'Remediation approach'}</EcSectionHeading>
              {workflow.remediation_conclusion.headline ? (
                <p className="mt-2 text-sm font-semibold text-slate-50">{workflow.remediation_conclusion.headline}</p>
              ) : null}
              {workflow.remediation_conclusion.narrative_points?.filter((point) => point.trim()).length ? (
                <ConclusionPoints points={workflow.remediation_conclusion.narrative_points} />
              ) : null}
            </section>
          ) : null}

          {remPlanReviewBanner}

          {remPlanReview && workflow.remediation_results?.steps?.length ? (
            <EcInvestigationResultList
              header={workflow.remediation_results.header ?? 'Remediation plan'}
              steps={workflow.remediation_results.steps}
              anomalousAssetIds={anomalousAssetIds}
              selectable
              expandDetails
              selectedIds={remSelected}
              variant="remediation"
              {...artifactContext}
              onToggleStep={(id, checked) => {
                setRemSelected((current) => {
                  const next = new Set(current);
                  if (checked) next.add(id);
                  else next.delete(id);
                  return next;
                });
              }}
            />
          ) : null}

          {remPlanReview && !workflow.remediation_results?.steps?.length ? (
            <ProposedPlan
              steps={remSteps}
              summary={workflow.remediation_plan?.summary}
              editable
              selectedIds={remSelected}
              onToggle={(id, checked) => {
                setRemSelected((current) => {
                  const next = new Set(current);
                  if (checked) next.add(id);
                  else next.delete(id);
                  return next;
                });
              }}
            />
          ) : null}

          {remPlanReview ? (
            <div className="flex flex-wrap gap-2" data-ec-section="remediation-approve">
              <Button
                type="button"
                disabled={busy || remSelected.size === 0}
                className="bg-cyan-600 hover:bg-cyan-600/90"
                onClick={() => onRunRemediation([...remSelected])}
              >
                {workflow.remediation_plan?.primary_cta ?? 'Approve remediation'}
              </Button>
            </div>
          ) : null}

          {remComplete && workflow.remediation_summary ? (
            <div data-ec-section="remediation-summary">
              <EcInvestigationSummaryStrip summary={workflow.remediation_summary} />
            </div>
          ) : null}

          {remComplete && workflow.remediation_results?.steps?.length ? (
            <EcInvestigationResultList
              header={workflow.remediation_results.header ?? 'Remediation results'}
              steps={workflow.remediation_results.steps}
              anomalousAssetIds={anomalousAssetIds}
              variant="remediation"
              expandDetails
              {...artifactContext}
            />
          ) : null}

        </section>
      ) : null}

      {isRemediationTurn && remExecuting && workflow.execution_progress?.phase === 'remediation' ? (
        <RemediationProgressList
          header={workflow.execution_progress.header ?? 'Remediation in progress'}
          steps={workflow.execution_progress.steps ?? remSteps}
          anomalousAssetIds={anomalousAssetIds}
          {...artifactContext}
        />
      ) : null}

      {workflow.final_summary && workflow.lifecycle === 'COMPLETE' ? (
        <section className="space-y-3 rounded-lg border border-emerald-500/25 bg-emerald-950/15 p-4" data-ec-section="executive-summary">
          <EcSectionHeading>{workflow.final_summary.title ?? 'Response completed'}</EcSectionHeading>
          <p className="text-lg font-semibold text-slate-50">{workflow.final_summary.headline}</p>
          <p className="text-sm text-slate-300">
            Current risk: {workflow.final_summary.risk_from ?? workflow.final_summary.risk_to} ·{' '}
            {workflow.final_summary.severity} · {workflow.final_summary.affected} · malicious use:{' '}
            {workflow.final_summary.compromise}
          </p>
          <ul className="space-y-1 text-sm text-slate-200">
            {(workflow.final_summary.completed ?? []).map((item) => (
              <li key={item}>✓ {item}</li>
            ))}
            {(workflow.final_summary.deferred ?? []).map((item) => (
              <li key={item} className="text-slate-400">— {item}</li>
            ))}
          </ul>
          {(workflow.final_summary.in_progress ?? []).length ? (
            <p className="text-sm text-amber-100">
              Still in progress: {(workflow.final_summary.in_progress ?? []).join(' · ')}
            </p>
          ) : null}
          <p className="text-sm text-slate-300">{workflow.final_summary.risk_note}</p>
          {workflow.executive_summary?.length ? (
            <ul className="space-y-2 border-t border-emerald-500/15 pt-3 text-sm leading-relaxed text-slate-100">
              {workflow.executive_summary.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {workflow.verification?.length && ['VERIFYING', 'COMPLETE'].includes(workflow.lifecycle) ? (
        <section className="space-y-2">
          <EcSectionHeading>Verification</EcSectionHeading>
          <ul className="space-y-2 text-sm">
            {workflow.verification.map((row) => (
              <li key={row.item} className={cn('flex flex-wrap items-center gap-2 rounded-md border border-slate-800/80 px-3 py-2')}>
                <span className="text-slate-100">{row.item}</span>
                <Badge variant="outline" className={statusBadgeClass(row.status)}>
                  {row.status}
                </Badge>
                <span className="text-slate-400">{row.detail}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
