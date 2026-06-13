import { sendChatMessage } from '@/api/client';
import { getApiBaseUrl } from '@/lib/runtimeMode';
import type { ChatExecutionReviewOptions, PlaceholderResponse } from '@/types/api';

export type ChatProgressStage =
  | 'queued'
  | 'understanding_query'
  | 'classifying_intent'
  | 'planning_evidence'
  | 'route_adjudication'
  | 'retrieving_knowledge'
  | 'generating_spl'
  | 'checking_mcp'
  | 'mapping_mitre'
  | 'checking_sufficiency'
  | 'generating_answer'
  | 'validating_answer'
  | 'completed'
  | 'partial_timeout'
  | 'failed';

export type ChatProgressEventType =
  | 'progress'
  | 'heartbeat'
  | 'final'
  | 'partial_timeout'
  | 'llm_degraded'
  | 'failed';

export interface ChatProgressEvent {
  type: ChatProgressEventType;
  stage: ChatProgressStage;
  label: string;
  detail?: string;
  message?: string;
  reason?: string;
  code?: string;
  recoverable?: boolean;
  response?: PlaceholderResponse;
}

export function formatChatStreamError(error: unknown): string {
  if (error instanceof TypeError && /fetch/i.test(error.message)) {
    return 'Lost connection to the AI SOC backend. Check that the API is running and your session is still valid.';
  }
  if (error instanceof Error) {
    const text = error.message;
    if (text.includes('Chat stream ended without a final response')) {
      return 'The investigation stream stopped before a final answer arrived (network drop or server restart). Try again.';
    }
    if (text.startsWith('Chat stream failed:')) {
      const status = text.replace('Chat stream failed:', '').trim();
      if (status === '105') {
        return 'The server returned HTTP 105. This is often a proxy/upstream issue—retry, or check nginx and the backend logs.';
      }
      return `Investigation request failed (HTTP ${status}).`;
    }
    return text;
  }
  return 'Investigation request failed.';
}

const FINALIZATION_STAGES: ReadonlySet<ChatProgressStage> = new Set([
  'generating_answer',
  'validating_answer',
]);

export function isFinalizationStage(stage: ChatProgressStage): boolean {
  return FINALIZATION_STAGES.has(stage);
}

export const FINALIZATION_STATUS_LINES = {
  initial: 'Generating final answer…',
  heartbeat: 'Still working on the final answer…',
  validating: 'Validating answer safety and evidence grounding…',
  timeout10:
    'This is taking slightly longer because live LLM synthesis is running.',
  timeout25:
    'Still working. Evidence checks are complete; final answer is being generated.',
  timeout45Partial: 'Final synthesis is taking longer than expected. You can retry or review the validated plan below.',
} as const;

export type FinalizationTimeoutTier = 0 | 1 | 2 | 3;

export function finalizationLineForTier(tier: FinalizationTimeoutTier, stage?: ChatProgressStage): string {
  if (tier >= 3) return FINALIZATION_STATUS_LINES.timeout45Partial;
  if (tier >= 2) return FINALIZATION_STATUS_LINES.timeout25;
  if (tier >= 1) return FINALIZATION_STATUS_LINES.timeout10;
  if (stage === 'validating_answer') return FINALIZATION_STATUS_LINES.validating;
  return FINALIZATION_STATUS_LINES.initial;
}

function parseSseChunk(buffer: string): { events: ChatProgressEvent[]; rest: string } {
  const events: ChatProgressEvent[] = [];
  const parts = buffer.split('\n\n');
  const rest = parts.pop() ?? '';
  for (const part of parts) {
    const line = part
      .split('\n')
      .find((row) => row.startsWith('data:'));
    if (!line) continue;
    const payload = line.slice(5).trim();
    if (!payload) continue;
    try {
      events.push(JSON.parse(payload) as ChatProgressEvent);
    } catch {
      // ignore malformed frames
    }
  }
  return { events, rest };
}

export async function streamChatMessage(
  message: string,
  onEvent: (event: ChatProgressEvent) => void,
  signal?: AbortSignal,
  sessionId?: string | null,
  llmSplDraftMode = false,
  executionReview?: ChatExecutionReviewOptions,
): Promise<PlaceholderResponse> {
  const response = await fetch(`${getApiBaseUrl()}/chat/stream`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      ...(sessionId ? { session_id: sessionId } : {}),
      ...(llmSplDraftMode ? { llm_spl_draft_mode: true } : {}),
      ...(executionReview ?? {}),
    }),
    signal,
  });
  if (!response.ok) {
    let detail = '';
    try {
      const body = (await response.json()) as { detail?: string | { msg?: string } };
      if (typeof body.detail === 'string') {
        detail = body.detail;
      } else if (body.detail && typeof body.detail === 'object' && 'msg' in body.detail) {
        detail = String(body.detail.msg);
      }
    } catch {
      try {
        detail = (await response.text()).slice(0, 240);
      } catch {
        detail = '';
      }
    }
    throw new Error(
      detail
        ? `Chat stream failed (${response.status}): ${detail}`
        : `Chat stream failed: ${response.status}`,
    );
  }
  if (!response.body) {
    throw new Error('Chat stream returned no body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let lastResponse: PlaceholderResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseChunk(buffer);
    buffer = parsed.rest;
    for (const event of parsed.events) {
      onEvent(event);
      if ((event.type === 'final' || event.type === 'partial_timeout') && event.response) {
        lastResponse = event.response;
      }
      if (event.type === 'failed') {
        throw new Error(event.message ?? 'Chat stream failed');
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseChunk(`${buffer}\n\n`);
    for (const event of parsed.events) {
      onEvent(event);
      if ((event.type === 'final' || event.type === 'partial_timeout') && event.response) {
        lastResponse = event.response;
      }
    }
  }

  if (!lastResponse) {
    try {
      return await sendChatMessage(message, sessionId, llmSplDraftMode, executionReview);
    } catch (fallbackError) {
      const hint =
        fallbackError instanceof Error ? fallbackError.message : 'non-stream request also failed';
      throw new Error(
        `Chat stream ended before the final answer arrived (the connection may have been cut early). Fallback request failed: ${hint}`,
      );
    }
  }
  return lastResponse;
}
