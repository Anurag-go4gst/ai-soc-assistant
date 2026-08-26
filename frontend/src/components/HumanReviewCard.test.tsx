import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HumanReviewCard } from '@/components/HumanReviewCard';
import type { HumanReviewEnvelope } from '@/types/api';

afterEach(() => cleanup());

function review(overrides: Partial<HumanReviewEnvelope> = {}): HumanReviewEnvelope {
  return {
    required: true,
    review_type: 'spl_execution_confirmation',
    reason: 'per_call_confirmation',
    reviewer_role: 'analyst',
    allowed_actions: ['confirm_execution', 'provide_updated_spl'],
    safe_message_for_user: 'Confirm this search before it may approach the MCP gate.',
    proposed_normalized_spl: 'search index=auth earliest=-24h | stats count by user',
    ...overrides,
  };
}

describe('HumanReviewCard execution HIL', () => {
  it('keeps execution confirmation separate from write Approve/Edit/Cancel', () => {
    render(
      <MemoryRouter>
        <HumanReviewCard
          review={review()}
          onExecutionReview={vi.fn()}
          execution={{ status: 'skipped' } as never}
          runContract={{ mcp_allowed: false, execution_authorized: false }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Confirm execution/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit updated SPL/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reject/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Approve$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /run/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Execution posture/i)).toBeInTheDocument();
  });

  it('confirm submits execution_review_action confirm, not a write approval', () => {
    const onExecutionReview = vi.fn();
    render(
      <MemoryRouter>
        <HumanReviewCard review={review()} onExecutionReview={onExecutionReview} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Confirm execution/i }));
    expect(onExecutionReview).toHaveBeenCalledWith(
      { execution_review_action: 'confirm' },
      'Confirm proposed SPL execution',
    );
  });
});
