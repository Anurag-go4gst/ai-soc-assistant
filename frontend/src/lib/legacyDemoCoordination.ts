import type { InvestigationProgressStep } from '@/lib/investigationProgress';

export const LEGACY_COORDINATION_STEP_ID = 'demo_coordination';

export const PRIORITY_LEGACY_DEMO_SCENARIOS = [
  'firewall_deny_coordinated_attack',
  'ir_containment_advisory_firewall_incident',
  'cert_in_ot_reporting_obligation',
  'guided_investigation_supply_chain',
] as const;

export type PriorityLegacyDemoScenarioId = (typeof PRIORITY_LEGACY_DEMO_SCENARIOS)[number];

export type LegacyDemoCoordinationActionType =
  | 'firewall_block'
  | 'ir_containment'
  | 'stakeholder_reporting'
  | 'supplier_follow_up';

export type LegacyDemoCoordinationActionStatus =
  | 'pending'
  | 'waiting_for_analyst'
  | 'verifying'
  | 'completed'
  | 'skipped'
  | 'failed'
  | 'configuration_required';

export interface LegacyDemoCoordinationAction {
  action_id: string;
  action_type: LegacyDemoCoordinationActionType;
  label: string;
  scenario_id: PriorityLegacyDemoScenarioId;
  phase_step_id: string;
  status: LegacyDemoCoordinationActionStatus;
  hil_required: boolean;
  available: boolean;
  description: string;
  draft_summary?: string | null;
  result_message?: string | null;
}

interface ScenarioCoordinationTemplate {
  action_type: LegacyDemoCoordinationActionType;
  label: string;
  description: string;
  draft_summary: string;
  hil_required: boolean;
  insert_after_step_id: string;
  simulated_result: string;
  verify_message: string;
}

const SCENARIO_COORDINATION: Record<PriorityLegacyDemoScenarioId, ScenarioCoordinationTemplate> = {
  firewall_deny_coordinated_attack: {
    action_type: 'firewall_block',
    label: 'Prepare perimeter deny coordination',
    description:
      'Request a governed SOAR / firewall block for the primary external offender after evidence review. No automatic enforcement.',
    draft_summary:
      'Indicator 203.0.113.14 · playbook perimeter_deny · requires SOC lead sign-off before SOAR submission.',
    hil_required: true,
    insert_after_step_id: 'mcp_evidence',
    simulated_result: 'SOAR playbook queued for analyst-approved perimeter deny (simulated · no live firewall change).',
    verify_message: 'Verified block request recorded in the incident timeline (simulated).',
  },
  ir_containment_advisory_firewall_incident: {
    action_type: 'ir_containment',
    label: 'Confirm IR containment advisory',
    description:
      'Acknowledge perimeter deny, host segmentation, and identity session review steps from governed IR guidance.',
    draft_summary:
      'Perimeter deny on approved block list · segment affected hosts at next change window · identity session review.',
    hil_required: true,
    insert_after_step_id: 'rag',
    simulated_result: 'IR containment advisory acknowledged and logged for change-window execution (simulated).',
    verify_message: 'Containment checklist verified against SOC-IR-ADV-FW guidance (simulated).',
  },
  cert_in_ot_reporting_obligation: {
    action_type: 'stakeholder_reporting',
    label: 'Coordinate CERT-In reporting stakeholders',
    description:
      'Prepare CISO and legal/compliance coordination for the 6-hour CERT-In reporting window. Email transport is not sent in this demo step.',
    draft_summary:
      'Stakeholders: CISO, legal/compliance · channel CERT-In portal · preserve ICS/OT logs before filing.',
    hil_required: true,
    insert_after_step_id: 'rag',
    simulated_result: 'Stakeholder coordination draft prepared for analyst review (simulated · no email sent).',
    verify_message: 'Reporting coordination checklist recorded (simulated).',
  },
  guided_investigation_supply_chain: {
    action_type: 'supplier_follow_up',
    label: 'Request supplier security coordination',
    description:
      'Open a supplier / build-pipeline security follow-up for the out-of-catalog supply-chain hunt. Analyst-authored SPL still required.',
    draft_summary:
      'Supplier security liaison · CI/CD build-server scope · review-only hunt plan attached · no SPL auto-execution.',
    hil_required: true,
    insert_after_step_id: 'rag',
    simulated_result: 'Supplier coordination follow-up recorded for analyst review (simulated).',
    verify_message: 'Follow-up coordination verified against hunt evidence package (simulated).',
  },
};

