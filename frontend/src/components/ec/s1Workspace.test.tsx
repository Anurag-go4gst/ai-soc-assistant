import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EcActionFlow } from '@/components/ec/EcActionFlow';
import { EcAgentWorkflow } from '@/components/ec/EcAgentWorkflow';
import { EcFollowUpBar } from '@/components/ec/EcFollowUpBar';
import { EcInvestigationAnswer } from '@/components/ec/EcInvestigationAnswer';
import { EcInvestigationResultList } from '@/components/ec/EcInvestigationResultList';
import { EcScenarioPicker } from '@/components/ec/EcScenarioPicker';
import { EcTransparencyDrawer } from '@/components/ec/EcTransparencyDrawer';
import type { ExperienceCenterResponse } from '@/components/ec/types';
import { agentLifecycleScrollTarget } from '@/lib/ecAgentWorkflow';

vi.mock('@/api/ecClient', () => ({
  listEcScenarios: vi.fn(async () => ({
    scenarios: [
      {
        scenario_id: 's1_governed_splunk_investigation',
        label: 'S1 · Governed large-scale Splunk investigation',
        category: 'Flagship',
        query: 'We have seen a new IP 198.51.100.42. Check and verify over the last 30 days whether it is malicious, and what is the standard SOP to raise monitoring and block it if required.',
        expected_skill: 'attack_discovery',
      },
    ],
    count: 1,
  })),
  runEcScenario: vi.fn(),
  followUpEcScenario: vi.fn(),
  prepareEcAction: vi.fn(),
  approveEcAction: vi.fn(),
  executeEcAction: vi.fn(),
  verifyEcAction: vi.fn(),
}));

const stamp = { kind: 'experience_center_fixture', detail: 's1' };

