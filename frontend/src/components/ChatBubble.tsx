import { Bot, ChevronRight, User } from 'lucide-react';
import { AnalystResponseCard } from '@/components/AnalystResponseCard';
import { AnalystSummaryCard } from '@/components/AnalystSummaryCard';
import { AnswerFeedbackControls } from '@/components/AnswerFeedbackControls';
import { HumanReviewCard } from '@/components/HumanReviewCard';
import { InvestigationLineagePanel } from '@/components/InvestigationLineagePanel';
import { InvestigationProgressPanel } from '@/components/InvestigationProgressPanel';
import { Stage3DTracePanel } from '@/components/Stage3DTracePanel';
import { Badge } from '@/components/ui/badge';
import type { InvestigationProgressState } from '@/lib/investigationProgress';
import { cn } from '@/lib/utils';
import type {
  CandidateSplEnvelope,
  ChatExecutionReviewOptions,
  EcProvenance,
  ExecutionEnvelope,
  HumanReviewEnvelope,
  PlaceholderResponse,
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
  onRetryFinalSynthesis?: () => void;
}

export function ChatBubble({ message, investigationBusy = false, onExecutionReview, onRetryFinalSynthesis }: ChatBubbleProps) {
  const isUser = message.role === 'user';
  const showProgress = !isUser && message.displayStage === 'progress' && message.investigationProgress;
  const showSummaryOnly = !isUser && message.displayStage === 'summary' && message.trace;
  const showFullAnswer = !isUser && message.trace && message.displayStage !== 'progress' && message.displayStage !== 'summary';

  const scrollAnswerToTop = showSummaryOnly || showFullAnswer;

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
          <InvestigationProgressPanel
            state={message.investigationProgress}
            demoMode={message.progressDemoMode ?? message.trace?.demo_mode ?? false}
            ecProvenance={message.ecProvenance ?? message.trace?.ec_provenance ?? null}
            onRetryFinalSynthesis={onRetryFinalSynthesis}
          />
        ) : null}
        {showSummaryOnly ? <AnalystSummaryCard trace={message.trace!} /> : null}
        {showFullAnswer && message.trace?.analyst_response ? (
          <AnalystResponseCard
            response={message.trace.analyst_response}
            foundationSecGovernance={message.trace.foundation_sec_governance}
          />
        ) : null}
        {showFullAnswer && message.trace && !message.trace.analyst_response ? <AnalystSummaryCard trace={message.trace} /> : null}
        {showFullAnswer && message.trace?.human_review?.required && !message.trace.analyst_response ? (
          <HumanReviewCard
            review={message.trace.human_review}
            busy={investigationBusy}
            onExecutionReview={onExecutionReview}
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
        {showFullAnswer && message.trace?.investigation_lineage ? (
          <details className="group rounded-lg border border-slate-800/70 bg-slate-950/40">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-300 transition hover:text-cyan-200">
              <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
              How this answer was produced
              {message.trace.demo_mode ? <Badge variant="warning">scenario-backed</Badge> : <Badge variant="success">live-backed</Badge>}
            </summary>
            <div className="border-t border-slate-800/70 p-3">
              {message.trace.route_plan_shadow ? (
                <ShadowNarrationReveal shadow={message.trace.route_plan_shadow} />
              ) : null}
              <InvestigationLineagePanel lineage={message.trace.investigation_lineage} />
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
            <code className="mt-2 block overflow-x-auto rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[0.7rem] text-cyan-100">
              {message.candidateSpl.candidate_spl}
            </code>
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
