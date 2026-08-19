import type { ExperienceCenterResponse } from '@/components/ec/types';

/** Default orchestration follow-ups that render inline execution progress in agent mode. */
export const DEFAULT_AGENT_INLINE_PROGRESS_FOLLOWUPS = new Set([
  'run_investigation',
  'approve_investigation_vuln_scan',
  'skip_investigation_vuln_scan',
  'create_remediation_plan',
  'run_remediation',
]);

export function isAgentWorkflowMode(envelope: ExperienceCenterResponse | null | undefined): boolean {
  return Boolean(envelope?.ec_agent_workflow);
}

export function suppressesAgentExecutionProgressPanel(
  envelope: ExperienceCenterResponse | null | undefined,
): boolean {
  return isAgentWorkflowMode(envelope);
}

export function isAgentExecutiveSummaryFollowUp(
  envelope: ExperienceCenterResponse | null | undefined,
  followUpId: string,
): boolean {
  return isAgentWorkflowMode(envelope) && followUpId === 'generate_executive_summary';
}

export function isAgentInlineProgressFollowUp(
  envelope: ExperienceCenterResponse | null | undefined,
  followUpId: string,
  keepAnswer: boolean,
): boolean {
  return (
    isAgentWorkflowMode(envelope) &&
    keepAnswer &&
    DEFAULT_AGENT_INLINE_PROGRESS_FOLLOWUPS.has(followUpId)
  );
}

export function agentLifecycleScrollTarget(
  lifecycle: string | null | undefined,
): string | null {
  switch (lifecycle) {
    case 'INVESTIGATION_COMPLETE':
      return '[data-ec-section="investigation-summary"]';
    case 'REMEDIATION_PLAN_READY':
      return '[data-ec-section="remediation-summary"]';
    case 'INVESTIGATION_NEEDS_APPROVAL':
      return '[data-ec-section="agent-hil"]';
    default:
      return null;
  }
}
