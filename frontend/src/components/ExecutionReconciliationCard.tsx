import { AlertTriangle } from 'lucide-react';
import type { ExecutionEnvelope } from '@/types/api';
import { Badge } from '@/components/ui/badge';

const REASON_LABEL: Record<string, string> = {
  execution_outcome_uncertain: 'A prior execution may have completed outside this assistant. Reconcile tool state before retrying.',
  execution_step_in_progress: 'Another worker may still be executing this step. Wait or escalate before retrying.',
};

export function ExecutionReconciliationCard({ execution }: { execution: ExecutionEnvelope | null | undefined }) {
  if (!execution?.outcome_uncertain) return null;
  const reason = execution.reconciliation_reason ?? 'execution_outcome_uncertain';
  const copy = REASON_LABEL[reason] ?? REASON_LABEL.execution_outcome_uncertain;

  return (
    <section
      className="rounded-xl border border-amber-400/45 bg-amber-500/[0.10] px-4 py-3.5 text-amber-50 shadow-sm"
      aria-labelledby="execution-reconciliation-heading"
      data-reconciliation-reason={reason}
    >
      <div className="flex flex-wrap items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-amber-300" aria-hidden />
        <h3 id="execution-reconciliation-heading" className="text-sm font-semibold">Manual reconciliation required</h3>
        <Badge variant="warning">{reason.replace(/_/g, ' ')}</Badge>
      </div>
      <p className="mt-2 text-sm leading-6">{copy}</p>
      <p className="mt-2 text-xs text-amber-100/90">Do not retry execution until you confirm whether the prior side effect completed.</p>
    </section>
  );
}
