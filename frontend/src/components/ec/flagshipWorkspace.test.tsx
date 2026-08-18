import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EcActionFlow } from '@/components/ec/EcActionFlow';
import { EcCoordinationPanels } from '@/components/ec/EcCoordinationPanels';
import { EcInvestigationAnswer } from '@/components/ec/EcInvestigationAnswer';
import { EcInvestigationWorkspace } from '@/components/ec/EcInvestigationWorkspace';
import { EcScenarioPicker } from '@/components/ec/EcScenarioPicker';
import { EcTransparencyDrawer } from '@/components/ec/EcTransparencyDrawer';
import type { ExperienceCenterResponse } from '@/components/ec/types';
import { followUpEcScenario, runEcScenario } from '@/api/ecClient';

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

async function readyComposer() {
  await screen.findByPlaceholderText(/Ask V.AI SOC/i);
}

function sendInvestigationQuery(query: string) {
  const input = screen.getByPlaceholderText(/Ask V.AI SOC/i);
  fireEvent.change(input, { target: { value: query } });
  fireEvent.click(screen.getByRole('button', { name: /Send investigation query/i }));
}

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

  it('renders inbound team reply without duplicating action panels', () => {
    render(<EcCoordinationPanels envelope={envelope} />);
    expect(screen.getByText(/Inbound team reply/i)).toBeInTheDocument();
    expect(screen.getByText(/whitelisted yesterday/i)).toBeInTheDocument();
    expect(screen.queryByText('Email')).not.toBeInTheDocument();
  });

  it('renders editable email draft with send control', () => {
    render(
      <EcActionFlow
        actions={[{
          action_id: 'ec-act-email',
          kind: 'email_send',
          label: 'Email firewall/security team',
          state: 'APPROVAL_REQUIRED',
          provenance: 'simulated_phase10_action',
          production_side_effect: false,
          draft: {
            to: 'anurag.agarwal@velocis.in',
            subject: 'SOC request',
            body: 'Please review the indicator.',
          },
        }]}
        onUpdate={vi.fn()}
      />,
    );
    expect(screen.getByDisplayValue('anurag.agarwal@velocis.in')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Send email/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Approve$/i })).not.toBeInTheDocument();
  });

  it('renders investigation path', () => {
    render(<EcTransparencyDrawer envelope={envelope} />);
    expect(screen.getByText(/Investigation Path/i)).toBeInTheDocument();
  });

  it('hides Layer 1 until the execution journey finishes', async () => {
    render(<EcInvestigationWorkspace />);
    await readyComposer();
    vi.useFakeTimers();
    sendInvestigationQuery('q3');
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId('experience-execution-progress-panel')).toBeInTheDocument();
    expect(screen.queryByText(/SOC Answer/i)).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(900);
    });
    expect(screen.getByText(/SOC Answer/i)).toBeInTheDocument();
    expect(screen.queryByTestId('experience-execution-progress-panel')).not.toBeInTheDocument();
    expect(document.querySelector('[data-ec-layer="soc-answer"]')?.textContent).toMatch(
      /Firewall-team coordination/,
    );
  });

  it('keeps the waiting panel when the journey pauses on HIL', async () => {
    vi.mocked(runEcScenario).mockResolvedValueOnce({
      ...envelope,
      ec_execution_journey: {
        journey_id: 's3-wait',
        kind: 'action',
        header: 'Connecting to email transport',
        stages: [
          { id: 'prep', title: 'Preparing firewall-team request', semantic_type: 'plan', duration_ms_hint: 15 },
          { id: 'hil', title: 'Waiting for send approval', semantic_type: 'hil', duration_ms_hint: 0 },
        ],
      },
    });
    render(<EcInvestigationWorkspace />);
    await readyComposer();
    vi.useFakeTimers();
    sendInvestigationQuery('q3');
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(900);
    });
    expect(screen.getByText(/SOC Answer/i)).toBeInTheDocument();
    expect(screen.getByTestId('experience-execution-progress-panel')).toBeInTheDocument();
    expect(screen.getByText(/Connecting to email transport/i)).toBeInTheDocument();
  });

  it('plays a connector journey for an action chip instead of the initial investigation', async () => {
    vi.mocked(runEcScenario).mockResolvedValueOnce({
      ...envelope,
      ec_followups: [{
        follow_up_id: 'create_incident_ticket',
        label: 'Create incident ticket',
        advances_state: true,
        group: 'action',
        leads_to_action: true,
      }],
      ec_execution_journey: {
        journey_id: 's3-test-initial',
        kind: 'initial',
        header: 'Running governed investigation pipeline',
        stages: [
          { id: 'understand', title: 'Understanding the question', semantic_type: 'understand', duration_ms_hint: 15 },
          { id: 'outcome', title: 'Building InvestigationOutcome', semantic_type: 'outcome', duration_ms_hint: 15 },
        ],
      },
    });
    vi.mocked(followUpEcScenario).mockResolvedValueOnce({
      ...envelope,
      analyst: {
        ...envelope.analyst,
        finding_title: 'Ticket recorded',
      },
      ec_followups: [],
      ec_execution_journey: {
        journey_id: 'act-ticket',
        kind: 'action',
        header: 'Connecting to ITSM',
        follow_up_id: 'create_incident_ticket',
        stages: [
          { id: 'sel', title: 'Selecting ITSM connector', semantic_type: 'plan', duration_ms_hint: 15 },
          { id: 'conn', title: 'Connecting to ITSM', semantic_type: 'execute', duration_ms_hint: 15 },
        ],
      },
    });
    render(<EcInvestigationWorkspace />);
    await readyComposer();
    vi.useFakeTimers();
    sendInvestigationQuery('q3');
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(900);
    });
    expect(screen.getByRole('button', { name: /Create incident ticket/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Create incident ticket/i }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText(/SOC Answer/i)).toBeInTheDocument();
    expect(screen.getByTestId('experience-execution-progress-panel')).toBeInTheDocument();
    expect(screen.getAllByText(/Connecting to ITSM/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Understanding the question/i)).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(900);
    });
    expect(screen.getByText(/Ticket recorded/i)).toBeInTheDocument();
    expect(screen.queryByTestId('experience-execution-progress-panel')).not.toBeInTheDocument();
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
    await readyComposer();
    vi.useFakeTimers();
    sendInvestigationQuery('q1');
    await act(async () => {
      await Promise.resolve();
    });
    fireEvent.change(screen.getByLabelText(/Scenario catalog/i), { target: { value: 's2_ai_prompt_injection' } });
    sendInvestigationQuery('q2');
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(900);
    });
    expect(screen.getByText('S2 title')).toBeInTheDocument();
    expect(screen.queryByText('S1 title')).not.toBeInTheDocument();
  });

  it('renders source evidence inside the SOC answer layer', () => {
    const policyRule = 'A compromised device running version 14 must be upgraded to version 15';
    const { container } = render(
      <EcInvestigationAnswer
        envelope={{
          ...envelope,
          scenario_id: 's5_cisco_hardening_remediation',
          source_evidence: [
            {
              evidence_id: 'ev-s5-policy',
              source_type: 'kb_fixture',
              source_name: 'Enterprise hardening policy',
              provenance: 'ec_scenario_policy',
              preview_rows: [{ rule: policyRule }],
            },
          ],
        }}
      />,
    );
    const layer = container.querySelector('[data-ec-layer="soc-answer"]');
    expect(layer).not.toBeNull();
    expect(layer).toHaveTextContent(policyRule);
  });

  it('renders closure summary when present and omits the section otherwise', () => {
    const summary = 'R-17 upgraded to version 15 with rollback plan recorded.';
    const { container, rerender } = render(
      <EcInvestigationAnswer
        envelope={{
          ...envelope,
          ec_investigation_outcome: {
            ...envelope.ec_investigation_outcome!,
            closure_summary: summary,
          },
        }}
      />,
    );
    expect(screen.getByText(summary)).toBeInTheDocument();
    expect(container.querySelector('[data-ec-section="closure-summary"]')).not.toBeNull();

    rerender(
      <EcInvestigationAnswer
        envelope={{
          ...envelope,
          ec_investigation_outcome: {
            ...envelope.ec_investigation_outcome!,
            closure_summary: undefined,
          },
        }}
      />,
    );
    expect(container.querySelector('[data-ec-section="closure-summary"]')).toBeNull();
  });

  it('renders credibility strip badges for S1 validator and S5 device MCP footnote', () => {
    const { rerender } = render(
      <EcInvestigationAnswer
        envelope={{
          ...envelope,
          scenario_id: 's1_governed_splunk_investigation',
          ec_provenance: { live_llm_called: false, live_mcp_called: false, live_rag_called: false },
          ec_spl_governance: {
            user_request: 'q',
            time_range_supplied: true,
            environment_governance: 'g',
            why: 'w',
            searches: [],
            controls: [],
            validation: {
              engine: 'validate_spl',
              provenance: 'production_validator_read_only',
              search_1_approved: true,
              search_2_approved: true,
              override: false,
            },
            evidence_merge: 'm',
            production_mcp_executed: false,
            spl_not_required: false,
          },
          spl_validation: { warnings: ['demo_fixture_not_live_data'] },
        }}
      />,
    );
    expect(screen.getByText('SPL: production validate_spl')).toBeInTheDocument();
    expect(screen.getByText('Fixture data · not live customer telemetry')).toBeInTheDocument();

    rerender(
      <EcInvestigationAnswer
        envelope={{
          ...envelope,
          scenario_id: 's5_cisco_hardening_remediation',
          ec_provenance: { live_llm_called: false, live_mcp_called: false, live_rag_called: false },
        }}
      />,
    );
    expect(screen.getByText(/Cisco device MCP \(simulated router API\)/)).toBeInTheDocument();
    expect(screen.getByText(/Foundation-Sec 8B LLM is not used here/)).toBeInTheDocument();
  });
});
