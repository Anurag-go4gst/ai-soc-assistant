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

  it('does not label guidance as Investigation plan when canonical approval card owns the plan', () => {
    render(
      <AnalystResponseCard
        response={{
          response_profile: 'full',
          direct_answer_summary: 'Review the pending investigation plan.',
          recommended_actions: [
            'P1 — Correlate failed then successful SSH',
            'P2 — Confirm admin session source',
          ],
        }}
        canonicalInvestigationPlanElsewhere
      />,
    );
    expect(screen.queryByText('Investigation plan')).not.toBeInTheDocument();
    expect(screen.getByText('Recommended checks')).toBeInTheDocument();
  });

  it('renders utility synthesis as summary, what it does, SPL, mappings, expected result', () => {
    const { container } = render(
      <AnalystResponseCard
        response={{
          response_profile: 'spl_only',
          finding_title: 'Review-only SPL draft — not performed',
          direct_answer_summary: 'Review-only authentication sequence query.',
          initial_assessment: [
            'Finds a failure burst of more than 20 failed authentication attempts within 15 minutes.',
            'Establishes that qualifying failure burst first, then a later successful login within 10 minutes.',
          ],
          one_sentence_finding: 'Each row represents a qualifying burst and a later successful login.',
          draft_spl_code: 'search index=wineventlog earliest=-24h | stats count',
          spl_draft_preview: {
            draft_spl: 'search index=wineventlog earliest=-24h | stats count',
            draft_status: 'review_only',
            draft_source: 'compiler',
            detection_family: 'user_bound_spl_authoring',
            assumptions: [
              '`<your_index>` must be replaced with the approved authentication index.',
              'Authentication data is expected in sourcetype `pgcil:auth`.',
              'Authentication failures use EventCode 4625.',
            ],
            required_source_fields: [],
            source_profile_missing: false,
            governed_template_missing: true,
            validator_status: 'review_required',
            review_required: true,
            execution_enabled: false,
            warning: 'Review only — not executed.',
            not_catalog_approved_notice: 'Review-only draft.',
          },
          investigation_steps: [],
          recommended_actions: [],
          mitre_mappings: [],
        }}
      />,
    );
    const text = container.textContent ?? '';
    expect(text).toContain('Review-only SPL draft — not executed');
    expect(text).not.toContain('not performed');
    expect(text).toContain('Review-only authentication sequence query.');
    expect(text).toContain('failure burst');
    expect(text).toContain('approved authentication index');
    expect(text).toContain('pgcil:auth');
    expect(text).toContain('EventCode 4625');
    expect(text).toContain('No query was executed.');
    expect(text).not.toContain('Investigation steps');
    expect(text).not.toContain('MITRE');
    expect(text).not.toContain('•');
    expect(text).not.toContain('\\<');
    expect(text).not.toContain('\\_');
    expect(text).not.toContain('\\:');
    expect(text).toContain('<your_index>');
    expect(text).toContain('pgcil:auth');
    expect([...container.querySelectorAll('h3, h4')].map((el) => el.textContent)).toEqual([
      'Review-only SPL draft — not executed',
      'What this query does',
      'SPL',
      'Mappings / assumptions',
      'Expected result',
    ]);
    const splBlock = container.querySelector('pre')?.textContent ?? '';
    expect(splBlock).toContain('search index=wineventlog');
    expect(container.querySelector('ol')).toBeNull();
  });
});
