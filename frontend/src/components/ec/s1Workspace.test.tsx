import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EcActionFlow } from '@/components/ec/EcActionFlow';
import { EcFollowUpBar } from '@/components/ec/EcFollowUpBar';
import { EcInvestigationAnswer } from '@/components/ec/EcInvestigationAnswer';
import { EcScenarioPicker } from '@/components/ec/EcScenarioPicker';
import { EcTransparencyDrawer } from '@/components/ec/EcTransparencyDrawer';
import type { ExperienceCenterResponse } from '@/components/ec/types';

vi.mock('@/api/ecClient', () => ({
  listEcScenarios: vi.fn(async () => ({
    scenarios: [
      {
        scenario_id: 's1_governed_splunk_investigation',
        label: 'S1 · Governed large-scale Splunk investigation',
        category: 'Flagship',
        query: 'Find all communication involving suspicious IP 198.51.100.42 and identify affected systems.',
        expected_skill: 'attack_discovery',
      },
    ],
    count: 1,
  })),
  runEcScenario: vi.fn(),
  followUpEcScenario: vi.fn(),
  approveEcAction: vi.fn(),
  executeEcAction: vi.fn(),
  verifyEcAction: vi.fn(),
}));

const stamp = { kind: 'experience_center_fixture', detail: 's1' };

const envelope: ExperienceCenterResponse = {
  scenario_id: 's1_governed_splunk_investigation',
  trace_id: 'demo-s1-test',
  message: 'Suspicious activity from 198.51.100.42 was observed.',
  analyst_summary: 'Suspicious activity from 198.51.100.42 was observed.',
  analyst: {
    finding_title: 'Governed 60-day investigation of 198.51.100.42',
    severity_label: 'P2 High',
    assessment: 'Suspicious activity from 198.51.100.42 was observed across multiple internal systems.',
    what_we_found: 'Two bounded firewall searches cover 60 days as 30+30.',
    unconfirmed_findings: ['Successful account compromise', 'Lateral movement'],
    recommended_actions: ['Check successful authentications'],
    important_evidence: ['Traffic observed in both windows'],
    affected_systems: [
      {
        system: '10.20.1.10',
        role: 'Jump host',
        activity: 'Denied probing plus 3 allowed connections',
        first_seen: '2026-06-18T04:12:00Z',
        last_seen: '2026-08-16T16:44:00Z',
        allowed_denied: '3 allowed / 1842 denied',
        auth_correlation: 'svc_jump_ops',
        risk_note: 'Highest-priority host',
      },
    ],
  },
  ec_projection: {
    understanding: { title: 'Understanding', summary: 'No time range', items: [], provenance: stamp },
    resource_plan: { title: 'Resources', summary: 'Firewall index', items: [], provenance: stamp },
    phase_contract: { title: 'Governance', summary: '30+30', items: [], provenance: { kind: 'ec_scenario_policy' } },
    evidence_state: { title: 'Evidence', summary: 'Merged', items: [], provenance: stamp },
    investigation_outcome: { title: 'Outcome', summary: 'suspicious', items: ['production InvestigationOutcome field unused'], provenance: stamp },
    provenance: stamp,
  },
  ec_actions: [],
  ec_followups: [
    { follow_up_id: 'check_successful_auth', label: 'Check successful authentications', advances_state: true, group: 'continue' },
    { follow_up_id: 'prepare_firewall_block', label: 'Prepare firewall block request', advances_state: true, group: 'action', leads_to_action: true },
  ],
  ec_session_state: {
    family: 's1_governed_splunk',
    scenario_id: 's1_governed_splunk_investigation',
    turn: 0,
    awaiting_external: false,
    applied_follow_up_ids: [],
  },
  ec_provenance: { live_llm_called: false, live_mcp_called: false },
  ec_spl_governance: {
    user_request: 'Find all communication involving suspicious IP 198.51.100.42 and identify affected systems.',
    time_range_supplied: false,
    environment_governance: 'Environment search governance applied.',
    why: '60-day coverage as two bounded 30-day searches.',
    searches: [
      {
        search_id: 'search_1',
        label: 'Search 1 · first 30-day window',
        earliest: '-60d',
        latest: '-30d',
        candidate_spl: 'search index=pgcil_soc earliest=-60d latest=-30d | stats count | head 100',
        approved: true,
        reject_reasons: [],
        provenance: 'production_validator_read_only',
      },
      {
        search_id: 'search_2',
        label: 'Search 2 · next 30-day window',
        earliest: '-30d',
        latest: 'now',
        candidate_spl: 'search index=pgcil_soc earliest=-30d latest=now | stats count | head 100',
        approved: true,
        reject_reasons: [],
        provenance: 'production_validator_read_only',
      },
    ],
    controls: ['approved index pgcil_soc', 'bounded time range 30+30'],
    validation: {
      engine: 'validate_spl',
      provenance: 'production_validator_read_only',
      search_1_approved: true,
      search_2_approved: true,
      override: false,
    },
    evidence_merge: 'Both simulated search receipts were merged',
    production_mcp_executed: false,
    spl_not_required: false,
  },
  ec_layer2_path: ['Understanding', 'Environment search governance', 'Search 1', 'Search 2', 'Evidence merged'],
  ec_investigation_outcome: {
    disposition: 'suspicious',
    confirmed: ['Traffic observed across both windows'],
    supported: ['T1110.001'],
    unconfirmed: ['Successful account compromise'],
    missing_evidence: ['EDR'],
  },
};

