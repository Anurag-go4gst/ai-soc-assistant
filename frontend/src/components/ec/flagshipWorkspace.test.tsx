import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EcActionFlow } from '@/components/ec/EcActionFlow';
import { EcCoordinationPanels } from '@/components/ec/EcCoordinationPanels';
import { EcInvestigationAnswer } from '@/components/ec/EcInvestigationAnswer';
import { EcInvestigationWorkspace } from '@/components/ec/EcInvestigationWorkspace';
import { EcScenarioPicker } from '@/components/ec/EcScenarioPicker';
import { EcTransparencyDrawer } from '@/components/ec/EcTransparencyDrawer';
import type { ExperienceCenterResponse } from '@/components/ec/types';
import { runEcScenario } from '@/api/ecClient';

vi.mock('@/api/ecClient', () => ({
  listEcScenarios: vi.fn(async () => ({
    scenarios: [
      { scenario_id: 's1_governed_splunk_investigation', label: 'S1 · Governed large-scale investigation', category: 'Flagship', query: 'q1', expected_skill: 'attack_discovery' },
      { scenario_id: 's2_ai_prompt_injection', label: 'S2 · AI application security', category: 'Flagship', query: 'q2', expected_skill: 'guided_investigation' },
      { scenario_id: 's3_firewall_team_coordination', label: 'S3 · Firewall-team coordination', category: 'Flagship', query: 'q3', expected_skill: 'guided_investigation' },
      { scenario_id: 's4_zero_day_no_playbook', label: 'S4 · Zero-day / no playbook', category: 'Flagship', query: 'q4', expected_skill: 'guided_investigation' },
      { scenario_id: 's5_cisco_hardening_remediation', label: 'S5 · Policy-driven Cisco remediation', category: 'Flagship', query: 'q5', expected_skill: 'guided_investigation' },
      { scenario_id: 's6_investigation_continuity', label: 'S6 · Investigation continuity', category: 'Flagship', query: 'q6', expected_skill: 'guided_investigation' },
      { scenario_id: 's7_conflicting_ot_evidence', label: 'S7 · Conflicting evidence', category: 'Flagship', query: 'q7', expected_skill: 'guided_investigation' },
      { scenario_id: 'mitre_mapping_auth_alert', label: 'MITRE clarification', category: 'MITRE', query: 'map mitre', expected_skill: 'knowledge_recall' },
    ],
    count: 8,
  })),
  approveEcAction: vi.fn(),
  executeEcAction: vi.fn(),
  verifyEcAction: vi.fn(),
  runEcScenario: vi.fn(async () => ({
    scenario_id: 's3_firewall_team_coordination',
    trace_id: 'demo-s3',
    message: 'Coordinate the firewall block.',
    route_source: 'ec_fixture_selected',
    analyst: {
      finding_title: 'Firewall-team coordination',
      assessment: 'Follow the company firewall-block process.',
      unconfirmed_findings: ['Whether the whitelist explains the traffic'],
      missing_evidence: ['Firewall-team confirmation'],
    },
    ec_projection: {
      understanding: { title: 'Understanding', summary: 'Coordinate block', items: [], provenance: { kind: 'experience_center_fixture', detail: 's3' } },
      resource_plan: { title: 'Resources', summary: 'Email and process', items: [], provenance: { kind: 'experience_center_fixture', detail: 's3' } },
      phase_contract: { title: 'Controls', summary: 'HIL', items: [], provenance: { kind: 'ec_scenario_policy', detail: 's3' } },
      evidence_state: { title: 'Evidence', summary: 'Pending reply', items: [], provenance: { kind: 'experience_center_fixture', detail: 's3' } },
      investigation_outcome: { title: 'Outcome', summary: 'reassess', items: [], provenance: { kind: 'experience_center_fixture', detail: 's3' } },
      provenance: { kind: 'experience_center_fixture', detail: 's3' },
    },
    ec_actions: [],
    ec_followups: [],
    ec_session_state: {
      session_id: 'ec-sess-secret123',
      family: 's3',
      scenario_id: 's3_firewall_team_coordination',
      turn: 1,
      awaiting_external: true,
      applied_follow_up_ids: [],
    },
    ec_provenance: {
      live_llm_called: false,
      envelope: 'experience_center_response',
      route_source: 'ec_fixture_selected',
    },
    ec_workflow_state: 'AWAITING_FIREWALL_TEAM_CONFIRMATION',
    ec_workflow_path: ['Investigation', 'Email sent', 'Awaiting team'],
    ec_email: {
      to: 'firewall-team@internal',
      subject: 'Block request',
      status: 'awaiting_reply',
      mandatory_fields: { malicious_ip: '198.51.100.42', reason: 'confirmed malicious activity' },
      inbound: 'This IP was manually whitelisted yesterday for vendor testing.',
    },
    ec_investigation_outcome: {
      disposition: 'needs_reassessment',
      confirmed: ['Request sent'],
      supported: [],
      unconfirmed: ['Whether the whitelist explains the traffic'],
      missing_evidence: ['Business-owner reconfirmation'],
    },
    ec_execution_journey: {
      journey_id: 's3-test-initial',
      kind: 'initial',
      header: 'Running governed investigation pipeline',
      stages: [
        {
          id: 'understand',
          title: 'Understanding the question',
          semantic_type: 'understand',
          duration_ms_hint: 15,
        },
        {
          id: 'outcome',
          title: 'Building InvestigationOutcome',
          semantic_type: 'outcome',
          duration_ms_hint: 15,
        },
      ],
    },
  })),
  followUpEcScenario: vi.fn(),
}));

