import { delay, type InvestigationProgressState, type InvestigationProgressStep, type InvestigationProgressStepStatus } from '@/lib/investigationProgress';
import {
  LEGACY_COORDINATION_STEP_ID,
  completeLegacyDemoCoordinationVerification,
  confirmLegacyDemoCoordinationAction,
  markCoordinationWaiting,
  skipLegacyDemoCoordinationAction,
  type LegacyDemoCoordinationAction,
} from '@/lib/legacyDemoCoordination';

export interface LegacyDemoCoordinationPlayback {
  progress: InvestigationProgressState;
  action: LegacyDemoCoordinationAction | null;
}

export interface LegacyDemoCoordinationPlayerOptions {
  coordinationAction: LegacyDemoCoordinationAction | null;
  waitForAnalyst: () => Promise<'confirm' | 'skip'>;
  skipCompletion?: boolean;
  onCoordinationUpdate?: (action: LegacyDemoCoordinationAction) => void;
  isStale?: () => boolean;
}

function initialStatuses(steps: InvestigationProgressStep[]): Record<string, InvestigationProgressStepStatus> {
  return Object.fromEntries(steps.map((step) => [step.id, 'pending' as InvestigationProgressStepStatus]));
}

function snapshot(
  steps: InvestigationProgressStep[],
  activeStepIndex: number,
  completedStepIds: string[],
  stepStatuses: Record<string, InvestigationProgressStepStatus>,
  stepDisplayText?: Record<string, string>,
  finalization?: InvestigationProgressState['finalization'],
): InvestigationProgressState {
  return {
    steps,
    activeStepIndex,
    completedStepIds: [...completedStepIds],
    stepStatuses: { ...stepStatuses },
    stepDisplayText: stepDisplayText ? { ...stepDisplayText } : undefined,
    finalization,
  };
}

export async function playLegacyDemoInvestigationWithCoordination(
  steps: InvestigationProgressStep[],
  onUpdate: (playback: LegacyDemoCoordinationPlayback) => void,
  options: LegacyDemoCoordinationPlayerOptions,
): Promise<LegacyDemoCoordinationAction | null> {
  const completedStepIds: string[] = [];
  const stepStatuses = initialStatuses(steps);
  const stepDisplayText: Record<string, string> = {};
  let action = options.coordinationAction;

  const publish = (activeStepIndex: number, finalization?: InvestigationProgressState['finalization']) => {
    onUpdate({
      progress: snapshot(steps, activeStepIndex, completedStepIds, stepStatuses, stepDisplayText, finalization),
      action,
    });
  };

  for (let index = 0; index < steps.length; index += 1) {
    if (options.isStale?.()) return action;
    const step = steps[index];
    if (step.id === LEGACY_COORDINATION_STEP_ID && action) {
      stepStatuses[step.id] = 'active';
      publish(index);
      await delay(350);
      if (options.isStale?.()) return action;
      action = markCoordinationWaiting(action);
      stepStatuses[step.id] = 'active';
      stepDisplayText[step.id] = 'Waiting for analyst coordination decision…';
      options.onCoordinationUpdate?.(action);
      publish(index);

      let decision = await options.waitForAnalyst();
      if (options.isStale?.()) return action;
      if (decision === 'skip') {
        const skipped = skipLegacyDemoCoordinationAction(action);
        if (!skipped) {
          decision = await options.waitForAnalyst();
          if (options.isStale?.()) return action;
        } else {
          action = skipped;
          stepStatuses[step.id] = 'skipped';
          stepDisplayText[step.id] = action.result_message ?? 'Coordination skipped.';
          completedStepIds.push(step.id);
          options.onCoordinationUpdate?.(action);
          publish(index + 1);
          continue;
        }
      }

      if (decision === 'confirm') {
        action = confirmLegacyDemoCoordinationAction(action);
        stepStatuses[step.id] = 'active';
        stepDisplayText[step.id] = action.result_message ?? 'Submitting coordination request…';
        options.onCoordinationUpdate?.(action);
        publish(index);
        await delay(700);
        if (options.isStale?.()) return action;

        action = completeLegacyDemoCoordinationVerification(action);
        stepStatuses[step.id] = 'completed';
        stepDisplayText[step.id] = action.result_message ?? 'Coordination verified.';
        completedStepIds.push(step.id);
        options.onCoordinationUpdate?.(action);
        publish(index + 1);
      }
      continue;
    }

    stepStatuses[step.id] = 'active';
    publish(index);
    await delay(step.durationMs);
    if (options.isStale?.()) return action;
    stepStatuses[step.id] = 'completed';
    completedStepIds.push(step.id);
    publish(index + 1);
  }

  if (options.skipCompletion) {
    publish(steps.length - 1, {
      phase: 'finalizing',
      statusLine: 'Generating final answer…',
      timeoutTier: 0,
      partialFallback: false,
      showRetryHint: false,
    });
    return action;
  }

  publish(steps.length);
  return action;
}