describe('S1 Experience Center workspace', () => {
  it('lists S1 in the EC picker', async () => {
    render(<EcScenarioPicker selectedId="" onSelect={vi.fn()} onRun={vi.fn()} />);
    expect(await screen.findByRole('option', { name: /S1 · Governed large-scale Splunk investigation/i })).toBeInTheDocument();
  });

  it('renders Layer 1 assessment, affected systems, and uncertainty', () => {
    render(<EcInvestigationAnswer envelope={envelope} />);
    expect(screen.getByText(/Assessment/i)).toBeInTheDocument();
    expect(screen.getByText(/Suspicious activity from 198.51.100.42/i)).toBeInTheDocument();
    expect(screen.getByText('10.20.1.10')).toBeInTheDocument();
    expect(screen.getByText(/What remains unconfirmed/i)).toBeInTheDocument();
    expect(screen.getByText(/Successful account compromise/i)).toBeInTheDocument();
    const layer1 = document.querySelector('[data-ec-layer="soc-answer"]');
    expect(layer1?.textContent).not.toMatch(/ec_fixture_selected/);
    expect(layer1?.textContent).not.toMatch(/experience_center_fixture/);
    expect(layer1?.textContent).not.toMatch(/simulated_phase10_action/);
  });

  it('renders SPL governance 30+30 and validator approval', () => {
    render(<EcTransparencyDrawer envelope={envelope} />);
    expect(screen.getByText(/Search 1 · first 30-day window/i)).toBeInTheDocument();
    expect(screen.getByText(/Search 2 · next 30-day window/i)).toBeInTheDocument();
    expect(screen.getByText(/validate_spl approved/i)).toBeInTheDocument();
    expect(screen.queryByText('SPL not required')).not.toBeInTheDocument();
    expect(screen.getByText(/No time range supplied/i)).toBeInTheDocument();
  });

  it('renders follow-up chips and reports a click', () => {
    const onSelect = vi.fn();
    render(<EcFollowUpBar chips={envelope.ec_followups} onSelect={onSelect} />);
    expect(screen.getByText(/Continue investigation/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Check successful authentications/i }));
    expect(onSelect).toHaveBeenCalledWith('check_successful_auth');
    expect(screen.getByRole('button', { name: /Prepare firewall block request/i })).toBeInTheDocument();
  });

  it('renders EC action flow when a Phase 10 action is initiated', () => {
    render(
      <EcActionFlow
        actions={[
          {
            action_id: 'ec-act-block',
            kind: 'firewall_block',
            label: 'Prepare firewall block for 198.51.100.42',
            state: 'APPROVAL_REQUIRED',
            provenance: 'simulated_phase10_action',
            production_side_effect: false,
          },
        ]}
        onUpdate={vi.fn()}
      />,
    );
    expect(screen.getByText(/Action Journey/i)).toBeInTheDocument();
    expect(screen.getByText(/no production change/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve/i })).toBeInTheDocument();
  });
});
