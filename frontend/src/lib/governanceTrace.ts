import type { ExperienceCenterGovernance, PlaceholderResponse } from '@/types/api';

/** Shared governance panels from /chat or Experience Center demo. */
export function resolveGovernanceTrace(
  trace: PlaceholderResponse,
): ExperienceCenterGovernance | null | undefined {
  return trace.governance_trace ?? trace.experience_center_governance;
}