const envelope: ExperienceCenterResponse = {
  scenario_id: 's1_governed_splunk_investigation',
  trace_id: 'demo-s1-test',
  message: 'A newly observed IP 198.51.100.42 was reviewed over the last 30 days.',
  analyst_summary: 'A newly observed IP 198.51.100.42 was reviewed over the last 30 days.',
  analyst: {
    finding_title: 'Newly observed MCP IP 198.51.100.42 — last 30 days',
    severity_label: 'P2 High',
    assessment: 'A newly observed IP 198.51.100.42 was reviewed over the requested last 30 days across multiple internal systems.',
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
    user_request: 'We have seen a new IP 198.51.100.42. Check and verify over the last 30 days whether it is malicious, and what is the standard SOP to raise monitoring and block it if required.',
    time_range_supplied: true,
    environment_governance: 'Environment search governance applied.',
    why: 'Requested last 30 days plus a prior 30-day novelty window.',
    searches: [
      {
        search_id: 'search_1',
        label: 'Search 1 · prior 30-day novelty window',
        earliest: '-60d',
        latest: '-30d',
        candidate_spl: 'search index=pgcil_soc earliest=-60d latest=-30d | stats count | head 100',
        approved: true,
        reject_reasons: [],
        provenance: 'production_validator_read_only',
      },
      {
        search_id: 'search_2',
        label: 'Search 2 · requested last 30 days',
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
    disposition: 'needs_monitoring',
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
    expect(screen.getByText(/A newly observed IP 198.51.100.42/i)).toBeInTheDocument();
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
    expect(screen.getByText(/Search 1 · prior 30-day novelty window/i)).toBeInTheDocument();
    expect(screen.getByText(/Search 2 · requested last 30 days/i)).toBeInTheDocument();
    expect(screen.getByText(/validate_spl approved/i)).toBeInTheDocument();
    expect(screen.queryByText('SPL not required')).not.toBeInTheDocument();
    expect(screen.getByText(/Time range supplied/i)).toBeInTheDocument();
  });

  it('renders follow-up chips and reports a click', () => {
    const onSelect = vi.fn();
    render(<EcFollowUpBar chips={envelope.ec_followups} onSelect={onSelect} />);
    expect(screen.getByText(/Continue investigation/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Check successful authentications/i }));
    expect(onSelect).toHaveBeenCalledWith('check_successful_auth', expect.objectContaining({ follow_up_id: 'check_successful_auth' }));
    expect(screen.getByRole('button', { name: /Prepare firewall block request/i })).toBeInTheDocument();
  });

  it('derives source-evidence labels from actual items and omits unused systems', () => {
    render(
      <EcInvestigationAnswer
        envelope={{
          ...envelope,
          source_evidence: [
            {
              evidence_id: 'ev-1',
              source_type: 'splunk_mcp_fixture',
              source_name: 'Simulated Splunk firewall search',
              tool_name: 'splunk_run_query',
              provenance: 'simulated_mcp',
            },
            {
              evidence_id: 'ev-2',
              source_type: 'rag',
              source_name: 'Newly observed external SOP',
              tool_name: 'retrieve_soc_kb',
              provenance: 'experience_center_fixture',
            },
            {
              evidence_id: 'ev-3',
              source_type: 'knowledge_fixture',
              source_name: 'MCP endpoint identity',
              tool_name: 'retrieve_soc_kb',
              provenance: 'experience_center_fixture',
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/collected from Splunk MCP, SOC-KB \/ RAG, inventory fixture/i)).toBeInTheDocument();
    expect(screen.queryByText(/Agilus/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/ITSM/i)).not.toBeInTheDocument();
  });

  it('omits empty investigation-path cards and blank bullets', () => {
    const { container } = render(
      <EcTransparencyDrawer
        envelope={{
          ...envelope,
          ec_projection: {
            ...envelope.ec_projection,
            understanding: { title: 'Understanding', summary: '', items: ['', '  ', '-'], provenance: stamp },
            resource_plan: { title: 'Resources', summary: 'Firewall index', items: ['', '-'], provenance: stamp },
          },
        }}
      />,
    );
    expect(container.querySelector('[data-ec-path-card="Understanding"]')).toBeNull();
    const resources = container.querySelector('[data-ec-path-card="Resources"]');
    expect(resources).not.toBeNull();
    expect(resources?.querySelectorAll('li').length).toBe(0);
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
    expect(screen.getByRole('button', { name: /Call SOAR to block/i })).toBeInTheDocument();
  });

  it('renders Yes / Not now instead of a single continue CTA', () => {
    const onCreate = vi.fn();
    const onDecline = vi.fn();
    render(
      <EcAgentWorkflow
        workflow={{
          lifecycle: 'INVESTIGATION_COMPLETE',
          phase: 'investigation_complete',
          investigation_conclusion: {
            headline: 'Newly observed endpoint. Malicious use is not confirmed.',
            narrative_points: ['What happened: firewall communication seen.'],
          },
          executive_summary: [
            'Current risk: MEDIUM. Monitoring: pending. Blocking: CONDITIONAL — SOP threshold is not met.',
          ],
          remediation_offer: {
            title: 'Continue to remediation plan?',
            yes_label: 'Yes, create remediation plan',
            no_label: 'Not now',
          },
        }}
        onRunInvestigation={vi.fn()}
        onRunRemediation={vi.fn()}
        onHilApprove={vi.fn()}
        onHilSkip={vi.fn()}
        onCreateRemediationPlan={onCreate}
        onDeclineRemediationPlan={onDecline}
      />,
    );
    expect(screen.getByText('What happened')).toBeInTheDocument();
    expect(screen.getByText(/firewall communication seen/i)).toBeInTheDocument();
    expect(screen.getByText('Executive summary')).toBeInTheDocument();
    expect(screen.getByText(/Current risk: MEDIUM/i)).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText(/Continue to remediation plan\?/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Yes, create remediation plan/i }));
    expect(onCreate).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: /Not now/i }));
    expect(onDecline).toHaveBeenCalledTimes(1);
  });

  it('shows the remediation plan for review and executes only after Approve', () => {
    const onRunRemediation = vi.fn();
    render(
      <EcAgentWorkflow
        workflow={{
          lifecycle: 'REMEDIATION_PLAN_READY',
          phase: 'remediation',
          remediation_plan: {
            visible: true,
            primary_cta: 'Approve remediation',
            steps: [
              {
                id: 'deploy_monitoring',
                title: 'Deploy Splunk monitoring',
                status: 'QUEUED',
                selected: true,
              },
            ],
          },
          remediation_results: {
            header: 'Remediation plan',
            steps: [
              {
                id: 'deploy_monitoring',
                title: 'Deploy Splunk monitoring',
                status: 'QUEUED',
                selected: true,
                finding: { headline_finding: 'Splunk monitoring deployed', attention_state: 'INFORMATIONAL' },
              },
            ],
          },
          remediation_summary: { title: 'Remediation plan ready', steps_completed: 0, steps_total: 1 },
        }}
        onRunInvestigation={vi.fn()}
        onRunRemediation={onRunRemediation}
        onHilApprove={vi.fn()}
        onHilSkip={vi.fn()}
      />,
    );
    expect(screen.getByText(/Deploy Splunk monitoring/i)).toBeInTheDocument();
    expect(screen.getByText(/Review remediation plan/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Approve remediation/i })).toBeInTheDocument();
    expect(onRunRemediation).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Approve remediation/i }));
    expect(onRunRemediation).toHaveBeenCalledTimes(1);
    expect(onRunRemediation).toHaveBeenCalledWith(['deploy_monitoring']);
  });

  it('keeps rem execution progress inside the rem plan instead of jumping to the top', () => {
    const { container } = render(
      <EcAgentWorkflow
        workflow={{
          lifecycle: 'REMEDIATION_PLAN_READY',
          phase: 'remediation',
          remediation_plan: {
            visible: true,
            primary_cta: 'Approve remediation',
            steps: [{ id: 'notify_firewall', title: 'Notify SOC that monitoring is in place', status: 'QUEUED', selected: true }],
          },
          remediation_results: {
            header: 'Remediation plan',
            steps: [
              {
                id: 'notify_firewall',
                title: 'Notify SOC that monitoring is in place',
                status: 'QUEUED',
                selected: true,
                finding: { headline_finding: 'Draft pending send', attention_state: 'INFORMATIONAL' },
              },
            ],
          },
          remediation_summary: { title: 'Remediation plan ready', steps_completed: 0, steps_total: 1 },
        }}
        executionProgress={{
          header: 'Executing remediation',
          steps: [{ id: 'run', label: 'Apply selected actions', description: 'HIL drafts stay pending', durationMs: 400 }],
          activeStepIndex: 0,
          completedStepIds: [],
        }}
        onRunInvestigation={vi.fn()}
        onRunRemediation={vi.fn()}
        onHilApprove={vi.fn()}
        onHilSkip={vi.fn()}
      />,
    );
    const rem = container.querySelector('[data-ec-section="recommended-remediation"]');
    expect(rem?.querySelector('[data-ec-section="agent-execution-progress"]')).toBeTruthy();
    expect(container.querySelector('[data-ec-section="agent-workflow"] > [data-ec-section="agent-execution-progress"]')).toBeNull();
    expect(screen.queryByText(/Notify SOC that monitoring is in place/i)).not.toBeInTheDocument();
  });

  it('shows Email and Ticket on rem steps', () => {
    render(
      <EcInvestigationResultList
        variant="remediation"
        scenarioId="s1_governed_splunk_investigation"
        steps={[
          {
            id: 'notify_firewall',
            title: 'Notify SOC that 14-day monitoring is in place',
            status: 'QUEUED',
            finding: {
              headline_finding: 'SOC team notified',
              attention_state: 'INFORMATIONAL',
              details: {
                email_draft: {
                  to: 'FIREWALL_TEAM',
                  subject: '[SOC] 14-day monitoring in place',
                  body: 'Monitoring notice',
                },
              },
            },
          },
          {
            id: 'create_incident',
            title: 'Open incident with unexplained permitted-session evidence',
            status: 'QUEUED',
            finding: {
              headline_finding: 'Incident created · INC-2026-89412',
              attention_state: 'INFORMATIONAL',
              details: {
                ticket_detail: {
                  ticket_id: 'INC-2026-89412',
                  ticket_type: 'incident',
                  priority: 'P2',
                  title: 'Newly observed MCP endpoint',
                  status: 'CREATED',
                },
              },
            },
          },
        ]}
      />,
    );
    expect(screen.getByRole('button', { name: /Open email for Notify SOC/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open ticket for Open incident/i })).toBeInTheDocument();
  });

  it('keeps rem execute and rem-plan-ready on the rem plan section', () => {
    expect(agentLifecycleScrollTarget('REMEDIATION_PLAN_READY')).toBe(
      '[data-ec-section="recommended-remediation"]',
    );
    expect(agentLifecycleScrollTarget('REMEDIATING')).toBe('[data-ec-section="recommended-remediation"]');
    expect(agentLifecycleScrollTarget('INVESTIGATION_COMPLETE')).toBe('[data-ec-section="executive-summary"]');
    expect(agentLifecycleScrollTarget('COMPLETE')).toBe('[data-ec-section="executive-summary"]');
  });

  it('shows RESPONSE COMPLETE without dropping risk to LOW', () => {
    render(
      <EcAgentWorkflow
        workflow={{
          lifecycle: 'COMPLETE',
          phase: 'remediation',
          final_summary: {
            title: 'RESPONSE COMPLETE',
            headline: '14-day targeted monitoring active · malicious use not confirmed · blocking threshold not met',
            severity: 'P2',
            affected: '198.51.100.42',
            compromise: 'not confirmed',
            completed: ['Splunk monitoring deployed and verified', 'Incident INC-2026-89412 created', 'SOC notified'],
            deferred: ['IP block not required at current SOP threshold'],
            risk_from: 'MEDIUM',
            risk_to: 'MEDIUM',
            risk_note: 'Current risk: MEDIUM. Malicious use: NOT CONFIRMED. Monitoring: ACTIVE. Blocking: CONDITIONAL.',
          },
        }}
        onRunInvestigation={vi.fn()}
        onRunRemediation={vi.fn()}
        onHilApprove={vi.fn()}
        onHilSkip={vi.fn()}
      />,
    );
    expect(screen.getByText('RESPONSE COMPLETE')).toBeInTheDocument();
    expect(screen.getByText(/Monitoring: ACTIVE\. Blocking: CONDITIONAL/)).toBeInTheDocument();
    expect(screen.queryByText(/MEDIUM→LOW/i)).not.toBeInTheDocument();
    expect(screen.getByText(/IP block not required at current SOP threshold/i)).toBeInTheDocument();
  });

  it('shows ADDED BY AGENT with the permitted-session reason', () => {
    render(
      <EcInvestigationResultList
        steps={[
          {
            id: 'permitted_sessions',
            title: 'Investigate permitted sessions and authentication',
            status: 'COMPLETE',
            added_by_agent: true,
            reason:
              'Added because three permitted sessions reached a high-criticality jump host. Denied volume must not hide successful communication.',
            finding: {
              headline_finding: '3 permitted sessions remain unexplained; auth source IP not proven',
              attention_state: 'ATTENTION',
              details: {
                reasoning: {
                  label: 'Agent assessment',
                  trace_label: 'LLM interpretation — not evidence',
                  summary: 'Denied volume must not bury the permitted sessions.',
                  chain: ['LLM candidate', 'deterministic validation', 'normalized SPL', 'authorization', 'Splunk MCP', 'evidence'],
                },
              },
            },
          },
        ]}
      />,
    );
    expect(screen.getByText(/ADDED BY AGENT/i)).toBeInTheDocument();
    expect(screen.getByText(/high-criticality jump host/i)).toBeInTheDocument();
    expect(screen.queryByText(/require validation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Agent assessment/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'View trace ›' }));
    expect(screen.getByText(/LLM interpretation — not evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/LLM candidate → deterministic validation → normalized SPL → authorization → Splunk MCP → evidence/i)).toBeInTheDocument();
  });

  it('exposes View SPL and request/response behind expansion', () => {
    render(
      <EcInvestigationResultList
        steps={[
          {
            id: 'requested_30d',
            title: 'Investigate network activity — last 30 days',
            status: 'COMPLETE',
            finding: {
              headline_finding: 'Last 30 days: 3 allowed / 922 denied',
              attention_state: 'ATTENTION',
              details: {
                connector: 'Splunk MCP',
                normalized_spl: 'search index=pgcil_soc sourcetype=pgcil:firewall earliest=-30d latest=now',
                execution: 'AUTHORIZED → EXECUTED',
                request: 'action=splunk_run_query\nindicator=198.51.100.42',
                response: 'allow_count=3',
              },
            },
          },
        ]}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'View SPL ›' }));
    expect(screen.getByText('Normalized SPL')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'View request / response ›' }));
    expect(screen.getByText('Request')).toBeInTheDocument();
    expect(screen.getByText('Response')).toBeInTheDocument();
  });

  it('shows NOT REQUIRED for a conditional block that was not executed', () => {
    render(
      <EcInvestigationResultList
        variant="remediation"
        steps={[
          {
            id: 'prepare_block',
            title: 'Conditional IP block',
            status: 'NOT_REQUIRED',
            finding: {
              headline_finding: 'Conditional IP block · threshold not met',
              attention_state: 'NORMAL',
              details: {
                execution: 'EVALUATED → NOT_REQUIRED',
                request: 'action=Evaluate ip_block',
                response: 'decision=NOT_REQUIRED',
              },
            },
          },
        ]}
      />,
    );
    expect(screen.getByText('NOT_REQUIRED')).toBeInTheDocument();
    expect(screen.queryByText('PREPARED')).not.toBeInTheDocument();
    expect(screen.queryByText(/Plan step/i)).not.toBeInTheDocument();
  });
});
