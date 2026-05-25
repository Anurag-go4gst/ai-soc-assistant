import { Bot, ChevronRight, User } from 'lucide-react';
import { AnalystResponseCard } from '@/components/AnalystResponseCard';
import { AnalystSummaryCard } from '@/components/AnalystSummaryCard';
import { HumanReviewCard } from '@/components/HumanReviewCard';
import { Stage3DTracePanel } from '@/components/Stage3DTracePanel';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type {
  CandidateSplEnvelope,
  ExecutionEnvelope,
  HumanReviewEnvelope,
  PlaceholderResponse,
  SplValidationEnvelope,
  WorkflowPlan,
} from '@/types/api';

export interface SocChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
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
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-cyan-400 text-slate-950' : 'bg-slate-800 text-cyan-200 ring-1 ring-cyan-400/30',
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={cn('min-w-0 space-y-2', isUser ? 'max-w-[78%] items-end' : 'max-w-[94%] flex-1')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm',
            isUser
              ? 'rounded-tr-md bg-cyan-400 text-slate-950'
              : 'rounded-tl-md border border-slate-800 bg-slate-900/90 text-slate-100',
          )}
        >
          {message.content}
        </div>
        {!isUser && message.trace?.analyst_response ? <AnalystResponseCard response={message.trace.analyst_response} /> : null}
        {!isUser && message.trace && !message.trace.analyst_response ? <AnalystSummaryCard trace={message.trace} /> : null}
        {!isUser && message.trace?.human_review?.required && !message.trace.analyst_response ? <HumanReviewCard review={message.trace.human_review} /> : null}
        {!isUser && !message.trace && message.note ? (
          <div className="flex flex-wrap gap-2">
            {message.traceId ? <Badge variant="secondary">trace {message.traceId.slice(0, 8)}</Badge> : null}
            <Badge>{message.note}</Badge>
          </div>
        ) : null}
        {!isUser && message.trace ? (
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
