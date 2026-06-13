import { HelpCircle, ShieldAlert, UserCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { HumanReviewEnvelope } from '@/types/api';
import { Button } from '@/components/ui/button';

const REVIEW_META: Record<string, { title: string; icon: typeof ShieldAlert; tone: 'amber' | 'cyan' }> = {
  intent_clarification: { title: 'Clarification needed', icon: HelpCircle, tone: 'cyan' },
  execution_approval: { title: 'Approval required', icon: ShieldAlert, tone: 'amber' },
  analyst_review: { title: 'Analyst review required', icon: ShieldAlert, tone: 'amber' },
  spl_source_profile_clarification: { title: 'Source profile needed', icon: HelpCircle, tone: 'cyan' },
};

function humanizeAction(action: string): string {
  return action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function HumanReviewCard({ review }: { review: HumanReviewEnvelope }) {
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
      {showSourceProfileLink ? (
        <div className="mt-3">
          <Button asChild variant="outline" size="sm">
            <Link to="/settings/source-profiles">Open Source Profiles</Link>
          </Button>
        </div>
      ) : null}
      {review.allowed_actions.length ? (
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
