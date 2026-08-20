import type { ExperienceCenterResponse } from '@/components/ec/types';

/** Default orchestration follow-ups that render inline execution progress in agent mode. */
export const DEFAULT_AGENT_INLINE_PROGRESS_FOLLOWUPS = new Set([
  'run_investigation',
  'approve_investigation_vuln_scan',
  'skip_investigation_vuln_scan',
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

/** Agent follow-ups that reveal the next workflow state immediately (no execution journey). */
export const AGENT_IMMEDIATE_REVEAL_FOLLOWUPS = new Set([
  'create_remediation_plan',
  'decline_remediation_plan',
]);

export function isAgentImmediateRevealFollowUp(
  envelope: ExperienceCenterResponse | null | undefined,
  followUpId: string,
  keepAnswer: boolean,
): boolean {
  return (
    isAgentWorkflowMode(envelope) &&
    keepAnswer &&
    AGENT_IMMEDIATE_REVEAL_FOLLOWUPS.has(followUpId)
  );
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
      return '[data-ec-section="executive-summary"]';
    case 'REMEDIATION_PLAN_READY':
    case 'REMEDIATING':
    case 'VERIFYING':
      return '[data-ec-section="recommended-remediation"]';
    case 'COMPLETE':
      return '[data-ec-section="executive-summary"]';
    case 'INVESTIGATION_NEEDS_APPROVAL':
      return '[data-ec-section="agent-hil"]';
    default:
      return null;
  }
}
