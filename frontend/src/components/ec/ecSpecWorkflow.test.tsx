import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EcAgentWorkflow } from '@/components/ec/EcAgentWorkflow';
import { EcActionsTable } from '@/components/ec/EcFindingsTable';
import { friendlyProvenance } from '@/components/ec/EcInvestigationResultList';
import type { EcAgentWorkflowPayload, EcAssessment } from '@/components/ec/types';

const noop = () => undefined;

const assessment: EcAssessment = {
  incident_priority: 'P2',
  priority_rule: 'SOC-POL-PRIO-01 rule 2',
  priority_basis: 'Tier-0 asset · unexplained access, no compromise confirmed',
  threat_assessment: 'Unconfirmed',
};

function renderWorkflow(workflow: EcAgentWorkflowPayload) {
  return render(
    <EcAgentWorkflow
      workflow={workflow}
      onRunInvestigation={noop}
      onRunRemediation={noop}
      onHilApprove={noop}
      onHilSkip={noop}
    />,
  );
}

describe('spec-engine workflow rendering', () => {
  it('shows the backend status label, and a result only once the action has run', () => {
    render(
      <EcActionsTable
        editable={false}
        steps={[
          { id: 'a', title: 'Open a P2 incident', summary: 'ITSM incident at P2.', status: 'PROPOSED', status_label: 'Pending approval', result: null },
          { id: 'b', title: 'Ask Detection Engineering', summary: 'ITSM request.', status: 'REQUESTED', status_label: 'Requested', result: 'Request TASK0019220 raised' },
        ]}
      />,
    );
    expect(screen.getByText('Pending approval')).toBeInTheDocument();
    expect(screen.getByText('ITSM incident at P2.')).toBeInTheDocument();
    expect(screen.getByText('Requested')).toBeInTheDocument();
    expect(screen.getByText('Request TASK0019220 raised')).toBeInTheDocument();
    expect(screen.queryByText('Done')).not.toBeInTheDocument();
  });

  it('keeps incident priority and threat assessment apart in the findings', () => {
    renderWorkflow({
      lifecycle: 'INVESTIGATION_COMPLETE',
      phase: 'investigation_complete',
      investigation_conclusion: {
        headline: 'Not confirmed malicious.',
        narrative_points: ['Confirmed: no logon came from the IP.'],
        assessment,
        sources: ['SOC-SOP-AUTH-003 §4'],
      },
    });
    expect(screen.getByText(/Incident priority/)).toHaveTextContent('P2');
    expect(screen.getByText(/Threat assessment/)).toHaveTextContent('Unconfirmed');
    expect(screen.getByText(/Sources: SOC-SOP-AUTH-003 §4/)).toBeInTheDocument();
  });

  it('closes with the real final state, action statuses and what is still pending', () => {
    renderWorkflow({
      lifecycle: 'COMPLETE',
      phase: 'remediation',
      final_summary: {
        title: 'OPEN — MONITORING REQUESTED',
        headline: 'Incident open at P2. Watch requested.',
        assessment,
        actions: [
          { title: 'Open a P2 incident', status: 'VERIFIED', status_label: 'Verified', result: 'Incident INC0048213 opened (P2)' },
          { title: 'Ask Detection Engineering', status: 'REQUESTED', status_label: 'Requested', result: 'Request TASK0019220 raised' },
        ],
        in_progress: ['Detection Engineering to schedule the 14-day watch'],
        deferred: ['Block — not proposed'],
        risk_note: 'Re-investigate if the watch alerts.',
      },
    });
    expect(screen.getByText('OPEN — MONITORING REQUESTED')).toBeInTheDocument();
    const finalActions = screen.getByText('Incident INC0048213 opened (P2)').closest('ul');
    expect(finalActions).toHaveTextContent('Verified');
    expect(finalActions).toHaveTextContent('Requested');
    expect(screen.getByText(/Waiting on: Detection Engineering/)).toBeInTheDocument();
    expect(screen.getByText(/Next: Re-investigate/)).toBeInTheDocument();
  });

  it('never labels a connector as a demo', () => {
    expect(friendlyProvenance('experience_center_fixture')).toBe('');
    expect(friendlyProvenance('simulated_mcp')).toBe('');
    expect(friendlyProvenance('governed_search')).toBe('GOVERNED SEARCH');
  });
});

