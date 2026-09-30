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

  it('shows chunk-level retrieval detail and omits an empty headline', () => {
    const chunked: EcRagTracePayload = {
      ...trace,
      question: 'reported phishing email · user clicked link',
      excluded: [{ reason: 'superseded', count: 3, detail: 'SOC-SOP-PHISH-001 v2025.4 §3, replaced by v2026.3' }],
      excluded_total: 3,
      index: {
        embedding_model: 'BAAI/bge-m3',
        embedding_dims: 1024,
        sparse_method: 'BM25',
        reranker_model: 'BAAI/bge-reranker-v2-m3',
        documents: 41,
        chunks: 1286,
        chunking: 'section-aware, 512-token max, 64-token overlap',
      },
      funnel: {
        dense_candidates: 40,
        sparse_candidates: 40,
        fused: 58,
        fusion: 'reciprocal rank fusion (k=60)',
        excluded: 3,
        reranked: 8,
        rerank_threshold: 0.5,
        kept: 1,
        cited: 1,
      },
      passages: [
        {
          ...trace.passages[0],
          label: '[2]',
          chunk_id: 'SOC-SOP-PHISH-001@2026.3#c07',
          section: '§3.2 Contain the account',
          tokens: 212,
          scores: { dense: 0.861, dense_rank: 1, bm25: 15.4, bm25_rank: 1, rerank: 0.96 },
        },
      ],
      answer: { headline: '', sentences: [{ text: 'Reset the password.', citations: ['[2]'] }], gaps: [] },
    };
    const { container } = render(<EcRagTrace trace={chunked} />);
    expect(screen.getByText(/BAAI\/bge-m3 · 1024-d dense \+ BM25/)).toBeInTheDocument();
    expect(screen.getByText(/1,286 chunks from 41 approved documents/)).toBeInTheDocument();
    expect(screen.getByText('58 fused')).toBeInTheDocument();
    expect(screen.getByText('SOC-SOP-PHISH-001 v2025.4 §3, replaced by v2026.3')).toBeInTheDocument();
    expect(screen.getByText('SOC-SOP-PHISH-001@2026.3#c07')).toBeInTheDocument();
    expect(screen.getByText(/cosine 0\.861 \(#1\) · BM25 15\.4 \(#1\) · rerank 0\.96/)).toBeInTheDocument();
    expect(screen.getByText('Retrieved chunks')).toBeInTheDocument();
    expect(container.querySelector('[data-ec-section="rag-trace"] p.font-semibold.text-sm')).toBeNull();
  });
});
