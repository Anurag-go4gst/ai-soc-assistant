import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ChatBubble } from '@/components/ChatBubble';
import { ExperienceExecutionProgressPanel } from '@/components/experience-center/ExperienceExecutionProgressPanel';
import { buildInvestigationProgressSteps } from '@/lib/investigationProgress';
import { investigationProgressToExperienceView } from '@/lib/investigationProgressToExperience';
import {
  LEGACY_COORDINATION_STEP_ID,
  canSkipCoordinationAction,
  coordinationActionForScenario,
  createLegacyDemoCoordinationAction,
  injectLegacyCoordinationStep,
  markCoordinationWaiting,
  skipLegacyDemoCoordinationAction,
} from '@/lib/legacyDemoCoordination';
import { executeLegacyDemoCoordination } from '@/lib/legacyDemoEmail';
import { playLegacyDemoInvestigationWithCoordination } from '@/lib/legacyDemoCoordinationPlayer';
import type { ExperienceExecutionProgressView } from '@/lib/experienceCenterExecution';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const priorityScenarios = [
  'firewall_deny_coordinated_attack',
  'ir_containment_advisory_firewall_incident',
  'cert_in_ot_reporting_obligation',
  'guided_investigation_supply_chain',
] as const;

function stepsForScenario(scenarioId: string) {
  const skillMap: Record<string, { skill: string; sources: string[] }> = {
    firewall_deny_coordinated_attack: { skill: 'attack_discovery', sources: ['mcp:splunk', 'rag:sop'] },
    ir_containment_advisory_firewall_incident: { skill: 'knowledge_recall', sources: ['rag:sop'] },
    cert_in_ot_reporting_obligation: { skill: 'knowledge_recall', sources: ['rag:sop'] },
    guided_investigation_supply_chain: { skill: 'guided_investigation', sources: ['rag:sop'] },
  };
  const mapped = skillMap[scenarioId];
  return buildInvestigationProgressSteps({
    expectedSkill: mapped.skill,
    expectedSources: mapped.sources,
    demoMode: true,
  });
}

function coordinationView(
  scenarioId: (typeof priorityScenarios)[number],
  status: 'waiting_for_analyst' | 'completed' = 'waiting_for_analyst',
): ExperienceExecutionProgressView {
  const injected = injectLegacyCoordinationStep(stepsForScenario(scenarioId), scenarioId);
  const action = {
    ...createLegacyDemoCoordinationAction(scenarioId),
    ...(status === 'waiting_for_analyst' ? markCoordinationWaiting(createLegacyDemoCoordinationAction(scenarioId)) : {}),
    status,
    available: status === 'waiting_for_analyst',
    result_message: status === 'completed' ? 'Coordination verified (simulated).' : null,
  };
  return investigationProgressToExperienceView(
    {
      steps: injected.steps,
      activeStepIndex: injected.steps.findIndex((step) => step.id === LEGACY_COORDINATION_STEP_ID),
      completedStepIds: [],
      stepStatuses: { [LEGACY_COORDINATION_STEP_ID]: 'active' },
      stepDisplayText: { [LEGACY_COORDINATION_STEP_ID]: 'Waiting for analyst coordination decision…' },
    },
    true,
    action,
  );
}

describe('legacy demo coordination model', () => {
  it.each(priorityScenarios)('%s injects a coordination step after the narrative anchor', (scenarioId) => {
    const injected = injectLegacyCoordinationStep(stepsForScenario(scenarioId), scenarioId);
    expect(injected.action).not.toBeNull();
    expect(injected.steps.some((step) => step.id === LEGACY_COORDINATION_STEP_ID)).toBe(true);
    expect(injected.action?.hil_required).toBe(true);
    expect(canSkipCoordinationAction(injected.action!)).toBe(false);
  });

  it('does not inject coordination for non-priority legacy scenarios', () => {
    const injected = injectLegacyCoordinationStep(stepsForScenario('firewall_deny_coordinated_attack'), 'dns_beaconing_c2_hunt');
    expect(injected.action).toBeNull();
    expect(injected.steps.some((step) => step.id === LEGACY_COORDINATION_STEP_ID)).toBe(false);
  });

  it('mandatory HIL cannot be skipped via reducer', () => {
    const action = createLegacyDemoCoordinationAction('firewall_deny_coordinated_attack');
    expect(skipLegacyDemoCoordinationAction(action)).toBeNull();
  });

  it('resets coordination action per scenario identity', () => {
    const first = coordinationActionForScenario('firewall_deny_coordinated_attack');
    const second = coordinationActionForScenario('cert_in_ot_reporting_obligation');
    expect(first?.scenario_id).toBe('firewall_deny_coordinated_attack');
    expect(second?.scenario_id).toBe('cert_in_ot_reporting_obligation');
    expect(first?.delivery_mode).toBe('simulated');
    expect(second?.delivery_mode).toBe('email');
    expect(first?.action_id).not.toBe(second?.action_id);
  });
});

