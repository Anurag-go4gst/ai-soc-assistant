/** Diagnostic authority-tier labels from control_plane_trace (metadata only). */

export type AuthorityTier = 'AUTHORITATIVE' | 'PLANNING' | 'ADVISORY' | 'DIAGNOSTIC';

export interface AuthorityTierEntry {
  authority_tier: AuthorityTier;
  authority_note?: string;
}

export interface TraceAuthoritySectionRow {
  key: string;
  label: string;
  tier: AuthorityTier;
  note?: string;
  source: 'index' | 'section';
}

const TIER_ORDER: AuthorityTier[] = ['AUTHORITATIVE', 'PLANNING', 'ADVISORY', 'DIAGNOSTIC'];

export const TRACE_AUTHORITY_SECTION_LABELS: Record<string, string> = {
  route_adjudication: 'Route adjudication',
  routing_provenance: 'Routing provenance',
  evidence_plan: 'Evidence plan',
  resource_planner: 'Resource planner',
  planning_decision: 'Planning decision',
  llm_intent_advisory: 'LLM intent advisory',
  llm_advisory_trace: 'LLM advisory trace',
  llm_plan_validation: 'LLM plan validation',
  rag_trace: 'RAG trace',
  precondition_evaluation: 'Route-plan shadow preconditions',
  candidate_spl_generation: 'SPL candidate generation',
  spl_slot_binding: 'SPL slot binding',
  spl_artifact_handoff_summary: 'SPL artifact handoff',
  slot_constraint_projection: 'SPL slot constraint projection',
  mcp_execution: 'MCP execution gate',
  answer_contract: 'Answer contract',
  final_answer_validation: 'Final answer validation',
  run_contract: 'RunContract',
  final_evidence_gate: 'FinalEvidenceGate',
  route_plan_shadow_authority: 'Route-plan shadow',
};

const SECTION_SCAN_KEYS = [
  'run_contract',
  'final_evidence_gate',
  'evidence_plan',
  'resource_planner',
  'route_adjudication',
  'routing_provenance',
  'llm_advisory_trace',
  'llm_intent_advisory',
  'llm_plan_validation',
  'rag_trace',
  'candidate_spl_generation',
  'spl_artifact_handoff_summary',
  'spl_slot_binding',
  'slot_constraint_projection',
  'mcp_execution',
  'answer_contract',
  'final_answer_validation',
  'planning_decision',
  'precondition_evaluation',
  'route_plan_shadow_authority',
] as const;

function isAuthorityTier(value: unknown): value is AuthorityTier {
  return value === 'AUTHORITATIVE' || value === 'PLANNING' || value === 'ADVISORY' || value === 'DIAGNOSTIC';
}

function readAuthorityEntry(value: unknown): AuthorityTierEntry | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (!isAuthorityTier(record.authority_tier)) {
    return null;
  }
  return {
    authority_tier: record.authority_tier,
    authority_note: typeof record.authority_note === 'string' ? record.authority_note : undefined,
  };
}

export function formatTraceAuthoritySectionLabel(key: string): string {
  return TRACE_AUTHORITY_SECTION_LABELS[key] ?? key.replace(/_/g, ' ');
}

export function readTraceAuthorityIndex(
  controlPlaneTrace: Record<string, unknown> | null | undefined,
): Record<string, AuthorityTierEntry> | null {
  const raw = controlPlaneTrace?.trace_authority_index;
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const index: Record<string, AuthorityTierEntry> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    const entry = readAuthorityEntry(value);
    if (entry) {
      index[key] = entry;
    }
  }
  return Object.keys(index).length ? index : null;
}

export function collectTraceAuthorityRows(
  controlPlaneTrace: Record<string, unknown> | null | undefined,
): TraceAuthoritySectionRow[] {
  if (!controlPlaneTrace) {
    return [];
  }

  const rows: TraceAuthoritySectionRow[] = [];
  const seen = new Set<string>();

  const index = readTraceAuthorityIndex(controlPlaneTrace);
  if (index) {
    for (const [key, entry] of Object.entries(index)) {
      rows.push({
        key,
        label: formatTraceAuthoritySectionLabel(key),
        tier: entry.authority_tier,
        note: entry.authority_note,
        source: 'index',
      });
      seen.add(key);
    }
  }

  for (const key of SECTION_SCAN_KEYS) {
    if (seen.has(key)) {
      continue;
    }
    const entry = readAuthorityEntry(controlPlaneTrace[key]);
    if (!entry) {
      continue;
    }
    rows.push({
      key,
      label: formatTraceAuthoritySectionLabel(key),
      tier: entry.authority_tier,
      note: entry.authority_note,
      source: 'section',
    });
    seen.add(key);
  }

  rows.sort((left, right) => {
    const tierDelta = TIER_ORDER.indexOf(left.tier) - TIER_ORDER.indexOf(right.tier);
    if (tierDelta !== 0) {
      return tierDelta;
    }
    return left.label.localeCompare(right.label);
  });

  return rows;
}

export function hasTraceAuthorityData(
  controlPlaneTrace: Record<string, unknown> | null | undefined,
): boolean {
  return collectTraceAuthorityRows(controlPlaneTrace).length > 0;
}

export function summarizeTraceAuthorityTiers(rows: TraceAuthoritySectionRow[]): string {
  const counts = new Map<AuthorityTier, number>();
  for (const row of rows) {
    counts.set(row.tier, (counts.get(row.tier) ?? 0) + 1);
  }
  return TIER_ORDER.filter((tier) => counts.has(tier))
    .map((tier) => `${counts.get(tier)} ${tier.toLowerCase()}`)
    .join(' · ');
}
