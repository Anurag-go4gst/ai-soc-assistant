import type { PlanningOutcomeSummary } from '@/types/api';

export type PlanningOutcomePresentationVariant = 'info' | 'warning' | 'destructive';

export interface PlanningOutcomePresentation {
  title: string;
  variant: PlanningOutcomePresentationVariant;
  userMessage: string;
  recoveryHint: string;
}

const TERMINAL_STATUSES = [
  'clarification_required',
  'policy_blocked',
  'planning_failed',
  'persistence_failed',
  'resolution_failed',
  'unsupported',
  'execution_failed',
] as const;

type TerminalStatus = (typeof TERMINAL_STATUSES)[number];

const TITLES: Record<TerminalStatus, string> = {
  clarification_required: 'Clarification needed',
  policy_blocked: 'Blocked by policy',
  planning_failed: 'Planning could not complete',
  persistence_failed: 'Turn not saved safely',
  resolution_failed: 'Context could not be resolved',
  unsupported: 'Request not supported',
  execution_failed: 'Execution step failed',
};

const VARIANTS: Record<TerminalStatus, PlanningOutcomePresentationVariant> = {
  clarification_required: 'info',
  policy_blocked: 'warning',
  planning_failed: 'destructive',
  persistence_failed: 'destructive',
  resolution_failed: 'warning',
  unsupported: 'warning',
  execution_failed: 'destructive',
};

function isTerminalStatus(status: string): status is TerminalStatus {
  return (TERMINAL_STATUSES as readonly string[]).includes(status);
}

export function presentPlanningOutcome(
  outcome: PlanningOutcomeSummary | null | undefined,
): PlanningOutcomePresentation | null {
  if (!outcome?.status || !isTerminalStatus(outcome.status)) {
    return null;
  }
  return {
    title: TITLES[outcome.status],
    variant: VARIANTS[outcome.status],
    userMessage: outcome.user_message,
    recoveryHint: outcome.recovery_hint,
  };
}

export function executionLabel(trace: {
  execution?: {
    status?: string | null;
    evidence_source?: string | null;
    execution_status_label?: string | null;
    block_reason?: string | null;
    outcome_uncertain?: boolean | null;
  } | null;
}): { label: string; variant: 'success' | 'warning' | 'destructive' | 'secondary' } {
  const execution = trace.execution;
  if (!execution?.status) {
    return { label: 'Not required', variant: 'secondary' };
  }
  if (execution.outcome_uncertain) {
    return { label: 'Outcome uncertain — reconcile manually', variant: 'warning' };
  }
  if (execution.status === 'executed') {
    const source = execution.evidence_source ?? '';
    if (source === 'live') return { label: 'Executed (live evidence)', variant: 'success' };
    if (source === 'mock') return { label: 'Executed (mock evidence)', variant: 'success' };
    return { label: 'Executed (review provenance)', variant: 'warning' };
  }
  if (execution.status === 'blocked' || execution.status === 'requires_human_review') {
    return { label: 'Blocked pending review', variant: 'warning' };
  }
  if (execution.status === 'failed') {
    return { label: 'Execution failed', variant: 'destructive' };
  }
  if (execution.status === 'skipped') {
    return { label: 'Not required', variant: 'secondary' };
  }
  return { label: execution.status.replace(/_/g, ' '), variant: 'secondary' };
}