describe('response records and priority choice', () => {
  const incidentStep = {
    id: 'open_incident',
    title: 'Open a P2 incident',
    summary: 'ITSM incident at P2.',
    status: 'PROPOSED',
    status_label: 'Pending approval',
    selected: true,
    priority_control: {
      policy_priority: 'P2',
      policy_rule: 'SOC-POL-PRIO-01 rule 2',
      policy_basis: 'Tier-0 asset · unexplained access, no compromise confirmed',
      options: ['P1', 'P2', 'P3', 'P4'],
      selected: 'P2',
      reason: '',
    },
  };

  it('needs a reason before a priority change can be approved, then sends it', () => {
    const calls: unknown[][] = [];
    const { container } = render(
      <EcAgentWorkflow
        workflow={{
          lifecycle: 'REMEDIATION_PLAN_READY',
          phase: 'remediation',
          remediation_plan: { visible: true, steps: [incidentStep] },
          remediation_results: { steps: [incidentStep] },
        }}
        onRunInvestigation={noop}
        onRunRemediation={(...args) => calls.push(args)}
        onHilApprove={noop}
        onHilSkip={noop}
      />,
    );
    const scope = within(container);
    fireEvent.change(scope.getByLabelText('Priority'), { target: { value: 'P1' } });
    const approve = scope.getByRole('button', { name: /Approve/ });
    expect(approve).toBeDisabled();
    fireEvent.change(scope.getByLabelText(/Reason for changing from P2 to P1/), { target: { value: 'Active audit scope' } });
    expect(approve).not.toBeDisabled();
    fireEvent.click(approve);
    expect(calls).toEqual([[['open_incident'], { priority: 'P1', reason: 'Active audit scope' }]]);
  });

  it('shows the created ticket and the email as sent from the final summary', () => {
    const { container } = render(
      <EcAgentWorkflow
        workflow={{
          lifecycle: 'COMPLETE',
          phase: 'remediation',
          final_summary: {
            title: 'OPEN — MONITORING REQUESTED',
            headline: 'Incident open at P2.',
            actions: [
              {
                title: 'Open a P2 incident',
                status: 'VERIFIED',
                status_label: 'Verified',
                result: 'Incident INC0048213 opened (P2)',
                ticket: { number: 'INC0048213', type: 'Incident', state: 'New', assignment_group: 'SOC Tier 2' },
              },
              {
                title: 'Ask the partner owner',
                status: 'AWAITING_REPLY',
                status_label: 'Sent · awaiting reply',
                result: 'Sent to the Integration team',
                email: { to: 'Integration team', subject: 'Partner PRT-0147 — please confirm', body: 'Incident: INC0048213' },
                email_delivery: { sent: true, line: 'Delivered by SMTP to soc@example.org', to_address: 'soc@example.org', message_id: '<abc@x>' },
              },
            ],
          },
        }}
        onRunInvestigation={noop}
        onRunRemediation={noop}
        onHilApprove={noop}
        onHilSkip={noop}
      />,
    );
    const scope = within(container);
    fireEvent.click(scope.getByRole('button', { name: 'View ticket' }));
    expect(scope.getByText('SOC Tier 2')).toBeInTheDocument();
    fireEvent.click(scope.getByRole('button', { name: 'View email' }));
    expect(scope.getByText('Delivered by SMTP to soc@example.org')).toBeInTheDocument();
    expect(scope.getByText('Message ID: <abc@x>')).toBeInTheDocument();
  });
});
