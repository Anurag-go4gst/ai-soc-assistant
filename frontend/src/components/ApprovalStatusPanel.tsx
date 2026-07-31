import { UserCheck } from 'lucide-react';
import type { ExecutionEnvelope, HumanReviewEnvelope, PlaceholderResponse } from '@/types/api';
import { Badge } from '@/components/ui/badge';

export function ApprovalStatusPanel({ trace }: { trace: PlaceholderResponse | null }) {
  if (!trace) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-400">
        Run a chat investigation to see approval and execution posture for the latest turn.
      </div>
    );
  }

  const review = trace.human_review;
  const execution = trace.execution;
  const runContract = (trace.run_contract ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-3 text-sm text-slate-300">
      <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
        <div className="flex items-center gap-2 font-semibold text-slate-100">
          <UserCheck className="h-4 w-4 text-cyan-300" />
          Human review
        </div>
        {review?.required ? (
          <div className="mt-2 space-y-2">
            <Badge variant="warning">{review.review_type.replace(/_/g, ' ')}</Badge>
            <p className="leading-relaxed">{review.safe_message_for_user}</p>
          </div>
        ) : (
          <p className="mt-2 text-slate-400">No human review required on the latest turn.</p>
        )}
      </div>
      <ExecutionPostureSummary execution={execution} runContract={runContract} />
    </div>
  );
}

function ExecutionPostureSummary({
  execution,
  runContract,
}: {
  execution: ExecutionEnvelope | null | undefined;
  runContract: Record<string, unknown>;
}) {
  const mcpAllowed = runContract.mcp_allowed === true;
  const executionAuthorized = runContract.execution_authorized === true;
  const blockReason = execution?.block_reason;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <p className="font-semibold text-slate-100">Execution posture (authoritative)</p>
      <ul className="mt-2 space-y-1 text-xs text-slate-400">
        <li>Status: <span className="text-slate-200">{execution?.status ?? 'not evaluated'}</span></li>
        <li>MCP allowed this turn: <span className="text-slate-200">{mcpAllowed ? 'yes' : 'no'}</span></li>
        <li>Execution authorized: <span className="text-slate-200">{executionAuthorized ? 'yes' : 'no'}</span></li>
        {blockReason ? <li>Block reason: <span className="text-amber-200">{blockReason}</span></li> : null}
        {execution?.outcome_uncertain ? (
          <li className="text-amber-200">Outcome uncertain — reconcile before retry.</li>
        ) : null}
      </ul>
      <p className="mt-2 text-xs text-slate-500">Posture reflects the latest chat response, not global settings snapshots.</p>
    </div>
  );
}
