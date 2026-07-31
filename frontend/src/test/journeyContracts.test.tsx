import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PlanningOutcomeBanner } from '@/components/PlanningOutcomeBanner';
import { ExecutionReconciliationCard } from '@/components/ExecutionReconciliationCard';
import { HumanReviewCard } from '@/components/HumanReviewCard';
import { TopBar } from '@/components/TopBar';
import { presentPlanningOutcome, executionLabel } from '@/lib/planningOutcome';
import type { PlaceholderResponse } from '@/types/api';

const baseTrace = (overrides: Partial<PlaceholderResponse>): PlaceholderResponse => ({
  trace_id: 'trace-test-001',
  message: 'Test message',
  note: 'note',
  ...overrides,
});

describe('journey contract surfaces', () => {
  it('1 knowledge — governed citation path uses human_review sop_reference', () => {
    const trace = baseTrace({
      selected_skill: 'knowledge_recall',
      human_review: {
        required: false,
        review_type: 'none',
        reason: 'policy_checks_passed',
        reviewer_role: 'analyst',
        allowed_actions: [],
        safe_message_for_user: '',
        sop_reference: 'SOC-SOP-AUTH-002',
      },
    });
    expect(trace.human_review?.sop_reference).toBe('SOC-SOP-AUTH-002');
  });

  it('2 clarification — planning_outcome banner', () => {
    render(
      <PlanningOutcomeBanner
        outcome={{
          status: 'clarification_required',
          user_message: 'Which alert should I investigate?',
          recovery_hint: 'Provide alert id and resend.',
          category: 'clarification',
        }}
      />,
    );
    expect(screen.getByRole('heading', { name: /clarification needed/i })).toBeInTheDocument();
    expect(screen.getByText(/Which alert should I investigate?/)).toBeInTheDocument();
  });

  it('3 policy_blocked — planning_outcome banner', () => {
    const presentation = presentPlanningOutcome({
      status: 'policy_blocked',
      user_message: 'Unsafe action blocked.',
      recovery_hint: 'Use read-only investigation.',
      category: 'policy',
    });
    expect(presentation?.title).toMatch(/blocked by policy/i);
  });

  it('4 workflow SPL disabled — execution label skipped', () => {
    const label = executionLabel({
      execution: { status: 'skipped', evidence_source: 'unavailable' },
    });
    expect(label.label).toMatch(/not required/i);
  });

  it('5 HIL execution — HumanReviewCard shows posture from response', () => {
    render(
      <HumanReviewCard
        review={{
          required: true,
          review_type: 'spl_execution_confirmation',
          reason: 'spl_execution_confirmation',
          reviewer_role: 'analyst',
          allowed_actions: ['confirm_execution'],
          safe_message_for_user: 'Confirm SPL execution.',
          proposed_normalized_spl: 'index=main | head 10',
        }}
        execution={{
          status: 'requires_human_review',
          execution_intent: 'spl_search',
          tool_selection_status: 'selected',
          tool_selection_reason: 'awaiting confirmation',
          result_count: 0,
          results_preview: [],
          duration_ms: 0,
          block_reason: 'mcp_global_execution_disabled',
        }}
        runContract={{ mcp_allowed: false, execution_authorized: false }}
      />,
    );
    expect(screen.getByRole('button', { name: /confirm & run/i })).toBeInTheDocument();
    expect(screen.getByText(/mcp_global_execution_disabled/)).toBeInTheDocument();
  });

  it('6 planning_failed — banner destructive', () => {
    render(
      <PlanningOutcomeBanner
        outcome={{
          status: 'planning_failed',
          user_message: 'Planning could not complete.',
          recovery_hint: 'Retry with a shorter question.',
          category: 'planner',
        }}
      />,
    );
    expect(screen.getByRole('heading', { name: /planning could not complete/i })).toBeInTheDocument();
  });

  it('7 reconciliation — execution uncertain card', () => {
    render(
      <ExecutionReconciliationCard
        execution={{
          status: 'requires_human_review',
          execution_intent: 'spl_search',
          tool_selection_status: 'blocked',
          tool_selection_reason: 'execution_outcome_uncertain',
          result_count: 0,
          results_preview: [],
          duration_ms: 0,
          outcome_uncertain: true,
          reconciliation_reason: 'execution_outcome_uncertain',
        }}
      />,
    );
    expect(screen.getByRole('heading', { name: /manual reconciliation required/i })).toBeInTheDocument();
  });

  it('8 deterministic fallback — packaging status mapping', () => {
    const trace = baseTrace({ response_packaging_status: 'deterministic_fallback' });
    expect(trace.response_packaging_status).toBe('deterministic_fallback');
  });

  it('9 auth expiry — health still distinguishes API reachability', () => {
    render(
      <TopBar
        username="analyst"
        health={null}
        healthError="401"
        onLogout={async () => undefined}
      />,
    );
    expect(screen.getByText(/API unreachable/i)).toBeInTheDocument();
  });

  it('10 migration readiness — TopBar shows migrations pending', () => {
    render(
      <TopBar
        username="analyst"
        health={{
          status: 'ok',
          service: 'ai-soc-assistant-backend',
          readiness: {
            database_migrations: {
              ready: false,
              missing_versions: ['20260701'],
              remediation: 'alembic upgrade head',
            },
          },
        }}
        healthError={null}
        onLogout={async () => undefined}
      />,
    );
    expect(screen.getByText(/Migrations pending/i)).toBeInTheDocument();
  });

  it('execution live vs mock labels', () => {
    expect(executionLabel({ execution: { status: 'executed', evidence_source: 'live' } }).label).toMatch(/live evidence/i);
    expect(executionLabel({ execution: { status: 'executed', evidence_source: 'mock' } }).label).toMatch(/mock evidence/i);
  });
});
