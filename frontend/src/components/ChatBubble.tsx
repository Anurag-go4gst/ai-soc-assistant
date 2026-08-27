import { Bot, ChevronRight, ShieldAlert, User } from 'lucide-react';
import { ExecutionReconciliationCard } from '@/components/ExecutionReconciliationCard';
import { PlanningOutcomeBanner } from '@/components/PlanningOutcomeBanner';
import { AnalystResponseCard } from '@/components/AnalystResponseCard';
import { AnalystSummaryCard } from '@/components/AnalystSummaryCard';
import { AnswerFeedbackControls } from '@/components/AnswerFeedbackControls';
import { EcVisualLanesPanel } from '@/components/EcVisualLanesPanel';
import { HumanReviewCard } from '@/components/HumanReviewCard';
import { ProposedActionsPanel } from '@/components/ProposedActionsPanel';
import { InvestigationLineagePanel } from '@/components/InvestigationLineagePanel';
import { UnderstandingProvenancePanel } from '@/components/UnderstandingProvenancePanel';
import { InvestigationProgressPanel, McpTransportBadge } from '@/components/InvestigationProgressPanel';
import { InvestigationPlanApprovalCard } from '@/components/InvestigationPlanApprovalCard';
import { RemediationPlanApprovalCard } from '@/components/RemediationPlanApprovalCard';
import { InvestigationOutcomeCard } from '@/components/InvestigationOutcomeCard';
import { ConditionalRequestedActionsCard } from '@/components/ConditionalRequestedActionsCard';
import { GovernedEmailDraftCard } from '@/components/GovernedEmailDraftCard';
import { ExperienceExecutionProgressPanel } from '@/components/experience-center/ExperienceExecutionProgressPanel';
import { Stage3DTracePanel } from '@/components/Stage3DTracePanel';
import { Badge } from '@/components/ui/badge';
import type { InvestigationProgressState } from '@/lib/investigationProgress';
import { investigationProgressToExperienceView } from '@/lib/investigationProgressToExperience';
import type { LegacyDemoCoordinationAction } from '@/lib/legacyDemoCoordination';
import { cn } from '@/lib/utils';
import type {
  CandidateSplEnvelope,
  ChatExecutionReviewOptions,
  ChatInvestigationReviewOptions,
  ChatRemediationReviewOptions,
  EcProvenance,
  ExecutionEnvelope,
  HumanReviewEnvelope,
  PlaceholderResponse,
  RequestedConditionalAction,
  RoutePlanShadowEnvelope,
  SplValidationEnvelope,
  WorkflowPlan,
} from '@/types/api';

export type AssistantDisplayStage = 'progress' | 'summary' | 'complete';

export interface SocChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  displayStage?: AssistantDisplayStage;
  investigationProgress?: InvestigationProgressState | null;
  progressDemoMode?: boolean;
  demoScenarioId?: string | null;
  coordinationAction?: LegacyDemoCoordinationAction | null;
  /** Capture provenance for the MCP-transport honesty badge (B6). */
  ecProvenance?: EcProvenance | null;
  traceId?: string;
  note?: string;
  routing?: {
    selectedSkill?: string | null;
    confidence?: number | null;
    toolPlan?: string[] | null;
    disagreement?: boolean | null;
    disagreementReason?: string | null;
  };
  trace?: PlaceholderResponse | null;
  workflowPlan?: WorkflowPlan | null;
  candidateSpl?: CandidateSplEnvelope | null;
  splValidation?: SplValidationEnvelope | null;
  execution?: ExecutionEnvelope | null;
  humanReview?: HumanReviewEnvelope | null;
}

interface ChatBubbleProps {
  message: SocChatMessage;
  investigationBusy?: boolean;
  onExecutionReview?: (payload: ChatExecutionReviewOptions, label: string) => void;
  onInvestigationReview?: (payload: ChatInvestigationReviewOptions, label: string, originalQuery: string) => void;
  onRemediationReview?: (payload: ChatRemediationReviewOptions, label: string, originalQuery: string) => void;
  onRetryFinalSynthesis?: () => void;
  onCoordinationConfirm?: (progressId: string) => void;
  onCoordinationSkip?: (progressId: string) => void;
}

