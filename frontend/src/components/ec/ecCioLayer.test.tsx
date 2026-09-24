import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EcAgentWorkflow } from '@/components/ec/EcAgentWorkflow';
import { EcExecutiveBrief, EcStepWhy, EcStoryThreadBadge, EcToolFabric } from '@/components/ec/EcCioLayer';
import type { EcAgentWorkflowPayload } from '@/components/ec/types';
import { ExperienceExecutionProgressPanel } from '@/components/experience-center/ExperienceExecutionProgressPanel';
import * as scrollModule from '@/lib/scrollIntoScrollParent';

const baseWorkflow: EcAgentWorkflowPayload = {
  lifecycle: 'PLAN_READY',
  phase: 'plan',
  opening_narrative: 'My plan: two checks. Nothing runs until you approve.',
  investigation_plan: {
    editable: true,
    steps: [
      {
        id: 'inv_a',
        title: 'Check A',
        tools: ['Splunk MCP'],
        selected: true,
        rationale: 'A decides whether B matters.',
        decides: 'Escalate or not.',
        if_skipped: 'No verdict.',
      },
      { id: 'inv_b', title: 'Check B', tools: ['CMDB'], selected: true },
    ],
  },
  tool_fabric: [
    { tool_id: 'splunk_mcp', name: 'Splunk MCP', role: 'SIEM', kind: 'mcp', demo_fixture: true, used: true },
    { tool_id: 'agilus_mcp', name: 'Agilus MCP', role: 'Patch', kind: 'mcp', demo_fixture: true, used: false },
  ],
};

const noop = () => undefined;

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

describe('EC CIO layer', () => {
  it('shows a Why line only for steps that carry a rationale, with detail on demand', () => {
    renderWorkflow(baseWorkflow);
    expect(screen.getByText('A decides whether B matters.')).toBeInTheDocument();
    expect(document.querySelector('[data-ec-step-why="inv_b"]')).toBeNull();
    expect(screen.queryByText('Escalate or not.')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('A decides whether B matters.'));
    expect(screen.getByText('Escalate or not.')).toBeInTheDocument();
  });

  it('renders the tool fabric from the payload with used tools marked', () => {
    renderWorkflow(baseWorkflow);
    const used = document.querySelector('[data-ec-section="tool-fabric"] [data-tool-used="true"]');
    const unused = document.querySelector('[data-ec-section="tool-fabric"] [data-tool-used="false"]');
    expect(used?.textContent).toBe('Splunk MCP');
    expect(unused?.textContent).toBe('Agilus MCP');
  });

  it('renders the executive brief after investigation and on completion', () => {
    const brief = {
      verdict: 'Attack attempted and blocked.',
      risk_from: 'HIGH',
      risk_to: 'MEDIUM',
      decision_needed: 'Approve containment.',
    };
    const { rerender } = renderWorkflow({
      ...baseWorkflow,
      lifecycle: 'INVESTIGATION_COMPLETE',
      phase: 'investigation_complete',
      executive_brief: brief,
    });
    expect(document.querySelector('[data-ec-section="executive-brief"]')).not.toBeNull();
    expect(screen.getByText('Approve containment.')).toBeInTheDocument();
    rerender(
      <EcAgentWorkflow
        workflow={{ ...baseWorkflow, lifecycle: 'COMPLETE', phase: 'remediation', executive_brief: brief }}
        onRunInvestigation={noop}
        onRunRemediation={noop}
        onHilApprove={noop}
        onHilSkip={noop}
      />,
    );
    expect(document.querySelectorAll('[data-ec-section="executive-brief"]')).toHaveLength(1);
  });

  it('renders standalone components without optional fields', () => {
    render(<EcExecutiveBrief brief={{ verdict: 'Only a verdict.' }} />);
    expect(screen.getByText('Only a verdict.')).toBeInTheDocument();
    render(<EcStepWhy step={{ id: 'x', title: 'No reason' }} />);
    render(<EcToolFabric tools={[]} />);
  });

  it('renders the incident thread badge with the next question', () => {
    render(
      <EcStoryThreadBadge
        thread={{
          thread_id: 'INC-2026-89412',
          day: 0,
          total_days: 2,
          title: 'New IP seen — watch raised',
          verdict_so_far: 'MEDIUM',
          next: { scenario_id: 'q1', label: 'Day 1 — the watch fires' },
        }}
      />,
    );
    expect(screen.getByText(/Incident INC-2026-89412 · Day 0/)).toBeInTheDocument();
    expect(screen.getByText(/Day 1 — the watch fires/)).toBeInTheDocument();
  });
});

describe('EC scroll ownership', () => {
  it('EcAgentWorkflow never scrolls on lifecycle transitions (the workspace owns scrolling)', () => {
    const spy = vi.spyOn(scrollModule, 'scrollIntoScrollParent');
    vi.useFakeTimers();
    const { rerender } = renderWorkflow(baseWorkflow);
    for (const lifecycle of ['INVESTIGATION_COMPLETE', 'REMEDIATION_PLAN_READY', 'REMEDIATING', 'COMPLETE']) {
      rerender(
        <EcAgentWorkflow
          workflow={{ ...baseWorkflow, lifecycle, phase: lifecycle === 'INVESTIGATION_COMPLETE' ? 'investigation_complete' : 'remediation' }}
          onRunInvestigation={noop}
          onRunRemediation={noop}
          onHilApprove={noop}
          onHilSkip={noop}
        />,
      );
      vi.advanceTimersByTime(200);
    }
    expect(spy).not.toHaveBeenCalled();
    vi.useRealTimers();
    spy.mockRestore();
  });

  it('progress ticks never scroll the page, only the step list', () => {
    const pageScrollTo = vi.fn();
    const page = document.createElement('div');
    page.style.overflowY = 'auto';
    page.scrollTo = pageScrollTo as unknown as typeof page.scrollTo;
    document.body.appendChild(page);
    const steps = Array.from({ length: 6 }, (_, index) => ({
      id: `s${index}`,
      label: `Step ${index}`,
      description: '',
      durationMs: 10,
    }));
    const view = (active: number) => ({
      steps,
      activeStepIndex: active,
      completedStepIds: steps.slice(0, active).map((step) => step.id),
    });
    const { rerender } = render(<ExperienceExecutionProgressPanel state={view(0)} />, { container: page });
    for (let tick = 1; tick <= 5; tick += 1) {
      rerender(<ExperienceExecutionProgressPanel state={view(tick)} />);
    }
    expect(pageScrollTo).not.toHaveBeenCalled();
    page.remove();
  });
});
