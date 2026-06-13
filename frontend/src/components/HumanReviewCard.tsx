import { useState } from 'react';
import { HelpCircle, ShieldAlert, UserCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ChatExecutionReviewOptions, ExecutionReviewAction, HumanReviewEnvelope } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

const REVIEW_META: Record<string, { title: string; icon: typeof ShieldAlert; tone: 'amber' | 'cyan' }> = {
  intent_clarification: { title: 'Clarification needed', icon: HelpCircle, tone: 'cyan' },
  execution_approval: { title: 'Approval required', icon: ShieldAlert, tone: 'amber' },
  analyst_review: { title: 'Analyst review required', icon: ShieldAlert, tone: 'amber' },
  spl_source_profile_clarification: { title: 'Source profile needed', icon: HelpCircle, tone: 'cyan' },
  spl_execution_confirmation: { title: 'Confirm search execution', icon: ShieldAlert, tone: 'amber' },
  spl_revision: { title: 'SPL revision needed', icon: HelpCircle, tone: 'cyan' },
};

function humanizeAction(action: string): string {
  return action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function HumanReviewCard({
  review,
  onExecutionReview,
  busy = false,
}: {
  review: HumanReviewEnvelope;
  onExecutionReview?: (payload: ChatExecutionReviewOptions, label: string) => void;
  busy?: boolean;
}) {
  const meta = REVIEW_META[review.review_type] ?? { title: 'Review required', icon: ShieldAlert, tone: 'amber' as const };
  const Icon = meta.icon;
  const tone =
    meta.tone === 'cyan'
      ? 'border-cyan-400/40 bg-cyan-500/[0.08]'
      : 'border-amber-400/45 bg-amber-500/[0.10]';
  const iconTone = meta.tone === 'cyan' ? 'text-cyan-300' : 'text-amber-300';
  const showSourceProfileLink =
    review.review_type === 'spl_source_profile_clarification' ||
    review.allowed_actions.includes('open_source_profile_settings');
  const showExecutionControls =
    review.review_type === 'spl_execution_confirmation' ||
    review.allowed_actions.includes('confirm_execution') ||
    review.allowed_actions.includes('provide_updated_spl');
  const [updatedSpl, setUpdatedSpl] = useState(review.proposed_normalized_spl ?? '');

  const submitReview = (action: ExecutionReviewAction) => {
    if (!onExecutionReview) return;
    if (action === 'confirm') {
      onExecutionReview({ execution_review_action: 'confirm' }, 'Confirm proposed SPL execution');
      return;
    }
    if (action === 'reject') {
      onExecutionReview({ execution_review_action: 'reject' }, 'Reject SPL execution');
      return;
    }
    onExecutionReview(
      {
        execution_review_action: 'update_spl',
        analyst_provided_spl: updatedSpl.trim(),
      },
      'Run updated SPL after safety checks',
    );
  };

  return (
    <div className={`rounded-xl border-l-4 ${tone} px-4 py-3.5 shadow-sm`}>
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 shrink-0 ${iconTone}`} />
        <span className="text-sm font-semibold text-slate-50">{meta.title}</span>
        <span className="ml-auto inline-flex items-center gap-1 text-[0.65rem] uppercase tracking-[0.14em] text-slate-400">
          <UserCheck className="h-3 w-3" />
          {review.reviewer_role.replace(/_/g, ' ')}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-100">{review.safe_message_for_user}</p>
      {showExecutionControls ? (
        <div className="mt-3 space-y-3 rounded-md border border-slate-700/80 bg-slate-950/50 p-3">
          <div className="space-y-1.5">
            <Label htmlFor="execution-review-spl" className="text-xs text-slate-300">
              Proposed or updated SPL
            </Label>
            <Textarea
              id="execution-review-spl"
              value={updatedSpl}
              onChange={(event) => setUpdatedSpl(event.target.value)}
              className="min-h-[110px] font-mono text-xs"
              placeholder="Paste an updated SPL/query here, or keep the proposed SPL and confirm."
            />
          </div>
          {review.selected_mcp_tool ? (
            <p className="text-[0.7rem] text-slate-500">
              Tool: <span className="font-mono text-slate-300">{review.selected_mcp_tool}</span>
              {review.selected_mcp_server ? (
                <>
                  {' '}
                  on <span className="font-mono text-slate-300">{review.selected_mcp_server}</span>
                </>
              ) : null}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" disabled={busy || !onExecutionReview} onClick={() => submitReview('confirm')}>
              Confirm & run
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={busy || !onExecutionReview || !updatedSpl.trim()}
              onClick={() => submitReview('update_spl')}
            >
              Run updated SPL
            </Button>
            <Button type="button" size="sm" variant="outline" disabled={busy || !onExecutionReview} onClick={() => submitReview('reject')}>
              Reject
            </Button>
          </div>
          <p className="text-[0.65rem] text-slate-500">
            Updated SPL is re-validated for indexes, sourcetypes, commands, and row limits before execution.
          </p>
        </div>
      ) : null}
      {showSourceProfileLink ? (
        <div className="mt-3">
          <Button asChild variant="outline" size="sm">
            <Link to="/settings/source-profiles">Open Source Profiles</Link>
          </Button>
        </div>
      ) : null}
      {review.allowed_actions.length && !showExecutionControls ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {review.allowed_actions.map((action) => (
            <span
              key={action}
              className="rounded-full border border-slate-600/70 bg-slate-900/60 px-3 py-1 text-xs font-medium text-slate-200"
            >
              {humanizeAction(action)}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