export function isPriorityLegacyDemoScenario(
  scenarioId: string | null | undefined,
): scenarioId is PriorityLegacyDemoScenarioId {
  return PRIORITY_LEGACY_DEMO_SCENARIOS.includes(scenarioId as PriorityLegacyDemoScenarioId);
}

export function createLegacyDemoCoordinationAction(
  scenarioId: PriorityLegacyDemoScenarioId,
): LegacyDemoCoordinationAction {
  const template = SCENARIO_COORDINATION[scenarioId];
  return {
    action_id: `legacy-coord-${scenarioId}`,
    action_type: template.action_type,
    label: template.label,
    scenario_id: scenarioId,
    phase_step_id: LEGACY_COORDINATION_STEP_ID,
    status: 'pending',
    hil_required: template.hil_required,
    available: false,
    description: template.description,
    draft_summary: template.draft_summary,
    result_message: null,
  };
}

export function injectLegacyCoordinationStep(
  steps: InvestigationProgressStep[],
  scenarioId: string | null | undefined,
): { steps: InvestigationProgressStep[]; action: LegacyDemoCoordinationAction | null } {
  if (!isPriorityLegacyDemoScenario(scenarioId)) {
    return { steps, action: null };
  }
  const template = SCENARIO_COORDINATION[scenarioId];
  const anchorIndex = steps.findIndex((step) => step.id === template.insert_after_step_id);
  if (anchorIndex < 0) {
    return { steps, action: null };
  }
  const coordinationStep: InvestigationProgressStep = {
    id: LEGACY_COORDINATION_STEP_ID,
    label: template.label,
    description: template.description,
    durationMs: 0,
    activity: ['Awaiting analyst coordination decision…'],
  };
  const nextSteps = [...steps];
  nextSteps.splice(anchorIndex + 1, 0, coordinationStep);
  return {
    steps: nextSteps,
    action: createLegacyDemoCoordinationAction(scenarioId),
  };
}

export function coordinationActionForScenario(
  scenarioId: string | null | undefined,
): LegacyDemoCoordinationAction | null {
  if (!isPriorityLegacyDemoScenario(scenarioId)) return null;
  return createLegacyDemoCoordinationAction(scenarioId);
}

export function markCoordinationWaiting(action: LegacyDemoCoordinationAction): LegacyDemoCoordinationAction {
  return {
    ...action,
    status: 'waiting_for_analyst',
    available: true,
    result_message: null,
  };
}

export function canSkipCoordinationAction(action: LegacyDemoCoordinationAction): boolean {
  return !action.hil_required;
}

export function confirmLegacyDemoCoordinationAction(
  action: LegacyDemoCoordinationAction,
): LegacyDemoCoordinationAction {
  const template = SCENARIO_COORDINATION[action.scenario_id];
  return {
    ...action,
    status: 'verifying',
    available: false,
    result_message: template.simulated_result,
  };
}

export function completeLegacyDemoCoordinationVerification(
  action: LegacyDemoCoordinationAction,
): LegacyDemoCoordinationAction {
  const template = SCENARIO_COORDINATION[action.scenario_id];
  return {
    ...action,
    status: 'completed',
    available: false,
    result_message: template.verify_message,
  };
}

export function skipLegacyDemoCoordinationAction(
  action: LegacyDemoCoordinationAction,
): LegacyDemoCoordinationAction | null {
  if (action.hil_required) return null;
  return {
    ...action,
    status: 'skipped',
    available: false,
    result_message: 'Coordination skipped by analyst.',
  };
}

export function coordinationBlocksProgress(action: LegacyDemoCoordinationAction | null | undefined): boolean {
  if (!action) return false;
  return action.status === 'waiting_for_analyst' || action.status === 'verifying';
}
