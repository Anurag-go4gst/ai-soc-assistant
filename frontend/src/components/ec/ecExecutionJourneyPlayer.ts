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

const LLM_ACTIVITY = [
  'Loading captured Foundation-sec instruct signal…',
  'Applying severity, MITRE, and SPL governance overrides…',
  'Final synthesis disabled for Experience Center',
];

function archStage(
  id: string,
  title: string,
  semantic_type: EcExecutionStage['semantic_type'],
  duration_ms_hint: number,
  activity?: string[],
): EcExecutionStage {
  return {
    id,
    title,
    semantic_type,
    duration_ms_hint,
    activity,
    provenance: 'experience_center_fixture',
  };
}

export function genericFallbackJourney(): EcExecutionJourney {
  return {
    journey_id: 'ec-fallback-initial',
    kind: 'initial',
    header: 'Running governed investigation pipeline',
    stages: [
      archStage('understand', 'Decomposing the investigation question', 'understand', FALLBACK_DURATION.understand, [
        'Reading the question…',
        'Identifying entities and requested outcome…',
      ]),
      archStage('resource-plan', 'Planning evidence and resources', 'plan', FALLBACK_DURATION.plan, [
        'Mapping evidence needs…',
        'Locking the investigation plan…',
      ]),
      archStage('mcp-select', 'Selecting governed MCP tools', 'plan', FALLBACK_DURATION.plan, [
        'Selecting splunk_run_query when Splunk evidence is required…',
        'Applying safety gates…',
      ]),
      archStage('mcp-connect', 'Connecting to Splunk MCP', 'plan', 1400, [
        'Resolving splunk server from MCP registry…',
        'tools/list → splunk_run_query allowed for this skill ✓',
      ]),
      archStage('evidence', 'Reusing or retrieving governed evidence', 'gather', FALLBACK_DURATION.gather, [
        'Retrieving configured evidence…',
        'Replaying approved saved search when suitable…',
      ]),
      archStage('spl-validate', 'Validating governed SPL', 'evaluate', FALLBACK_DURATION.evaluate, [
        'Running deterministic SPL validator…',
        'Normalizing time range and index constraints…',
      ]),
      archStage('mcp-execute', 'Executing governed MCP search', 'gather', 1800, [
        'Submitting governed search job…',
        'Polling job dispatchState=DONE…',
        'Fetching governed result rows…',
      ]),
      archStage('correlate', 'Correlating evidence sources', 'correlate', FALLBACK_DURATION.correlate, [
        'Aligning entities and timelines…',
        'Separating confirmed vs unconfirmed claims…',
      ]),
      archStage('llm-advisory', 'Applying governed LLM advisory', 'evaluate', 1500, LLM_ACTIVITY),
      archStage('outcome', 'Building InvestigationOutcome and next options', 'outcome', FALLBACK_DURATION.outcome, [
        'Evaluating uncertainty…',
        'Packaging the outcome and next steps…',
      ]),
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

function jitteredPlaybackMs(ms: number): number {
  if (ms <= 0) return 0;
  const spread = ms * 0.2;
  return Math.max(0, Math.round(ms + (Math.random() * 2 - 1) * spread));
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
  options?: { isStale?: () => boolean; skipRemaining?: () => boolean },
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
    await delay(options?.skipRemaining?.() ? 0 : jitteredPlaybackMs(durationFor(stage)));
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
