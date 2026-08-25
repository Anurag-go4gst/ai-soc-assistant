import { describe, expect, it } from 'vitest';
import { formatAnalystNextAction, isWorkflowControlToken } from '@/lib/workflowNextAction';

describe('workflowNextAction', () => {
  it('maps BLOCK control tokens to process language', () => {
    expect(formatAnalystNextAction('BLOCK')).toBe('Unable to proceed — additional evidence required');
    expect(formatAnalystNextAction('blocked')).toBe('Unable to proceed — additional evidence required');
    expect(isWorkflowControlToken('BLOCK')).toBe(true);
  });

  it('passes through non-control recommendations', () => {
    expect(formatAnalystNextAction('request_operator_readiness')).toBe('request operator readiness');
    expect(isWorkflowControlToken('request_operator_readiness')).toBe(false);
  });
});
