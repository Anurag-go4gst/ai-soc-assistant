import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { InvestigationPlanApprovalCard } from '@/components/InvestigationPlanApprovalCard';
import type { InvestigationApprovalState } from '@/types/api';

afterEach(() => cleanup());

function approval(overrides: Partial<InvestigationApprovalState> = {}): InvestigationApprovalState {
  return {
    status: 'awaiting_approval',
    handoff_id: 'inv-1',
    handoff_version: 1,
    allowed_actions: ['run', 'edit', 'cancel'],
    plan_summary: {
      what_will_be_checked: ['Failed logins for alice'],
      why_it_matters: 'Confirm whether the spike is malicious.',
      scope_and_time: ['last 24 hours'],
      resources_and_capabilities: ['read-only Splunk search'],
    },
    validated_plan: {},
    safe_message: 'Investigation plan ready. Review it, then Approve, Edit, or Cancel.',
    revalidation_warnings: [],
    ...overrides,
  };
}

describe('InvestigationPlanApprovalCard vocabulary', () => {
  it('exposes Approve / Edit / Cancel and never a Run control', () => {
    const onReview = vi.fn();
    render(
      <InvestigationPlanApprovalCard
        approval={approval()}
        originalQuery="investigate alice"
        onReview={onReview}
      />,
    );
    expect(screen.getByRole('button', { name: /^Approve$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Edit$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Cancel$/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /run/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/run investigation/i)).not.toBeInTheDocument();
  });

  it('sends the governed run action when Approve is clicked', () => {
    const onReview = vi.fn();
    render(
      <InvestigationPlanApprovalCard
        approval={approval()}
        originalQuery="investigate alice"
        onReview={onReview}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /^Approve$/i }));
    expect(onReview).toHaveBeenCalledWith(
      expect.objectContaining({ investigation_review_action: 'run' }),
      'Approve investigation plan',
      'investigate alice',
    );
  });
});
