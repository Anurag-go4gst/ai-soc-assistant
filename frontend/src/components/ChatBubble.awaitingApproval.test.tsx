import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatBubble, type SocChatMessage } from '@/components/ChatBubble';
import type { PlaceholderResponse } from '@/types/api';

function awaitingTrace(overrides: Partial<PlaceholderResponse> = {}): PlaceholderResponse {
  return {
    trace_id: 't1',
    user_query: 'failed SSH then success',
    selected_skill: 'guided_investigation',
    message: 'Investigation plan ready. Review the scope, then Approve, Edit, or Cancel.',
    investigation_approval: {
      status: 'awaiting_approval',
      handoff_id: 'inv-1',
      handoff_version: 1,
      allowed_actions: ['run', 'edit', 'cancel'],
      plan_summary: {
        what_will_be_checked: ['Failed and successful SSH authentication'],
        why_it_matters: 'Determine whether unauthorized access is likely.',
        scope_and_time: ['bounded timeline around the sequence'],
        resources_and_capabilities: ['read-only Splunk search'],
      },
      validated_plan: {},
      safe_message: 'Investigation plan ready. Review the scope, then Approve, Edit, or Cancel.',
      revalidation_warnings: [],
      plan_version: 1,
    },
    planning_outcome: {
      status: 'awaiting_investigation_plan',
      user_message: 'Investigation plan is ready for analyst review.',
    },
    // Stale post-execution fields that must NOT render while awaiting approval.
    investigation_outcome: {
      investigation_status: 'inconclusive',
      disposition: 'inconclusive',
      conclusion: 'Should not render',
    } as unknown as PlaceholderResponse['investigation_outcome'],
    analyst_response: {
      direct_answer_summary: 'Should not render analyst steps',
      investigation_steps: ['Step that must stay hidden'],
    } as unknown as PlaceholderResponse['analyst_response'],
    ...overrides,
  } as PlaceholderResponse;
}

describe('ChatBubble awaiting investigation approval', () => {
  it('renders plan approval only — hides outcome and analyst steps', () => {
    const message: SocChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: 'plan',
      displayStage: 'complete',
      trace: awaitingTrace(),
    };
    render(
      <ChatBubble
        message={message}
        onInvestigationReview={() => undefined}
      />,
    );
    expect(screen.getAllByText(/Investigation plan ready/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /^Approve$/i })).toBeTruthy();
    expect(screen.queryByText('Should not render')).toBeNull();
    expect(screen.queryByText('Should not render analyst steps')).toBeNull();
    expect(screen.queryByText('Step that must stay hidden')).toBeNull();
    expect(screen.queryByText(/Technical evidence path/i)).toBeNull();
  });
});
