import type { EcExecutionJourney, EcExecutionStage } from '@/components/ec/types';
import type { ExperienceExecutionProgressView, ExperienceExecutionStageStatus } from '@/lib/experienceCenterExecution';

const FALLBACK_DURATION: Record<string, number> = {
  understand: 1200,
  plan: 1200,
  gather: 1800,
  correlate: 1400,
  evaluate: 1400,
  outcome: 1600,
  next: 1000,
  wait: 0,
  hil: 0,
  execute: 1400,
  verify: 1400,
};

export function genericFallbackJourney(): EcExecutionJourney {
  return {
    journey_id: 'ec-fallback-initial',
    kind: 'initial',
    header: 'Running governed investigation pipeline',
    stages: [
      {
        id: 'understand',
        title: 'Understanding the question',
        description: 'Parsing analyst intent and the investigation goal.',
        activity: ['Reading the question…', 'Identifying entities and requested outcome…'],
        semantic_type: 'understand',
        duration_ms_hint: FALLBACK_DURATION.understand,
      },
      {
        id: 'plan',
        title: 'Planning evidence and resources',
        description: 'Selecting governed resources for this investigation.',
        activity: ['Mapping evidence needs…', 'Locking the investigation plan…'],
        semantic_type: 'plan',
        duration_ms_hint: FALLBACK_DURATION.plan,
      },
      {
        id: 'gather',
        title: 'Gathering evidence',
        description: 'Collecting approved evidence for this scenario.',
        activity: ['Retrieving configured evidence…'],
        semantic_type: 'gather',
        duration_ms_hint: FALLBACK_DURATION.gather,
      },
      {
        id: 'correlate',
        title: 'Correlating findings',
        description: 'Comparing evidence sources without inventing facts.',
        activity: ['Aligning entities and timelines…'],
        semantic_type: 'correlate',
        duration_ms_hint: FALLBACK_DURATION.correlate,
      },
      {
        id: 'outcome',
        title: 'Building InvestigationOutcome',
        description: 'Separating confirmed, unconfirmed, and missing evidence.',
        activity: ['Evaluating uncertainty…', 'Packaging the outcome…'],
        semantic_type: 'outcome',
        duration_ms_hint: FALLBACK_DURATION.outcome,
      },
      {
        id: 'next',
        title: 'Preparing next investigation options',
        description: 'Identifying follow-up questions and recommended actions.',
        activity: ['Preparing contextual next steps…'],
        semantic_type: 'next',
        duration_ms_hint: FALLBACK_DURATION.next,
      },
    ],
  };
}

export function resolveJourney(journey: EcExecutionJourney | null | undefined): EcExecutionJourney {
  if (journey?.stages?.length) return journey;
  return genericFallbackJourney();
}

export function durationFor(stage: EcExecutionStage): number {
  if (typeof stage.duration_ms_hint === 'number' && stage.duration_ms_hint >= 0) {
    return stage.duration_ms_hint;
  }
  return FALLBACK_DURATION[stage.semantic_type || 'gather'] ?? 1200;
}

export function viewFromJourney(
  journey: EcExecutionJourney,
  options: {
    activeStepIndex: number;
    completedStepIds: string[];
    stepStatuses?: Record<string, ExperienceExecutionStageStatus>;
    demoMode?: boolean;
  },
): ExperienceExecutionProgressView {
  const resource = journey.stages.find((stage) => stage.resource)?.resource;
  return {
    header: journey.header,
    demoMode: options.demoMode ?? true,
    resourceBadge: resource ? `${resource.system} · ${resource.mode ?? 'read'}` : null,
    steps: journey.stages.map((stage) => ({
      id: stage.id,
      label: stage.title,
      description: stage.description || '',
      durationMs: durationFor(stage),
      activity: stage.activity,
    })),
    activeStepIndex: options.activeStepIndex,
    completedStepIds: options.completedStepIds,
    stepStatuses: options.stepStatuses,
  };
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function playEcExecutionJourney(
  journey: EcExecutionJourney,
  onUpdate: (view: ExperienceExecutionProgressView) => void,
  options?: { isStale?: () => boolean },
): Promise<boolean> {
  const resolved = resolveJourney(journey);
  const completedStepIds: string[] = [];
  const stepStatuses: Record<string, ExperienceExecutionStageStatus> = Object.fromEntries(
    resolved.stages.map((stage) => [stage.id, 'pending' as ExperienceExecutionStageStatus]),
  );
  for (let index = 0; index < resolved.stages.length; index += 1) {
    if (options?.isStale?.()) return false;
    const stage = resolved.stages[index];
    stepStatuses[stage.id] = stage.semantic_type === 'wait' || stage.semantic_type === 'hil' ? 'waiting' : 'active';
    onUpdate(
      viewFromJourney(resolved, {
        activeStepIndex: index,
        completedStepIds: [...completedStepIds],
        stepStatuses: { ...stepStatuses },
      }),
    );
    if (stage.semantic_type === 'wait' || stage.semantic_type === 'hil') {
      return true;
    }
    await delay(durationFor(stage));
    if (options?.isStale?.()) return false;
    stepStatuses[stage.id] = 'completed';
    completedStepIds.push(stage.id);
  }
  if (options?.isStale?.()) return false;
  onUpdate(
    viewFromJourney(resolved, {
      activeStepIndex: resolved.stages.length,
      completedStepIds: [...completedStepIds],
      stepStatuses: { ...stepStatuses },
    }),
  );
  return true;
}