describe('ExperienceExecutionProgressPanel coordination UI', () => {
  it('firewall_deny_coordinated_attack shows HIL coordination without auto execution', () => {
    render(
      <ExperienceExecutionProgressPanel
        state={coordinationView('firewall_deny_coordinated_attack')}
        onCoordinationConfirm={() => undefined}
      />,
    );
    const panel = screen.getByTestId('legacy-demo-coordination-panel');
    expect(panel).toBeInTheDocument();
    expect(within(panel).getByText(/Prepare perimeter deny coordination/i)).toBeInTheDocument();
    expect(screen.queryByTestId('legacy-demo-coordination-skip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('legacy-demo-coordination-result')).not.toBeInTheDocument();
  });

  it('ir_containment_advisory_firewall_incident waits for analyst confirmation', () => {
    render(
      <ExperienceExecutionProgressPanel
        state={coordinationView('ir_containment_advisory_firewall_incident')}
        onCoordinationConfirm={() => undefined}
      />,
    );
    const panel = screen.getByTestId('legacy-demo-coordination-panel');
    expect(within(panel).getByText(/Confirm IR containment advisory/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Human confirmation required/i)).toBeInTheDocument();
  });

  it('cert_in_ot_reporting_obligation exposes email coordination draft', () => {
    render(
      <ExperienceExecutionProgressPanel
        state={coordinationView('cert_in_ot_reporting_obligation')}
        onCoordinationConfirm={() => undefined}
      />,
    );
    const panel = screen.getByTestId('legacy-demo-coordination-panel');
    expect(within(panel).getByText(/Coordinate CERT-In reporting stakeholders/i)).toBeInTheDocument();
    expect(within(panel).getByText(/allowlisted EC transport/i)).toBeInTheDocument();
    expect(within(panel).getByTestId('legacy-demo-coordination-confirm')).toHaveTextContent(/coordination email/i);
  });

  it('guided_investigation_supply_chain shows supplier follow-up only', () => {
    render(
      <ExperienceExecutionProgressPanel
        state={coordinationView('guided_investigation_supply_chain')}
        onCoordinationConfirm={() => undefined}
      />,
    );
    const panel = screen.getByTestId('legacy-demo-coordination-panel');
    expect(within(panel).getByText(/Request supplier security coordination/i)).toBeInTheDocument();
    expect(screen.queryByText(/Prepare perimeter deny coordination/i)).not.toBeInTheDocument();
  });

  it('demoMode=false path does not render coordination panel in live ChatBubble shell', () => {
    render(
      <ChatBubble
        message={{
          id: 'live-progress',
          role: 'assistant',
          content: 'Running',
          displayStage: 'progress',
          progressDemoMode: false,
          investigationProgress: {
            steps: [{ id: 'query', label: 'Understanding query', description: 'x', durationMs: 1 }],
            activeStepIndex: 0,
            completedStepIds: [],
          },
          coordinationAction: markCoordinationWaiting(createLegacyDemoCoordinationAction('firewall_deny_coordinated_attack')),
        }}
      />,
    );
    expect(screen.getByTestId('investigation-progress-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('legacy-demo-coordination-panel')).not.toBeInTheDocument();
  });

  it('confirm triggers callback and does not pre-complete before analyst action', async () => {
    const onConfirm = vi.fn();
    render(
      <ExperienceExecutionProgressPanel
        state={coordinationView('firewall_deny_coordinated_attack')}
        onCoordinationConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByTestId('legacy-demo-coordination-confirm'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('legacy-demo-coordination-result')).not.toBeInTheDocument();
  });
});

describe('legacy demo coordination player', () => {
  it('pauses progress until analyst confirms, then verifies before continuing', async () => {
    vi.useFakeTimers();
    const scenarioId = 'firewall_deny_coordinated_attack';
    const injected = injectLegacyCoordinationStep(stepsForScenario(scenarioId), scenarioId);
    const updates: Array<{ action: ReturnType<typeof markCoordinationWaiting> | null; waiting: boolean }> = [];
    let resolveAnalyst: ((decision: 'confirm' | 'skip') => void) | undefined;

    const playback = playLegacyDemoInvestigationWithCoordination(
      injected.steps.map((step) => ({ ...step, durationMs: step.id === LEGACY_COORDINATION_STEP_ID ? 0 : 5 })),
      ({ action }) => {
        updates.push({
          action,
          waiting: action?.status === 'waiting_for_analyst',
        });
      },
      {
        coordinationAction: injected.action,
        skipCompletion: true,
        executeCoordination: executeLegacyDemoCoordination,
        waitForAnalyst: () =>
          new Promise<'confirm' | 'skip'>((resolve) => {
            resolveAnalyst = resolve;
          }),
      },
    );

    await vi.advanceTimersByTimeAsync(2000);
    expect(updates.some((item) => item.waiting)).toBe(true);
    expect(resolveAnalyst).toBeTruthy();

    if (resolveAnalyst) resolveAnalyst('confirm');
    await vi.advanceTimersByTimeAsync(2000);
    await playback;

    const last = updates.at(-1);
    expect(last?.action?.status).toBe('completed');
    expect(last?.waiting).toBe(false);
  });

  it('does not auto-execute coordination without analyst input', async () => {
    vi.useFakeTimers();
    const scenarioId = 'ir_containment_advisory_firewall_incident';
    const injected = injectLegacyCoordinationStep(stepsForScenario(scenarioId), scenarioId);
    const statuses: string[] = [];

    const playback = playLegacyDemoInvestigationWithCoordination(
      injected.steps.map((step) => ({ ...step, durationMs: step.id === LEGACY_COORDINATION_STEP_ID ? 0 : 5 })),
      ({ action }) => {
        if (action) statuses.push(action.status);
      },
      {
        coordinationAction: injected.action,
        skipCompletion: true,
        executeCoordination: executeLegacyDemoCoordination,
        waitForAnalyst: () => new Promise(() => undefined),
      },
    );

    await vi.advanceTimersByTimeAsync(1500);
    expect(statuses).toContain('waiting_for_analyst');
    expect(statuses).not.toContain('completed');
    void playback;
  });
});
