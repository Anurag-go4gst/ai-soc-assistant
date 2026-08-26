import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ChatBubble } from '@/components/ChatBubble';

afterEach(() => cleanup());

describe('ChatBubble conditional requested actions', () => {
  it('CV.MULTI.01A shows pending intents without remediation or send CTAs', () => {
    render(
      <ChatBubble
        message={{
          id: 'multi-01a',
          role: 'assistant',
          content: 'The investigation is inconclusive.',
          displayStage: 'complete',
          trace: {
            trace_id: 'trace-multi-01a',
            message: 'The investigation is inconclusive.',
            note: 'deterministic',
            user_query: 'Investigate and conditionally remediate and draft an email.',
            investigation_outcome: {
              schema_version: 'investigation_outcome_v2',
              investigation_status: 'incomplete',
              disposition: 'inconclusive',
              findings: [],
              supported_hypotheses: [],
              unconfirmed_hypotheses: [],
              evidence_refs: [],
              missing_evidence: ['authentication_correlation'],
              limitations: ['MCP execution disabled'],
              remediation_offer_required: false,
              recommended_actions: [],
              llm_proposal_accepted: false,
            },
            control_plane_trace: {
              resolved_query: {
                requested_conditional_actions: [
                  {
                    action_kind: 'remediation',
                    lifecycle_state: 'PENDING_CONDITION',
                    predicate_id: 'account_compromise_confirmed',
                    recipient_roles: [],
                  },
                  {
                    action_kind: 'email_draft',
                    lifecycle_state: 'PENDING_CONDITION',
                    predicate_id: 'account_compromise_confirmed',
                    recipient_roles: ['firewall_team', 'identity_team'],
                  },
                ],
              },
            },
          },
        }}
      />,
    );

    expect(screen.getByRole('region', { name: 'Requested conditional actions' })).toBeInTheDocument();
    expect(screen.getByText('Remediation plan requested')).toBeInTheDocument();
    expect(screen.getByText('Email draft requested')).toBeInTheDocument();
    expect(screen.getByText('Recipient roles: firewall team, identity team')).toBeInTheDocument();
    expect(screen.getAllByText('account_compromise_confirmed')).toHaveLength(2);
    expect(screen.getByText(/not eligible, approved, sent, or executed/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /send/i })).not.toBeInTheDocument();
    expect(screen.queryByText('Create remediation plan?')).not.toBeInTheDocument();
  });

  it('does not render an ELIGIBLE action through the pending-intent surface', () => {
    render(
      <ChatBubble
        message={{
          id: 'eligible-action',
          role: 'assistant',
          content: 'Eligibility is handled by the governed Phase 10 lane.',
          displayStage: 'complete',
          trace: {
            trace_id: 'trace-eligible',
            message: 'Eligibility is handled by the governed Phase 10 lane.',
            note: 'deterministic',
            email_draft: {
              schema_version: 'governed_email_draft_v1',
              status: 'draft_ready',
              recipient_roles: ['firewall_team'],
              recipient_resolution_required: true,
              subject: 'Security investigation update: suspicious activity requires review',
              body: 'Investigation summary\n- Accepted finding\n\nEvidence references\n- ev.auth',
              findings: ['Accepted finding'],
              evidence_refs: ['ev.auth'],
              generation_source: 'deterministic_governed',
              llm_attempted: false,
              llm_status: 'not_attempted_no_governed_email_role',
              send_authorized: false,
              sent: false,
            },
            control_plane_trace: {
              resolved_query: {
                requested_conditional_actions: [
                  {
                    action_kind: 'email_draft',
                    lifecycle_state: 'ELIGIBLE',
                    predicate_id: 'account_compromise_confirmed',
                    recipient_roles: ['firewall_team'],
                  },
                ],
              },
            },
          },
        }}
      />,
    );

    expect(screen.queryByRole('region', { name: 'Requested conditional actions' })).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Governed email draft' })).toBeInTheDocument();
    expect(screen.getByText('Recipients unresolved · not approved or sent')).toBeInTheDocument();
    expect(screen.getByText(/no live model call · no send authority/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /send/i })).not.toBeInTheDocument();
  });
});
