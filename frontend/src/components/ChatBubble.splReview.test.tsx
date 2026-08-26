import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ChatBubble } from '@/components/ChatBubble';

afterEach(() => cleanup());

describe('ChatBubble candidate SPL review', () => {
  it('shows rejected candidate SPL with the fail-closed reason and no execution claim', () => {
    render(
      <ChatBubble
        message={{
          id: 'spl-review',
          role: 'assistant',
          content: 'Candidate SPL is not executable.',
          candidateSpl: {
            trace_id: 't-spl-1',
            skill: 'spl_generation',
            user_query: 'rolling failed logins',
            candidate_spl: 'search index=auth | head 100',
            generation_mode: 'utility_llm_spl_draft',
            confidence: 0.4,
            assumptions: [],
            warnings: [],
          },
          splValidation: {
            approved: false,
            normalized_spl: null,
            reject_reasons: ['semantic_fidelity_unresolved'],
            warnings: [],
            enforced_limits: {},
            policy_version: 'spl_policy_v1',
          },
        }}
      />,
    );
    expect(screen.getByText('candidate SPL')).toBeInTheDocument();
    expect(screen.getByText('rejected')).toBeInTheDocument();
    expect(screen.getByText('semantic_fidelity_unresolved')).toBeInTheDocument();
    expect(screen.getByText(/MCP execution is disabled/i)).toBeInTheDocument();
    expect(screen.queryByText(/executed/i)).not.toBeInTheDocument();
  });
});