export function ChatBubble({ message, investigationBusy = false, onExecutionReview, onInvestigationReview, onRemediationReview, onRetryFinalSynthesis, onCoordinationConfirm, onCoordinationSkip }: ChatBubbleProps) {
  const isUser = message.role === 'user';
  const showProgress = !isUser && message.displayStage === 'progress' && message.investigationProgress;
  const showSummaryOnly = !isUser && message.displayStage === 'summary' && message.trace;
  const showFullAnswer = !isUser && message.trace && message.displayStage !== 'progress' && message.displayStage !== 'summary';

  const scrollAnswerToTop = showSummaryOnly || showFullAnswer;
  const provenanceBadge = answerProvenanceBadge(message.trace ?? null);
  const understandingProvenance = understandingProvenanceFromTrace(message.trace ?? null);
  const showHowProduced = Boolean(
    message.trace?.investigation_lineage || understandingProvenance,
  );
  const blockedActionState = visibleBlockedActionState(message.trace);
  const requestedConditionalActions = requestedConditionalActionsFromTrace(message.trace);

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')} data-message-id={message.id}>
      <div
        className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-cyan-400 text-slate-950' : 'bg-slate-800 text-cyan-200 ring-1 ring-cyan-400/30',
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={cn('min-w-0 space-y-2', isUser ? 'max-w-[78%] items-end' : 'max-w-[94%] flex-1')}>
        {scrollAnswerToTop ? (
          <div
            data-answer-scroll-anchor={message.id}
            className="scroll-mt-4 h-0 w-full shrink-0"
            aria-hidden
          />
        ) : null}
        {showProgress ? null : showFullAnswer && message.trace?.analyst_response ? null : (
          <div
            className={cn(
              'rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm',
              isUser
                ? 'rounded-tr-md bg-cyan-400 text-slate-950'
                : 'max-w-[68ch] rounded-tl-md border border-slate-800 bg-slate-900/90 text-slate-100',
            )}
          >
            {message.content}
          </div>
        )}
        {showProgress && message.investigationProgress ? (
          (message.progressDemoMode ?? message.trace?.demo_mode) ? (
            <ExperienceExecutionProgressPanel
              state={investigationProgressToExperienceView(
                message.investigationProgress,
                true,
                message.coordinationAction,
              )}
              onRetry={onRetryFinalSynthesis}
              onCoordinationConfirm={
                message.coordinationAction?.status === 'waiting_for_analyst' && onCoordinationConfirm
                  ? () => onCoordinationConfirm(message.id)
                  : undefined
              }
              onCoordinationSkip={
                message.coordinationAction &&
                !message.coordinationAction.hil_required &&
                onCoordinationSkip
                  ? () => onCoordinationSkip(message.id)
                  : undefined
              }
              headerExtras={
                (message.ecProvenance ?? message.trace?.ec_provenance) ? (
                  <McpTransportBadge provenance={(message.ecProvenance ?? message.trace?.ec_provenance)!} />
                ) : null
              }
            />
          ) : (
            <InvestigationProgressPanel
              state={message.investigationProgress}
              demoMode={false}
              ecProvenance={message.ecProvenance ?? message.trace?.ec_provenance ?? null}
              onRetryFinalSynthesis={onRetryFinalSynthesis}
            />
          )
        ) : null}
        {showSummaryOnly && message.trace?.planning_outcome ? (
          <PlanningOutcomeBanner outcome={message.trace.planning_outcome} />
        ) : null}
        {showSummaryOnly ? <AnalystSummaryCard trace={message.trace!} /> : null}
        {showFullAnswer && message.trace?.planning_outcome ? (
          <PlanningOutcomeBanner outcome={message.trace.planning_outcome} />
        ) : null}
        {showFullAnswer && message.trace?.analyst_response ? (
          <div className="w-full min-w-0 space-y-2">
            {message.trace.human_review?.sop_reference ? (
              <div className="max-w-[72ch] rounded-lg border border-cyan-500/25 bg-cyan-500/[0.06] px-3 py-2 text-xs text-cyan-100">
                Governed citation: <span className="font-mono">{message.trace.human_review.sop_reference}</span>
              </div>
            ) : null}
            <AnalystResponseCard
              response={message.trace.analyst_response}
              foundationSecGovernance={message.trace.foundation_sec_governance}
            />
          </div>
        ) : null}
        {showFullAnswer && message.trace?.investigation_approval ? (
          <InvestigationPlanApprovalCard
            approval={message.trace.investigation_approval}
            busy={investigationBusy}
            originalQuery={message.trace.user_query}
            onReview={onInvestigationReview}
          />
        ) : null}
        {showFullAnswer && message.trace?.execution ? (
          <ExecutionReconciliationCard execution={message.trace.execution} />
        ) : null}
        {showFullAnswer && message.trace?.investigation_outcome?.investigation_status ? (
          <InvestigationOutcomeCard
            outcome={message.trace.investigation_outcome}
            progress={message.trace.investigation_progress}
            runStatus={message.trace.investigation_run_status}
          />
        ) : null}
        {showFullAnswer && requestedConditionalActions.length ? (
          <ConditionalRequestedActionsCard actions={requestedConditionalActions} />
        ) : null}
        {showFullAnswer && message.trace?.email_draft ? (
          <GovernedEmailDraftCard draft={message.trace.email_draft} />
        ) : null}
        {showFullAnswer && message.trace?.remediation_approval ? (
          <RemediationPlanApprovalCard
            approval={message.trace.remediation_approval}
            busy={investigationBusy}
            originalQuery={message.trace.user_query}
            onReview={onRemediationReview}
          />
        ) : null}
        {showFullAnswer && message.trace?.ec_visual_lanes ? (
          <EcVisualLanesPanel lanes={message.trace.ec_visual_lanes} />
        ) : null}
        {showFullAnswer && blockedActionState ? (
          <div className="w-full min-w-0 max-w-[72ch] rounded-xl border border-amber-400/40 bg-amber-500/[0.10] px-4 py-3 text-sm text-amber-50 shadow-sm">
            <div className="flex flex-wrap items-center gap-2 font-semibold">
              <ShieldAlert className="h-4 w-4 text-amber-300" />
              <span>Containment blocked</span>
              <Badge variant="warning">{blockedActionText(blockedActionState, 'block_class', 'blocked')}</Badge>
            </div>
            <p className="mt-2 leading-6">
              {blockedActionText(
                blockedActionState,
                'safe_message',
                blockedActionText(blockedActionState, 'banner', 'No action was performed.'),
              )}
            </p>
          </div>
        ) : null}
        {showFullAnswer && message.trace && !message.trace.analyst_response ? <AnalystSummaryCard trace={message.trace} /> : null}
        {showFullAnswer && message.trace?.proposed_actions?.length ? (
          <ProposedActionsPanel proposals={message.trace.proposed_actions} busy={investigationBusy} />
        ) : null}
        {showFullAnswer && message.trace?.human_review?.required && !message.trace.analyst_response ? (
          <HumanReviewCard
            review={message.trace.human_review}
            busy={investigationBusy}
            onExecutionReview={onExecutionReview}
            execution={message.trace.execution}
            runContract={message.trace.run_contract}
          />
        ) : null}
        {showFullAnswer && message.trace ? (
          <AnswerFeedbackControls turnId={message.trace.turn_id} traceId={message.trace.trace_id} />
        ) : null}
        {!isUser && !message.trace && message.note ? (
          <div className="flex flex-wrap gap-2">
            {message.traceId ? <Badge variant="secondary">trace {message.traceId.slice(0, 8)}</Badge> : null}
            <Badge>{message.note}</Badge>
          </div>
        ) : null}
        {showFullAnswer && showHowProduced ? (
          <details className="group rounded-lg border border-slate-800/70 bg-slate-950/40">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-300 transition hover:text-cyan-200">
              <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
              How this answer was produced
              <Badge variant={provenanceBadge.variant}>{provenanceBadge.label}</Badge>
            </summary>
            <div className="border-t border-slate-800/70 p-3">
              {understandingProvenance ? (
                <UnderstandingProvenancePanel provenance={understandingProvenance} />
              ) : null}
              {message.trace?.route_plan_shadow ? (
                <ShadowNarrationReveal shadow={message.trace.route_plan_shadow} />
              ) : null}
              {message.trace?.investigation_lineage ? (
                <InvestigationLineagePanel lineage={message.trace.investigation_lineage} />
              ) : null}
            </div>
          </details>
        ) : null}
        {showFullAnswer && message.trace ? (
          <details className="group rounded-lg border border-slate-800/70 bg-slate-950/40">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-400 transition hover:text-cyan-200">
              <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
              Technical evidence path
            </summary>
            <div className="border-t border-slate-800/70 p-3">
              <Stage3DTracePanel trace={message.trace} />
            </div>
          </details>
        ) : null}
        {!isUser && !message.trace && message.routing?.selectedSkill ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{message.routing.selectedSkill}</Badge>
              {typeof message.routing.confidence === 'number' ? (
                <Badge>{message.routing.confidence.toFixed(2)}</Badge>
              ) : null}
              <Badge variant={message.routing.disagreement ? 'warning' : 'success'}>
                {message.routing.disagreement ? 'compare: disagree' : 'compare: agree'}
              </Badge>
            </div>
            {message.routing.toolPlan?.length ? (
              <p className="mt-2 font-mono text-[0.7rem] text-slate-400">{message.routing.toolPlan.join(' → ')}</p>
            ) : null}
            <p className="mt-2 text-slate-400">Routing complete. SPL/MCP execution is not enabled yet.</p>
          </div>
        ) : null}
        {!isUser && !message.trace && message.workflowPlan ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">workflow plan</Badge>
              <Badge variant="warning">{message.workflowPlan.status}</Badge>
              <Badge variant={message.workflowPlan.execution_enabled ? 'success' : 'secondary'}>
                execution {message.workflowPlan.execution_enabled ? 'enabled' : 'disabled'}
              </Badge>
            </div>
            <ol className="mt-2 space-y-1">
              {message.workflowPlan.steps.map((step) => (
                <li key={`${step.order}-${step.name}`} className="flex gap-2">
                  <span className="font-mono text-slate-500">{step.order}.</span>
                  <span>{step.name}</span>
                </li>
              ))}
            </ol>
            {message.workflowPlan.required_connectors.length ? (
              <p className="mt-2 font-mono text-[0.7rem] text-slate-400">
                connectors: {message.workflowPlan.required_connectors.join(', ')}
              </p>
            ) : null}
            <p className="mt-2 text-slate-400">Workflow planning only. No tool execution has happened.</p>
          </div>
        ) : null}
        {!isUser && !message.trace && message.candidateSpl ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">candidate SPL</Badge>
              <Badge>{message.candidateSpl.generation_mode}</Badge>
              <Badge variant={message.splValidation?.approved ? 'success' : 'destructive'}>
                {message.splValidation?.approved ? 'approved' : 'rejected'}
              </Badge>
            </div>
            {message.candidateSpl.candidate_spl.trim() ? (
              <code className="mt-2 block overflow-x-auto rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[0.7rem] text-cyan-100">
                {message.candidateSpl.candidate_spl}
              </code>
            ) : null}
            {message.splValidation?.reject_reasons.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {message.splValidation.reject_reasons.map((reason) => (
                  <Badge key={reason} variant="destructive">{reason}</Badge>
                ))}
              </div>
            ) : null}
            {message.splValidation?.warnings.length ? (
              <p className="mt-2 text-amber-100">{message.splValidation.warnings.join(', ')}</p>
            ) : null}
            <p className="mt-2 text-slate-400">SPL validation complete. MCP execution is disabled.</p>
          </div>
        ) : null}
        {!isUser && !message.trace && message.execution ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">execution</Badge>
              <Badge variant={message.execution.status === 'executed' ? 'success' : message.execution.status === 'failed' ? 'destructive' : 'warning'}>
                {message.execution.status}
              </Badge>
              <Badge>{message.execution.execution_intent}</Badge>
            </div>
            {message.execution.selected_mcp_server || message.execution.selected_mcp_tool ? (
              <p className="mt-2 font-mono text-[0.7rem] text-slate-400">
                {message.execution.selected_mcp_server ?? 'no-server'} / {message.execution.selected_mcp_tool ?? 'no-tool'}
              </p>
            ) : null}
            <p className="mt-2 text-slate-400">{message.execution.tool_selection_reason}</p>
            {message.execution.block_reason ? (
              <Badge className="mt-2" variant="warning">{message.execution.block_reason}</Badge>
            ) : null}
            {message.execution.status === 'executed' ? (
              <div className="mt-2">
                <Badge variant="success">{message.execution.result_count} result preview rows</Badge>
                <code className="mt-2 block max-h-40 overflow-auto rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[0.7rem] text-cyan-100">
                  {JSON.stringify(message.execution.results_preview, null, 2)}
                </code>
              </div>
            ) : null}
            <p className="mt-2 text-slate-400">Final LLM synthesis is not enabled yet.</p>
          </div>
        ) : null}
        {!isUser && !message.trace && message.humanReview?.required ? (
          <div className="rounded-md border border-amber-400/30 bg-amber-500/10 p-3 text-xs text-amber-50">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="warning">human review</Badge>
              <Badge variant="secondary">{message.humanReview.review_type}</Badge>
              <Badge>{message.humanReview.reviewer_role}</Badge>
            </div>
            <p className="mt-2">{message.humanReview.safe_message_for_user}</p>
            <p className="mt-1 font-mono text-[0.7rem] text-amber-100">{message.humanReview.reason}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {message.humanReview.allowed_actions.map((action) => (
                <Badge key={action} variant="outline">{action}</Badge>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function requestedConditionalActionsFromTrace(
  trace: PlaceholderResponse | null | undefined,
): RequestedConditionalAction[] {
  const resolved = trace?.control_plane_trace?.resolved_query;
  if (!resolved || typeof resolved !== 'object' || Array.isArray(resolved)) return [];
  const actions = (resolved as Record<string, unknown>).requested_conditional_actions;
  return Array.isArray(actions)
    ? actions.filter((action): action is RequestedConditionalAction => (
        Boolean(action)
        && typeof action === 'object'
        && !Array.isArray(action)
        && ['remediation', 'email_draft'].includes(String((action as Record<string, unknown>).action_kind))
        && (action as Record<string, unknown>).lifecycle_state === 'PENDING_CONDITION'
      ))
    : [];
}

function visibleBlockedActionState(trace: PlaceholderResponse | null | undefined): Record<string, unknown> | null {
  const state = trace?.blocked_action_state;
  if (!state || state.visible !== true || state.status !== 'blocked') {
    return null;
  }
  return state;
}

function blockedActionText(state: Record<string, unknown>, key: string, fallback: string): string {
  const value = state[key];
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function understandingProvenanceFromTrace(
  trace: PlaceholderResponse | null,
): { lines?: { label: string; value: string }[] } | null {
  const block = trace?.control_plane_trace?.understanding_provenance;
  if (!block || typeof block !== 'object') {
    return null;
  }
  const lines = (block as { lines?: unknown }).lines;
  if (!Array.isArray(lines) || !lines.length) {
    return null;
  }
  return block as { lines?: { label: string; value: string }[] };
}

function answerProvenanceBadge(trace: PlaceholderResponse | null): { label: string; variant: 'success' | 'warning' | 'outline' } {
  if (!trace) return { label: 'review-only / no live execution', variant: 'outline' };
  if (trace.demo_mode) return { label: 'scenario-backed', variant: 'warning' };
  const runContract = trace.run_contract ?? {};
  const executionStatus = typeof runContract.execution_status === 'string' ? runContract.execution_status : trace.execution?.status;
  const collectedEvidenceCount =
    typeof runContract.collected_evidence_count === 'number' ? runContract.collected_evidence_count : 0;
  const allowLiveLanguage = runContract.allow_live_result_language === true;
  if (executionStatus === 'executed' && collectedEvidenceCount > 0 && allowLiveLanguage) {
    return { label: 'live-backed', variant: 'success' };
  }
  return { label: 'review-only / no live execution', variant: 'outline' };
}

function ShadowNarrationReveal({ shadow }: { shadow: RoutePlanShadowEnvelope }) {
  if (!shadow.analyst_summary_shadow_available || !shadow.analyst_summary_shadow_text) {
    return null;
  }
  const bullets = shadow.analyst_summary_trace_bullets ?? [];
  return (
    <div className="mb-3 rounded-md border border-amber-500/20 bg-amber-950/20 px-3 py-3 text-xs text-slate-300">
      <p className="font-semibold text-amber-200/90">Dormant: shadow narration (no execution)</p>
      <p className="mt-2 leading-5 text-slate-200">{shadow.analyst_summary_shadow_text}</p>
      {bullets.length ? (
        <ul className="mt-2 list-disc space-y-1 pl-4 text-slate-400">
          {bullets.map((bullet) => (
            <li key={bullet}>{bullet}</li>
          ))}
        </ul>
      ) : null}
      {shadow.analyst_summary_dropped_reasons?.length ? (
        <p className="mt-2 font-mono text-[0.65rem] text-amber-300/80">
          dropped: {shadow.analyst_summary_dropped_reasons.join(', ')}
        </p>
      ) : null}
    </div>
  );
}