const stamp = { kind: 'experience_center_fixture', detail: 's3' };
const envelope: ExperienceCenterResponse = {
  scenario_id: 's3_firewall_team_coordination',
  trace_id: 'demo-s3',
  message: 'Coordinate the firewall block.',
  analyst: {
    finding_title: 'Firewall-team coordination',
    assessment: 'Follow the company firewall-block process.',
    unconfirmed_findings: ['Whether the whitelist explains the traffic'],
    missing_evidence: ['Firewall-team confirmation'],
  },
  ec_projection: {
    understanding: { title: 'Understanding', summary: 'Coordinate block', items: [], provenance: stamp },
    resource_plan: { title: 'Resources', summary: 'Email and process', items: [], provenance: stamp },
    phase_contract: { title: 'Controls', summary: 'HIL', items: [], provenance: stamp },
    evidence_state: { title: 'Evidence', summary: 'Pending reply', items: [], provenance: stamp },
    investigation_outcome: { title: 'Outcome', summary: 'reassess', items: [], provenance: stamp },
    provenance: stamp,
  },
  ec_actions: [],
  ec_followups: [],
  route_source: 'ec_fixture_selected',
  ec_session_state: {
    session_id: 'ec-sess-secret123',
    family: 's3',
    scenario_id: 's3_firewall_team_coordination',
    turn: 1,
    awaiting_external: true,
    applied_follow_up_ids: [],
  },
  ec_provenance: { live_llm_called: false, route_source: 'ec_fixture_selected' },
  ec_workflow_state: 'AWAITING_FIREWALL_TEAM_CONFIRMATION',
  ec_workflow_path: ['Investigation', 'Email sent', 'Awaiting team'],
  ec_email: {
    to: 'firewall-team@internal',
    subject: 'Block request',
    status: 'awaiting_reply',
    mandatory_fields: { malicious_ip: '198.51.100.42', reason: 'confirmed malicious activity' },
    inbound: 'This IP was manually whitelisted yesterday for vendor testing.',
  },
  ec_impact_legend: ['Attempted', 'Blocked', 'Not confirmed'],
  ec_investigation_outcome: {
    disposition: 'needs_reassessment',
    confirmed: ['Request sent'],
    supported: [],
    unconfirmed: ['Whether the whitelist explains the traffic'],
    missing_evidence: ['Business-owner reconfirmation'],
  },
};

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('Flagship Experience Center UX', () => {
  it('lists seven flagships separately from lab', async () => {
    render(<EcScenarioPicker selectedId="" onSelect={vi.fn()} onRun={vi.fn()} />);
    expect(await screen.findByRole('option', { name: /S2 · AI application security/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /S7 · Conflicting evidence/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /MITRE clarification/i })).toBeInTheDocument();
  });

  it('renders Layer 1 without architecture dump or internal identifiers', () => {
    render(<EcInvestigationAnswer envelope={envelope} />);
    expect(screen.getByText(/SOC Answer/i)).toBeInTheDocument();
    expect(screen.getByText(/Assessment/i)).toBeInTheDocument();
    expect(screen.getByText(/Evidence still required/i)).toBeInTheDocument();
    expect(screen.queryByText(/v2/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/dispatch-v2/i)).not.toBeInTheDocument();
    const layer1 = document.querySelector('[data-ec-layer="soc-answer"]');
    expect(layer1?.textContent).not.toMatch(/ec_fixture_selected/);
    expect(layer1?.textContent).not.toMatch(/experience_center_fixture/);
    expect(layer1?.textContent).not.toMatch(/simulated_phase10_action/);
    expect(screen.queryByText('ec-sess-secret123')).not.toBeInTheDocument();
  });

  it('keeps provenance identifiers in Layer 2, not visitor chrome', async () => {
    render(<EcInvestigationWorkspace />);
    expect(await screen.findByRole('option', { name: /S1 · Governed large-scale investigation/i })).toBeInTheDocument();
    expect(screen.queryByText('ec_fixture_selected')).not.toBeInTheDocument();
    expect(screen.queryByText('ec-sess-secret123')).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/simulated_phase10_action/);
    render(<EcTransparencyDrawer envelope={envelope} />);
    const layer2 = document.querySelector('[data-ec-layer="investigation-path"]');
    expect(layer2?.textContent).toMatch(/experience_center_fixture/);
  });

  it('renders email send/await/inbound', () => {
    render(<EcCoordinationPanels envelope={envelope} />);
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText(/malicious ip/i)).toBeInTheDocument();
    expect(screen.getByText(/whitelisted yesterday/i)).toBeInTheDocument();
  });

  it('keeps Execute disabled until approved', () => {
    render(
      <EcActionFlow
        actions={[{
          action_id: 'ec-act-1',
          kind: 'cisco_upgrade',
          label: 'cisco.upgrade to 15',
          state: 'APPROVAL_REQUIRED',
          provenance: 'simulated_phase10_action',
          production_side_effect: false,
        }]}
        onUpdate={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /Execute/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Verify/i })).toBeDisabled();
  });

  it('renders investigation path', () => {
    render(<EcTransparencyDrawer envelope={envelope} />);
    expect(screen.getByText(/Investigation Path/i)).toBeInTheDocument();
  });

  it('hides Layer 1 until the execution journey finishes', async () => {
    render(<EcInvestigationWorkspace />);
    const run = await screen.findByRole('button', { name: /Run investigation/i });
    vi.useFakeTimers();
    fireEvent.click(run);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId('experience-execution-progress-panel')).toBeInTheDocument();
    expect(screen.queryByText(/SOC Answer/i)).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(screen.getByText(/SOC Answer/i)).toBeInTheDocument();
    expect(document.querySelector('[data-ec-layer="soc-answer"]')?.textContent).toMatch(
      /Firewall-team coordination/,
    );
  });

  it('cancels a stale journey so a prior envelope cannot appear later', async () => {
    vi.mocked(runEcScenario).mockImplementation(async (scenarioId: string) => ({
      ...envelope,
      scenario_id: scenarioId,
      analyst: {
        finding_title: scenarioId === 's2_ai_prompt_injection' ? 'S2 title' : 'S1 title',
        assessment: 'Assessment text',
        unconfirmed_findings: [],
        missing_evidence: [],
      },
      ec_execution_journey: {
        journey_id: `${scenarioId}-j`,
        kind: 'initial',
        header: 'Running governed investigation pipeline',
        stages: [
          { id: 'understand', title: 'Understanding the question', semantic_type: 'understand', duration_ms_hint: 40 },
          { id: 'outcome', title: 'Building InvestigationOutcome', semantic_type: 'outcome', duration_ms_hint: 40 },
        ],
      },
    }));
    render(<EcInvestigationWorkspace />);
    const run = await screen.findByRole('button', { name: /Run investigation/i });
    vi.useFakeTimers();
    fireEvent.click(run);
    await act(async () => {
      await Promise.resolve();
    });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 's2_ai_prompt_injection' } });
    fireEvent.click(screen.getByRole('button', { name: /Run investigation/i }));
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(screen.getByText('S2 title')).toBeInTheDocument();
    expect(screen.queryByText('S1 title')).not.toBeInTheDocument();
  });
});
