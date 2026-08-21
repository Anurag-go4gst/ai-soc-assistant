import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { InvestigationOutcomeCard } from '@/components/InvestigationOutcomeCard';
import type { InvestigationOutcomeEnvelope } from '@/types/api';

afterEach(() => cleanup());

function outcome(overrides: Partial<InvestigationOutcomeEnvelope> = {}): InvestigationOutcomeEnvelope {
  return {
    schema_version: 'investigation_outcome_v2',
    investigation_status: 'blocked',
    disposition: 'inconclusive',
    findings: [],
    supported_hypotheses: [],
    unconfirmed_hypotheses: ['Possible credential stuffing'],
    evidence_refs: [],
    missing_evidence: ['session corroboration'],
    limitations: ['Splunk connector unavailable'],
    recommended_next_action: 'restore connector readiness',
    remediation_offer_required: true,
    recommended_actions: [],
    llm_proposal_accepted: false,
    ...overrides,
  };
}

describe('InvestigationOutcomeCard', () => {
  it('keeps operational status separate from security disposition', () => {
    render(<InvestigationOutcomeCard outcome={outcome()} />);
    expect(screen.getByText('status: blocked')).toBeInTheDocument();
    expect(screen.getByText('disposition: inconclusive')).toBeInTheDocument();
    expect(screen.getByText('Not confirmed')).toBeInTheDocument();
    expect(screen.getByText('Possible credential stuffing')).toBeInTheDocument();
    expect(screen.getByText('Splunk connector unavailable')).toBeInTheDocument();
  });

  it('renders evidence-bound empty completion copy without a dash finding', () => {
    const { container } = render(
      <InvestigationOutcomeCard
        outcome={outcome({
          investigation_status: 'completed',
          unconfirmed_hypotheses: [],
          remediation_offer_required: false,
        })}
        progress={[
          {
            step_id: 'auth',
            purpose: 'authentication_correlation',
            status: 'executed',
            source: 'splunk_search',
            evidence_summary: '',
            evidence_refs: [],
          },
        ]}
      />,
    );
    expect(screen.getByText('No matching governed evidence was found for this step.')).toBeInTheDocument();
    expect(screen.getByText('No matching governed evidence was found for the approved scope.')).toBeInTheDocument();
    expect(container.textContent).not.toContain('Finding: -');
  });

  it('offers a separate remediation-plan transition without executing an action', () => {
    render(<InvestigationOutcomeCard outcome={outcome()} />);
    expect(screen.getByText('Create remediation plan?')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Yes' }));
    expect(screen.getByText('Remediation planning requires a separately reviewed and approved plan.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Yes' })).not.toBeInTheDocument();
  });

  it('omits the remediation ask when the governed outcome says it was already requested', () => {
    render(<InvestigationOutcomeCard outcome={outcome({ remediation_offer_required: false })} />);
    expect(screen.queryByText('Create remediation plan?')).not.toBeInTheDocument();
  });
});
