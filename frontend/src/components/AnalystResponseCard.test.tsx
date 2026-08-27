import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { AnalystResponseCard } from '@/components/AnalystResponseCard';
import type { AnalystResponseEnvelope } from '@/types/api';

afterEach(() => cleanup());

function splUtilityResponse(overrides: Partial<AnalystResponseEnvelope> = {}): AnalystResponseEnvelope {
  return {
    response_profile: 'spl_only',
    direct_answer_summary: 'Review-only SPL for denied firewall traffic.',
    draft_spl_code: 'search index=pgcil_soc sourcetype=cisco:firepower earliest=-24h latest=now | stats count by src_ip | sort - count | head 100',
    limitations: ['- Field mapping for deny action may vary by deployment.', 'Review before execution.'],
    investigation_steps: ['Validate index coverage', 'Confirm deny field semantics'],
    required_evidence: ['- Source profile binding'],
    review_notice: 'Review only — not executed.',
    ...overrides,
  };
}

describe('AnalystResponseCard SPL utility rendering', () => {
  it('does not double-prefix bullet items that already start with a dash', () => {
    const { container } = render(<AnalystResponseCard response={splUtilityResponse()} />);
    expect(container.textContent).not.toContain('- -');
    expect(screen.getByText(/Field mapping for deny action/)).toBeInTheDocument();
    expect(screen.getByText(/Source profile binding/)).toBeInTheDocument();
  });

  it('does not leak svg icon text in phase timeline labels', () => {
    const { container } = render(
      <AnalystResponseCard
        response={splUtilityResponse({
          limitations: ['Governed review-only posture'],
        })}
      />,
    );
    const text = container.textContent ?? '';
    expect(text.toLowerCase().split(/\s+/).filter((token) => token === 'svg')).toHaveLength(0);
  });

  it('CV.SPL.02-class: blocked no-SPL shows non-null reason and no empty code block', () => {
    const { container } = render(
      <AnalystResponseCard
        response={{
          response_profile: 'spl_only',
          direct_answer_summary: 'No governed SPL is available for this ask.',
          spl_code: '   ',
          spl_status_detail: {
            template_status: 'unavailable',
            generation_status: 'blocked',
            reason: 'source_profile_unresolved',
            reason_display: 'Source profile unresolved — SPL withheld.',
            block_reason: 'source_profile_unresolved',
          },
        }}
      />,
    );
    expect(screen.getByText(/Source profile unresolved/i)).toBeInTheDocument();
    expect(container.querySelectorAll('pre').length).toBe(0);
    expect(container.querySelector('code')).toBeNull();
  });
});
