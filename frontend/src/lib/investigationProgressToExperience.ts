import type { InvestigationProgressState } from '@/lib/investigationProgress';
import type { ExperienceExecutionProgressView } from '@/lib/experienceCenterExecution';

export function investigationProgressToExperienceView(
  state: InvestigationProgressState,
  demoMode: boolean,
): ExperienceExecutionProgressView {
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
    stepStatuses: state.stepStatuses,
    stepDisplayText: state.stepDisplayText,
    demoMode,
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
