import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  genericFallbackJourney,
  playEcExecutionJourney,
  resolveJourney,
  viewFromJourney,
} from '@/components/ec/ecExecutionJourneyPlayer';
import type { EcExecutionJourney } from '@/components/ec/types';
import type { ExperienceExecutionProgressView } from '@/lib/experienceCenterExecution';

afterEach(() => {
  vi.useRealTimers();
});

function shortJourney(overrides: Partial<EcExecutionJourney> = {}): EcExecutionJourney {
  return {
    journey_id: 'test-journey',
    kind: 'initial',
    header: 'Running governed investigation pipeline',
    stages: [
      {
        id: 'understand',
        title: 'Understanding the question',
        activity: ['Reading the question…'],
        semantic_type: 'understand',
        duration_ms_hint: 20,
      },
      {
        id: 'gather',
        title: 'Gathering evidence',
        activity: ['Retrieving configured evidence…'],
        semantic_type: 'gather',
        duration_ms_hint: 20,
      },
      {
        id: 'outcome',
        title: 'Building InvestigationOutcome',
        semantic_type: 'outcome',
        duration_ms_hint: 20,
      },
    ],
    ...overrides,
  };
}

describe('ecExecutionJourneyPlayer', () => {
  it('plays stages in order and completes n/N', async () => {
    vi.useFakeTimers();
    const updates: ExperienceExecutionProgressView[] = [];
    const done = playEcExecutionJourney(shortJourney(), (view) => {
      updates.push(view);
    });
    await vi.runAllTimersAsync();
    expect(await done).toBe(true);
    expect(updates[0]?.activeStepIndex).toBe(0);
    expect(updates[0]?.completedStepIds).toEqual([]);
    expect(updates.at(-1)?.activeStepIndex).toBe(3);
    expect(updates.at(-1)?.completedStepIds).toEqual(['understand', 'gather', 'outcome']);
    expect(updates.some((view) => view.steps.map((step) => step.label).join('|') === 'Understanding the question|Gathering evidence|Building InvestigationOutcome')).toBe(true);
  });

  it('pauses on WAITING without completing later stages', async () => {
    vi.useFakeTimers();
    const updates: ExperienceExecutionProgressView[] = [];
    const journey = shortJourney({
      stages: [
        {
          id: 'prepare',
          title: 'Preparing email',
          semantic_type: 'plan',
          duration_ms_hint: 10,
        },
        {
          id: 'wait-hil',
          title: 'Waiting for approval',
          semantic_type: 'hil',
          duration_ms_hint: 9999,
        },
        {
          id: 'execute',
          title: 'Executing',
          semantic_type: 'execute',
          duration_ms_hint: 10,
        },
      ],
    });
    const done = playEcExecutionJourney(journey, (view) => {
      updates.push(view);
    });
    await vi.runAllTimersAsync();
    expect(await done).toBe(true);
    const last = updates.at(-1);
    expect(last?.stepStatuses?.['wait-hil']).toBe('waiting');
    expect(last?.completedStepIds).toEqual(['prepare']);
    expect(last?.activeStepIndex).toBe(1);
  });

  it('cancels stale playback so a later epoch cannot finish', async () => {
    vi.useFakeTimers();
    const updates: ExperienceExecutionProgressView[] = [];
    let stale = false;
    const done = playEcExecutionJourney(shortJourney(), (view) => {
      updates.push(view);
    }, { isStale: () => stale });
    stale = true;
    await vi.runAllTimersAsync();
    expect(await done).toBe(false);
    expect(updates.at(-1)?.completedStepIds ?? []).not.toContain('outcome');
  });

  it('uses a generic fallback without dishonest TLS/bearer copy', () => {
    const fallback = resolveJourney(null);
    expect(fallback.stages.map((stage) => stage.id)).toEqual([
      'understand',
      'plan',
      'gather',
      'correlate',
      'outcome',
      'next',
    ]);
    const blob = JSON.stringify(genericFallbackJourney());
    expect(blob).not.toMatch(/TLS handshake|bearer auth/i);
    const view = viewFromJourney(fallback, { activeStepIndex: 0, completedStepIds: [] });
    expect(view.header).toBe('Running governed investigation pipeline');
    expect(view.demoMode).toBe(true);
  });
});
