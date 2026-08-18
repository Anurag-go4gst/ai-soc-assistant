import type { InvestigationProgressState } from '@/lib/investigationProgress';
import type { ExperienceExecutionProgressView, ExperienceExecutionStageStatus } from '@/lib/experienceCenterExecution';
import {
  LEGACY_COORDINATION_STEP_ID,
  type LegacyDemoCoordinationAction,
} from '@/lib/legacyDemoCoordination';

function mapCoordinationStepStatus(
  stepId: string,
  baseStatus: ExperienceExecutionStageStatus | undefined,
  action: LegacyDemoCoordinationAction | null | undefined,
): ExperienceExecutionStageStatus | undefined {
  if (!action || stepId !== action.phase_step_id) return baseStatus;
  switch (action.status) {
    case 'waiting_for_analyst':
      return 'waiting';
    case 'verifying':
    case 'sending':
      return 'verifying';
    case 'completed':
      return 'completed';
    case 'skipped':
      return 'skipped';
    case 'failed':
    case 'rejected':
    case 'configuration_required':
      return 'failed';
    default:
      return baseStatus;
  }
}

export function investigationProgressToExperienceView(
  state: InvestigationProgressState,
  demoMode: boolean,
  coordinationAction?: LegacyDemoCoordinationAction | null,
): ExperienceExecutionProgressView {
  const stepStatuses: Record<string, ExperienceExecutionStageStatus> = {};
  for (const step of state.steps) {
    const base = state.stepStatuses?.[step.id] as ExperienceExecutionStageStatus | undefined;
    const mapped = mapCoordinationStepStatus(step.id, base, coordinationAction);
    if (mapped) stepStatuses[step.id] = mapped;
  }
  if (coordinationAction?.status === 'waiting_for_analyst') {
    stepStatuses[LEGACY_COORDINATION_STEP_ID] = 'waiting';
  }

  return {
    steps: state.steps.map((step) => ({
      id: step.id,
      label: step.label,
      description: step.description,
      durationMs: step.durationMs,
      activity: step.activity,
    })),
    activeStepIndex: state.activeStepIndex,
    completedStepIds: [...state.completedStepIds],
    stepStatuses,
    stepDisplayText: state.stepDisplayText,
    demoMode,
    coordinationAction: coordinationAction
      ? {
          action_id: coordinationAction.action_id,
          action_type: coordinationAction.action_type,
          label: coordinationAction.label,
          status: coordinationAction.status,
          delivery_mode: coordinationAction.delivery_mode,
          hil_required: coordinationAction.hil_required,
          available: coordinationAction.available,
          description: coordinationAction.description,
          draft_summary: coordinationAction.draft_summary,
          result_message: coordinationAction.result_message,
          logical_recipient: coordinationAction.logical_recipient,
        }
      : null,
    error: state.error,
    llmWarning: state.llmWarning,
    finalization: state.finalization
      ? {
          phase: state.finalization.phase,
          statusLine: state.finalization.statusLine,
          mcpDetail: state.finalization.mcpDetail,
          showRetryHint: state.finalization.showRetryHint,
        }
      : null,
  };
}
