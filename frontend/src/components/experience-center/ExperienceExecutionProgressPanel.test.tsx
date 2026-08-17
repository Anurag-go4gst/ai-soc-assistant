import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ExperienceExecutionProgressPanel } from '@/components/experience-center/ExperienceExecutionProgressPanel';
import type { ExperienceExecutionProgressView } from '@/lib/experienceCenterExecution';
import { EXPERIENCE_EXECUTION_PANEL_CHROME } from '@/lib/experienceCenterExecution';

afterEach(() => cleanup());

const running: ExperienceExecutionProgressView = {
  steps: [
    {
      id: 'understand',
      label: 'Understanding query',
      description: 'Parsing analyst intent.',
      durationMs: 700,
      activity: ['Normalizing query…'],
    },
    {
      id: 'gather',
      label: 'Replaying governed Splunk search',
      description: 'Replaying a governed search result set.',
      durationMs: 900,
    },
  ],
  activeStepIndex: 0,
  completedStepIds: [],
  demoMode: true,
  resourceBadge: 'Splunk · replay',
};

describe('ExperienceExecutionProgressPanel', () => {
  it('matches legacy chrome: header, Experience Center badge, n/N, and cyan panel', () => {
    const { container } = render(<ExperienceExecutionProgressPanel state={running} />);
    const panel = screen.getByTestId('experience-execution-progress-panel');
    expect(panel).toHaveClass(...EXPERIENCE_EXECUTION_PANEL_CHROME.root.split(' '));
    expect(screen.getByText('Running governed investigation pipeline')).toBeInTheDocument();
    expect(screen.getByText('Experience Center')).toBeInTheDocument();
    expect(screen.getByText('1/2')).toBeInTheDocument();
    expect(screen.getByText('Understanding query')).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/TLS handshake|bearer auth/i);
  });

  it('renders WAITING without a fake progress spinner in the waiting row', () => {
    render(
      <ExperienceExecutionProgressPanel
        state={{
          ...running,
          header: 'Waiting for approval',
          activeStepIndex: 1,
          completedStepIds: ['understand'],
          stepStatuses: { understand: 'completed', gather: 'waiting' },
        }}
      />,
    );
    expect(screen.getByText('Waiting for approval')).toBeInTheDocument();
    const waitingRow = screen.getByText('Replaying governed Splunk search').closest('li');
    expect(waitingRow).toHaveAttribute('data-stage-status', 'waiting');
  });

  it('renders BLOCKED and VERIFYING statuses', () => {
    const { rerender } = render(
      <ExperienceExecutionProgressPanel
        state={{
          ...running,
          stepStatuses: { understand: 'blocked', gather: 'pending' },
        }}
      />,
    );
    expect(screen.getByText('Understanding query').closest('li')).toHaveAttribute('data-stage-status', 'blocked');
    rerender(
      <ExperienceExecutionProgressPanel
        state={{
          ...running,
          header: 'Verifying',
          stepStatuses: { understand: 'completed', gather: 'verifying' },
          activeStepIndex: 1,
          completedStepIds: ['understand'],
        }}
      />,
    );
    expect(screen.getByText('Replaying governed Splunk search').closest('li')).toHaveAttribute(
      'data-stage-status',
      'verifying',
    );
  });

  it('renders the legacy error panel', () => {
    render(
      <ExperienceExecutionProgressPanel
        state={{
          ...running,
          error: { message: 'Investigation interrupted', code: 'ec_playback', recoverable: true },
        }}
        onRetry={() => undefined}
      />,
    );
    expect(screen.getByTestId('investigation-error-panel')).toHaveTextContent('Investigation interrupted');
    expect(screen.getByRole('button', { name: /retry investigation/i })).toBeInTheDocument();
  });
});
