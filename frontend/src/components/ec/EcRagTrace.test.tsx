import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EcRagTrace } from '@/components/ec/EcRagTrace';
import type { EcRagTrace as EcRagTracePayload } from '@/components/ec/types';

const trace: EcRagTracePayload = {
  question: 'What does our SOP require?',
  collections: ['SOC SOPs', 'Escalation matrix'],
  top_confidence: 0.94,
  excluded: [
    { reason: 'draft', count: 1 },
    { reason: 'expired', count: 1 },
  ],
  excluded_total: 2,
  passages: [
    {
      entry_id: 'a',
      label: 'AUTH-003',
      citation: 'SOP AUTH-003',
      doc_title: 'Auth Investigation SOP',
      doc_version: '1.0',
      approval_status: 'coe_reviewed',
      confidence: 0.94,
      excerpt: 'Review account criticality before escalation.',
      used: true,
      used_for: 'Answer: what to review',
    },
  ],
  answer: {
    headline: 'Escalate to Tier 2.',
    sentences: [{ text: 'Review the account first.', citations: ['AUTH-003'] }],
    gaps: ['A deadline for escalation.'],
  },
  governance: ['Only approved passages are eligible.'],
};

describe('EcRagTrace', () => {
  it('shows exclusions, cited sentences, passages and gaps', () => {
    render(<EcRagTrace trace={trace} />);
    expect(screen.getByText('How RAG answered this')).toBeInTheDocument();
    expect(screen.getByText(/1 draft, 1 expired/)).toBeInTheDocument();
    expect(screen.getByText('Review the account first.')).toBeInTheDocument();
    expect(screen.getByText('A deadline for escalation.', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('Review account criticality before escalation.')).toBeInTheDocument();
  });

  it('highlights the cited passage when its citation is focused', () => {
    render(<EcRagTrace trace={trace} />);
    const passage = document.querySelector('[data-ec-passage="AUTH-003"]') as HTMLElement;
    expect(passage.className).not.toContain('border-violet-300/70');
    fireEvent.mouseEnter(document.querySelector('[data-ec-citation="AUTH-003"]') as HTMLElement);
    expect(passage.className).toContain('border-violet-300/70');
  });
});
