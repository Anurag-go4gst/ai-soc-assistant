import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { RemediationPlanApprovalCard } from '@/components/RemediationPlanApprovalCard';
import type { RemediationApprovalState } from '@/types/api';

afterEach(() => cleanup());

function approval(overrides: Partial<RemediationApprovalState> = {}): RemediationApprovalState {
  return {
    status: 'awaiting_approval',
    allowed_actions: ['approve', 'edit', 'cancel'],
    plan_summary: {
      what_will_change: ['Block source IP'],
      why_it_matters: 'Contain confirmed suspicious activity.',
      what_stays_manual: [],
      how_it_is_verified: ['Re-query the blocking control'],
    },
    validated_plan: {
      steps: [
        {
          step_id: 'rem.01.firewall_block',
          capability_id: 'firewall_block',
          description: 'Block source IP',
          execution_mode: 'execute',
          availability: 'available',
          reversible: true,
          verification: 'Re-query the blocking control',
        },
      ],
      remediation_objective: 'Contain confirmed suspicious activity.',
      manual_only_steps: [],
      plan_source: 'deterministic',
      execution_authorized: false,
    },
    safe_message: 'Remediation plan ready. Review what changes, then Approve, Edit, or Cancel.',
    revalidation_warnings: [],
    execution_result: null,
    ...overrides,
  };
}

describe('RemediationPlanApprovalCard vocabulary', () => {
  it('exposes Approve / Edit / Cancel and never a Run control', () => {
    render(
      <RemediationPlanApprovalCard
        approval={approval()}
        originalQuery="investigate alice"
        onReview={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /Approve/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /run/i })).not.toBeInTheDocument();
  });

  it('approve does not claim a connector was called', () => {
    const onReview = vi.fn();
    render(
      <RemediationPlanApprovalCard
        approval={approval()}
        originalQuery="investigate alice"
        onReview={onReview}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Approve/i }));
    expect(onReview).toHaveBeenCalledWith(
      { remediation_review_action: 'approve' },
      'Approve remediation plan',
      'investigate alice',
    );
  });
});
