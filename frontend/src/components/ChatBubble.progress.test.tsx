import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ChatBubble } from '@/components/ChatBubble';
import type { InvestigationProgressState } from '@/lib/investigationProgress';

afterEach(() => cleanup());

const progress: InvestigationProgressState = {
  steps: [
    {
      id: 'query',
      label: 'Understanding query',
      description: 'Parsing analyst intent.',
      durationMs: 700,
      activity: ['Normalizing query…'],
    },
  ],
  activeStepIndex: 0,
  completedStepIds: [],
};

describe('ChatBubble progress shell', () => {
  it('uses the shared Experience Center shell when demoMode is true', () => {
    render(
      <ChatBubble
        message={{
          id: 'demo-progress',
          role: 'assistant',
          content: 'Running',
          displayStage: 'progress',
          progressDemoMode: true,
          investigationProgress: progress,
        }}
      />,
    );
    expect(screen.getByTestId('experience-execution-progress-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('investigation-progress-panel')).not.toBeInTheDocument();
    expect(screen.getByText('Experience Center')).toBeInTheDocument();
  });

  it('keeps the live investigation panel when demoMode is false', () => {
    render(
      <ChatBubble
        message={{
          id: 'live-progress',
          role: 'assistant',
          content: 'Running',
          displayStage: 'progress',
          progressDemoMode: false,
          investigationProgress: progress,
        }}
      />,
    );
    expect(screen.getByTestId('investigation-progress-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('experience-execution-progress-panel')).not.toBeInTheDocument();
    expect(screen.queryByText('Experience Center')).not.toBeInTheDocument();
  });
});
