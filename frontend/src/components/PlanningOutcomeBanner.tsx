import { AlertTriangle, HelpCircle, ShieldAlert } from 'lucide-react';
import { presentPlanningOutcome } from '@/lib/planningOutcome';
import type { PlanningOutcomeSummary } from '@/types/api';
import { cn } from '@/lib/utils';

export function PlanningOutcomeBanner({ outcome }: { outcome: PlanningOutcomeSummary | null | undefined }) {
  const presentation = presentPlanningOutcome(outcome);
  if (!presentation) return null;

  const Icon =
    outcome?.status === 'clarification_required' ? HelpCircle : outcome?.status === 'policy_blocked' ? ShieldAlert : AlertTriangle;
  const tone =
    presentation.variant === 'destructive'
      ? 'border-red-400/45 bg-red-500/[0.10] text-red-50'
      : presentation.variant === 'warning'
        ? 'border-amber-400/45 bg-amber-500/[0.10] text-amber-50'
        : 'border-cyan-400/40 bg-cyan-500/[0.08] text-cyan-50';

  return (
    <section
      className={cn('rounded-xl border px-4 py-3.5 shadow-sm', tone)}
      aria-labelledby="planning-outcome-heading"
      data-planning-outcome={outcome?.status}
    >
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <div className="min-w-0">
          <h3 id="planning-outcome-heading" className="text-sm font-semibold">{presentation.title}</h3>
          <p className="mt-2 text-sm leading-6">{presentation.userMessage}</p>
          <p className="mt-2 text-xs leading-5 opacity-90">
            <span className="font-semibold">Recovery: </span>
            {presentation.recoveryHint}
          </p>
        </div>
      </div>
    </section>
  );
}
