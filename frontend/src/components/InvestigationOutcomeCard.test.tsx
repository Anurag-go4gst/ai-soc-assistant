import { cleanup, render, screen } from '@testing-library/react';
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

  it('does not crash when backend sends null progress or nullable outcome lists', () => {
    render(
      <InvestigationOutcomeCard
        outcome={outcome({
          investigation_status: 'completed',
          findings: null as unknown as InvestigationOutcomeEnvelope['findings'],
          supported_hypotheses: null as unknown as InvestigationOutcomeEnvelope['supported_hypotheses'],
          unconfirmed_hypotheses: null as unknown as InvestigationOutcomeEnvelope['unconfirmed_hypotheses'],
          missing_evidence: null as unknown as InvestigationOutcomeEnvelope['missing_evidence'],
          limitations: null as unknown as InvestigationOutcomeEnvelope['limitations'],
          remediation_offer_required: false,
        })}
        progress={null}
      />,
    );

    expect(screen.getByText('status: completed')).toBeInTheDocument();
    expect(screen.getByText('No matching governed evidence was found for the approved scope.')).toBeInTheDocument();
  });

  it('does not render a local remediation CTA; backend remediation card is authoritative', () => {
    render(<InvestigationOutcomeCard outcome={outcome()} />);
    expect(screen.queryByText('Create remediation plan?')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Yes' })).not.toBeInTheDocument();
  });

  it('maps workflow BLOCK next action to process language', () => {
    render(
      <InvestigationOutcomeCard
        outcome={outcome({
          recommended_next_action: 'Unable to proceed — additional evidence required',
        })}
      />,
    );
    expect(screen.getByText('Unable to proceed — additional evidence required')).toBeInTheDocument();
    expect(screen.queryByText('BLOCK')).not.toBeInTheDocument();
  });

  it('omits the remediation ask when the governed outcome says it was already requested', () => {
    render(<InvestigationOutcomeCard outcome={outcome({ remediation_offer_required: false })} />);
    expect(screen.queryByText('Create remediation plan?')).not.toBeInTheDocument();
  });

  it('CV.MULTI.01A state C: inconclusive conclusion + named missing evidence/limitations', () => {
    render(
      <InvestigationOutcomeCard
        outcome={outcome({
          investigation_status: 'incomplete',
          disposition: 'inconclusive',
          findings: [],
          unconfirmed_hypotheses: [],
          missing_evidence: ['authentication_correlation', 'session_corroboration'],
          limitations: ['Missing governed evidence: authentication_correlation', 'MCP execution disabled'],
          remediation_offer_required: false,
        })}
        progress={[
          {
            step_id: 'auth',
            purpose: 'authentication_correlation',
            status: 'failed',
            source: 'splunk_search',
            evidence_summary: 'MCP execution disabled',
            evidence_refs: [],
            failure: 'mcp_off',
          },
        ]}
      />,
    );
    expect(screen.getByText('disposition: inconclusive')).toBeInTheDocument();
    expect(screen.getByText('Important missing evidence')).toBeInTheDocument();
    expect(screen.getByText('authentication_correlation')).toBeInTheDocument();
    expect(screen.getByText('Limitations')).toBeInTheDocument();
    expect(screen.getByText('Missing governed evidence: authentication_correlation')).toBeInTheDocument();
    // Progress telemetry is labeled separately from findings (same stop phrase may also appear in progress copy)
    expect(screen.getByLabelText('Operational progress')).toBeInTheDocument();
    expect(screen.getAllByText('MCP execution disabled').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('Supported by governed evidence')).not.toBeInTheDocument();
  });

  it('CV.MULTI.01B state D: suspicious conclusion with findings, no invented compromise_confirmed', () => {
    const { container } = render(
      <InvestigationOutcomeCard
        outcome={outcome({
          investigation_status: 'completed',
          disposition: 'suspicious',
          findings: ['25 failed SSH then success from 198.51.100.42 to admin'],
          unconfirmed_hypotheses: [],
          missing_evidence: [],
          limitations: [],
          remediation_offer_required: false,
        })}
      />,
    );
    expect(screen.getByText('disposition: suspicious')).toBeInTheDocument();
    expect(screen.getByText('Supported by governed evidence')).toBeInTheDocument();
    expect(screen.getByText('25 failed SSH then success from 198.51.100.42 to admin')).toBeInTheDocument();
    expect(container.textContent?.toLowerCase() ?? '').not.toContain('compromise_confirmed');
    expect(screen.queryByText('Important missing evidence')).not.toBeInTheDocument();
  });
});
