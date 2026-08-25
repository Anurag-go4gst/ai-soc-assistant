/** Analyst-facing labels for workflow control next-action tokens (P5). */

const WORKFLOW_CONTROL_LABELS: Record<string, string> = {
  BLOCK: 'Unable to proceed — additional evidence required',
  BLOCKED: 'Unable to proceed — additional evidence required',
  DEGRADE: 'Continue with available evidence',
  CLARIFY: 'Clarification required',
  CONTINUE: 'Continue investigation',
  CALL_T4: 'Semantic understanding required',
};

export function formatAnalystNextAction(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return '';
  }
  const mapped = WORKFLOW_CONTROL_LABELS[trimmed.toUpperCase()];
  if (mapped) {
    return mapped;
  }
  return trimmed.replace(/_/g, ' ');
}

export function isWorkflowControlToken(raw: string): boolean {
  return raw.trim().toUpperCase() in WORKFLOW_CONTROL_LABELS;
}
