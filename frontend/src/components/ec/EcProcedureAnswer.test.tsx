import { fireEvent, render, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EcProcedureAnswer } from '@/components/ec/EcProcedureAnswer';
import { EcRagTrace } from '@/components/ec/EcRagTrace';
import type { EcProcedureAnswer as EcProcedureAnswerPayload, EcRagTrace as EcRagTracePayload } from '@/components/ec/types';

const ref = (value: string, excerpt: string) => ({
  ref: value,
  doc_id: 'SOC-SOP-PHISH-001',
  section: `${value} Section`,
  excerpt,
});

const answer: EcProcedureAnswerPayload = {
  title: 'Phishing — user clicked a link',
  opening: 'r.mehta in Finance clicked a link in a reported phishing email. Contain the account now.',
  assessment: {
    incident_priority: 'P3',
    priority_rule: 'SOC-POL-PRIO-01 rule 3',
    priority_basis: 'Tier-2 asset',
    threat_assessment: 'Suspected',
  },
  documents: [
    { doc_id: 'SOC-SOP-PHISH-001', title: 'Phishing response procedure', version: '2026.3', approved_on: '12 Mar 2026' },
    { doc_id: 'SOC-ESC-MATRIX-01', title: 'SOC escalation matrix', version: '2026.1', approved_on: '20 Jan 2026' },
  ],
  phases: [
    {
      name: 'Contain',
      steps: [
        { text: 'Reset the password', owner: 'IAM', refs: [ref('3.2', 'Reset within 4 hours.')] },
        {
          text: 'Isolate the laptop',
          owner: 'Endpoint team',
          condition: 'only if a file was downloaded or ran',
          refs: [ref('3.5', 'Isolate only if a file ran.')],
        },
      ],
    },
    { name: 'Record and notify', steps: [{ text: 'Open an incident', owner: 'SOC Tier 1', refs: [ref('3.1', 'Open one.')] }] },
  ],
  escalation: {
    text: 'Escalate to Tier 2 if a password was entered',
    owner: 'SOC Tier 1',
    refs: [{ ref: 'PH-02', doc_id: 'SOC-ESC-MATRIX-01', section: 'PH-02 Phishing', excerpt: 'Tier 1 owns.' }],
  },
  retrieval_summary: '11 chunks · hybrid search · top match 0.96',
};

const trace: EcRagTracePayload = {
  question: 'reported phishing email',
  collections: ['SOC SOPs'],
  excluded: [],
  excluded_total: 0,
  passages: [],
  answer: { headline: '', sentences: [{ text: 'A sentence only the full panel shows.', citations: ['3.2'] }], gaps: ['No review date.'] },
};

describe('EcProcedureAnswer', () => {
  it('shows the opening, the dated source, numbered steps by phase, and the escalation rule', () => {
    const { container } = render(<EcProcedureAnswer answer={answer} trace={trace} />);
    const view = within(container);
    expect(view.getByText('Phishing — user clicked a link')).toBeInTheDocument();
    expect(view.getByText('P3')).toBeInTheDocument();
    expect(view.getByText(/Contain the account now/)).toBeInTheDocument();
    expect(view.getByText(/Phishing response procedure · v2026.3 · approved 12 Mar 2026/)).toBeInTheDocument();
    expect(view.getByText(/Also used: SOC escalation matrix v2026.1 \(20 Jan 2026\)/)).toBeInTheDocument();
    expect(view.getByText('— only if a file was downloaded or ran', { exact: false })).toBeInTheDocument();
    // Numbering runs straight through the phases.
    const numbers = [...container.querySelectorAll('[data-ec-procedure-step]')].map((node) =>
      node.getAttribute('data-ec-procedure-step'),
    );
    expect(numbers).toEqual(['1', '2', '3']);
    expect(view.getByText('Escalate to Tier 2 if a password was entered')).toBeInTheDocument();
    expect(container.textContent).not.toContain('§');
  });

  it('reveals a section excerpt when its reference is clicked', () => {
    const { container } = render(<EcProcedureAnswer answer={answer} trace={trace} />);
    expect(container.querySelector('[data-ec-excerpt="3.2"]')).toBeNull();
    fireEvent.click(container.querySelector('[data-ec-ref="3.2"]') as HTMLElement);
    expect(container.querySelector('[data-ec-excerpt="3.2"]')?.textContent).toContain('Reset within 4 hours.');
    fireEvent.click(container.querySelector('[data-ec-ref="3.2"]') as HTMLElement);
    expect(container.querySelector('[data-ec-excerpt="3.2"]')).toBeNull();
  });

  it('keeps retrieval detail collapsed and does not repeat the answer inside it', () => {
    const { container } = render(<EcProcedureAnswer answer={answer} trace={trace} />);
    const details = container.querySelector('[data-ec-section="procedure-retrieval"]') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(details.textContent).toContain('How this was found — 11 chunks · hybrid search · top match 0.96');
    expect(details.textContent).not.toContain('A sentence only the full panel shows.');
    expect(details.textContent).toContain('No review date.');
  });
});

describe('EcProcedureAnswer after approval', () => {
  const done: EcProcedureAnswerPayload = {
    ...answer,
    phases: [
      {
        name: 'Contain',
        steps: [
          {
            ...answer.phases[0].steps[0],
            status: 'requested',
            status_label: 'Requested',
            ticket: { number: 'TASK0019263', type: 'Request', state: 'Open', assignment_group: 'IAM' } as never,
          },
          { ...answer.phases[0].steps[1], status: 'conditional', status_label: 'Only if needed' },
        ],
      },
      { name: 'Record and notify', steps: [{ ...answer.phases[1].steps[0], status: 'done', status_label: 'Done' }] },
    ],
    progress_summary: { done: ['incident'], requested: ['password reset'], pending: ['find other recipients'] },
  };

  it('highlights the key message', () => {
    const { container } = render(<EcProcedureAnswer answer={answer} trace={trace} />);
    const key = container.querySelector('[data-ec-section="procedure-key-message"]');
    expect(key?.textContent).toContain('Contain the account now.');
  });

  it('shows each step status, its record, and what is done and pending', () => {
    const { container } = render(
      <EcProcedureAnswer
        answer={done}
        trace={trace}
        outcome={{ title: 'OPEN — AWAITING USER REPLY', in_progress: ["r.mehta's reply"], risk_note: 'Escalate if shared.' }}
      />,
    );
    const statuses = [...container.querySelectorAll('[data-ec-step-status]')].map((node) => node.textContent);
    expect(statuses).toEqual(['Requested', 'Only if needed', 'Done']);
    expect(within(container).getByText('View ticket')).toBeInTheDocument();
    const summary = container.querySelector('[data-ec-section="procedure-summary"]') as HTMLElement;
    expect(summary.textContent).toContain('OPEN — AWAITING USER REPLY');
    expect(summary.textContent).toContain('Done: incident');
    expect(summary.textContent).toContain('Requested: password reset');
    expect(summary.textContent).toContain('Pending: find other recipients');
    expect(summary.textContent).toContain("Waiting on: r.mehta's reply");
  });

  it('shows no status before approval', () => {
    const { container } = render(<EcProcedureAnswer answer={answer} trace={trace} />);
    expect(container.querySelector('[data-ec-step-status]')).toBeNull();
    expect(container.querySelector('[data-ec-section="procedure-summary"]')).toBeNull();
  });
});

describe('EcRagTrace showAnswer', () => {
  it('still renders the answer sentences by default', () => {
    const { container } = render(<EcRagTrace trace={trace} />);
    expect(container.textContent).toContain('A sentence only the full panel shows.');
  });
});
