import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EcAgilusPatchPanel, EcExecutiveSummaryPanel, EcInvestigationPhasesPanel, EcVpnGatewayPosturePanel } from '@/components/ec/EcInvestigationPosture';

describe('EcInvestigationPosture', () => {
  it('renders executive summary and VPN posture session totals', () => {
    render(
      <>
        <EcExecutiveSummaryPanel
          bullets={['Exposure is PARTIAL.', 'Claims verified.', 'Apply mitigations on approval.']}
        />
        <EcVpnGatewayPosturePanel
          rows={[
            {
              gateway: 'VPN-GW-01',
              site: 'DC-A',
              version: '12.3',
              affected: true,
              health: 'Healthy',
              active_sessions: 10,
            },
            {
              gateway: 'VPN-GW-02',
              site: 'DC-B',
              version: '13.0',
              affected: false,
              health: 'Healthy',
              active_sessions: 5,
            },
          ]}
        />
      </>,
    );
    expect(screen.getByText('Executive summary')).toBeInTheDocument();
    expect(screen.getByText(/Exposure is PARTIAL/)).toBeInTheDocument();
    expect(screen.getByText(/15 active VPN sessions/)).toBeInTheDocument();
    expect(screen.getByText('VPN-GW-01')).toBeInTheDocument();
  });

  it('renders Agilus patch panel with job and ticket when awaiting callback', () => {
    render(
      <EcAgilusPatchPanel
        patch={{
          product: 'Agilus',
          patch_id: 'EG-VPN-12.3.5-EMERG',
          patch_title: 'Emergency control-plane hardening',
          targets: ['VPN-GW-01', 'VPN-GW-02'],
          status: 'AWAITING_CALLBACK',
          job_id: 'AGILUS-JOB-8842',
          ticket_id: 'CHG-ZD-AGILUS-001',
          detail: 'Patch job submitted. Investigation will update on Agilus callback.',
        }}
      />,
    );
    expect(screen.getByText('Agilus patch orchestration')).toBeInTheDocument();
    expect(screen.getByText('AGILUS-JOB-8842')).toBeInTheDocument();
    expect(screen.getByText('CHG-ZD-AGILUS-001')).toBeInTheDocument();
  });

  it('renders phased investigation plan with action button', () => {
    const onAction = vi.fn();
    render(
      <EcInvestigationPhasesPanel
        phases={[
          {
            phase: '1',
            title: 'Assess exposure',
            steps: [
              {
                id: 'vuln_scan',
                title: 'Vulnerability scanner',
                status: 'PLANNED',
                plan_summary: 'Scan VPN gateways for the advisory condition.',
                action_label: 'Run scan',
                follow_up_id: 'run_vuln_scan',
                connector_mode: 'MCP',
                connector_available: true,
                executed: false,
              },
            ],
          },
        ]}
        onStepAction={onAction}
      />,
    );
    expect(screen.getByText('Investigation plan')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Run scan' }));
    expect(onAction).toHaveBeenCalledWith('run_vuln_scan');
  });
});
