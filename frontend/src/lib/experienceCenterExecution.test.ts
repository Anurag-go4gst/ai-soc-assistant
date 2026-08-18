import { describe, expect, it } from 'vitest';
import {
  defaultExperienceExecutionHeader,
  experienceExecutionCounter,
  type ExperienceExecutionProgressView,
} from '@/lib/experienceCenterExecution';

function view(partial: Partial<ExperienceExecutionProgressView> = {}): ExperienceExecutionProgressView {
  return {
    steps: [
      { id: 'understand', label: 'Understanding query', description: 'Parse intent.', durationMs: 700 },
      { id: 'gather', label: 'Gathering evidence', description: 'Collect evidence.', durationMs: 800 },
    ],
    activeStepIndex: 0,
    completedStepIds: [],
    ...partial,
  };
}

describe('experienceCenterExecution headers and counter', () => {
  it('defaults to the legacy running header', () => {
    expect(defaultExperienceExecutionHeader(view())).toBe('Running governed investigation pipeline');
  });

  it('uses waiting and verifying headers from stage status', () => {
    expect(
      defaultExperienceExecutionHeader(view({ stepStatuses: { gather: 'waiting' }, activeStepIndex: 1 })),
    ).toBe('Waiting');
    expect(
      defaultExperienceExecutionHeader(view({ stepStatuses: { gather: 'verifying' }, activeStepIndex: 1 })),
    ).toBe('Verifying');
  });

  it('keeps the legacy error and complete headers', () => {
    expect(defaultExperienceExecutionHeader(view({ error: { message: 'failed' } }))).toBe(
      'Investigation could not finish',
    );
    expect(defaultExperienceExecutionHeader(view({ activeStepIndex: 2, completedStepIds: ['understand', 'gather'] }))).toBe(
      'Investigation pipeline complete',
    );
  });

  it('exposes n/N while a stage is active', () => {
    expect(experienceExecutionCounter(view({ activeStepIndex: 0 }))).toEqual({ current: 1, total: 2 });
    expect(experienceExecutionCounter(view({ activeStepIndex: 2, completedStepIds: ['understand', 'gather'] }))).toBeNull();
  });
});
