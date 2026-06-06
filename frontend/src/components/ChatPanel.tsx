import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { runDemoScenario } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatBubble, type SocChatMessage } from './ChatBubble';
import { ChatInput } from './ChatInput';
import { DemoScenarioPicker } from './DemoScenarioPicker';
import { StarterPrompts } from './StarterPrompts';
import { cn } from '@/lib/utils';
import { isClearChatCommand } from '@/lib/chatCommands';
import {
  type ChatProgressEvent,
  FINALIZATION_STATUS_LINES,
  finalizationLineForTier,
  formatChatStreamError,
  isFinalizationStage,
  streamChatMessage,
} from '@/lib/chatProgressStream';
import {
  applyServerProgressStage,
  buildInvestigationProgressSteps,
  delay,
  playInvestigationProgress,
  type InvestigationProgressError,
  type InvestigationProgressState,
} from '@/lib/investigationProgress';
import type { DemoScenarioSummary, PlaceholderResponse } from '@/types/api';

interface ChatPanelProps {
  onTrace?: (response: PlaceholderResponse) => void;
  onClear?: () => void;
  title?: string;
  compactHeader?: boolean;
  flush?: boolean;
}

function assistantMessageFromResponse(response: PlaceholderResponse): Omit<SocChatMessage, 'id' | 'role'> {
  return {
    content: response.message,
    traceId: response.trace_id,
    note: response.note,
    trace: response,
    routing: {
      selectedSkill: response.selected_skill,
      confidence: response.confidence,
      toolPlan: response.tool_plan,
      disagreement: response.disagreement,
      disagreementReason: response.disagreement_reason,
    },
    workflowPlan: response.workflow_plan,
    candidateSpl: response.candidate_spl,
    splValidation: response.spl_validation,
    execution: response.execution,
    humanReview: response.human_review,
  };
}

export function ChatPanel({ onTrace, onClear, title = 'Investigation Workspace', compactHeader = false, flush = false }: ChatPanelProps) {
  const welcome = useMemo<SocChatMessage>(
    () => ({
      id: 'welcome',
      role: 'assistant',
      content:
        'Hi Anurag. I am V.AI SOC. Choose a starter prompt or ask for triage, SPL, MITRE mapping, or investigation notes.',
    }),
    [],
  );
  const [messages, setMessages] = useState<SocChatMessage[]>([welcome]);
  const [loading, setLoading] = useState(false);
  const investigationEpochRef = useRef(0);
  const lastUserMessageRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(
    typeof window !== 'undefined' ? window.sessionStorage.getItem('ai_soc_session_id') : null,
  );

  const conversationStarted = messages.some((message) => message.role === 'user');

  const isStaleInvestigation = (epoch: number) => epoch !== investigationEpochRef.current;

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!last) return;

    const scrollTo = (selector: string, block: ScrollLogicalPosition) => {
      requestAnimationFrame(() => {
        document.querySelector(selector)?.scrollIntoView({ behavior: 'smooth', block, inline: 'nearest' });
      });
    };

    if (last.role === 'user') {
      scrollTo(`[data-message-id="${last.id}"]`, 'end');
      return;
    }
    if (last.displayStage === 'progress') {
      scrollTo(`[data-message-id="${last.id}"]`, 'start');
      return;
    }
    if (last.displayStage === 'summary' || last.displayStage === 'complete') {
      scrollTo(`[data-answer-scroll-anchor="${last.id}"]`, 'start');
    }
  }, [messages]);

  const updateProgressMessage = (
    progressId: string,
    epoch: number,
    investigationProgress: InvestigationProgressState,
  ) => {
    if (isStaleInvestigation(epoch)) return;
    setMessages((current) =>
      current.map((message) =>
        message.id === progressId ? { ...message, investigationProgress } : message,
      ),
    );
  };

  const applyChatProgressEvent = (
    base: InvestigationProgressState,
    event: ChatProgressEvent,
  ): InvestigationProgressState => {
    if (event.type === 'llm_degraded') {
      return {
        ...base,
        llmWarning: {
          message: event.message ?? event.label,
          code: event.code ?? null,
        },
        finalization: {
          phase: 'finalizing',
          statusLine: event.message ?? 'Live LLM unavailable; finishing with deterministic answer…',
          timeoutTier: base.finalization?.timeoutTier ?? 0,
          partialFallback: false,
          currentServerStage: event.stage,
          mcpDetail: base.finalization?.mcpDetail,
          showRetryHint: false,
        },
      };
    }
    if (event.type === 'heartbeat') {
      const tier = base.finalization?.timeoutTier ?? 0;
      return {
        ...base,
        finalization: {
          phase: 'finalizing',
          statusLine: event.label || FINALIZATION_STATUS_LINES.heartbeat,
          timeoutTier: tier,
          partialFallback: false,
          currentServerStage: event.stage,
          mcpDetail: base.finalization?.mcpDetail,
          showRetryHint: base.finalization?.showRetryHint ?? false,
        },
      };
    }
    let next = applyServerProgressStage(base, event.stage, event.detail);
    if (isFinalizationStage(event.stage)) {
      const tier = next.finalization?.timeoutTier ?? 0;
      next = {
        ...next,
        activeStepIndex: next.steps.length,
        completedStepIds: next.steps.map((step) => step.id),
        finalization: {
          phase: event.type === 'partial_timeout' ? 'partial' : 'finalizing',
          statusLine: finalizationLineForTier(tier, event.stage),
          timeoutTier: tier,
          partialFallback: event.type === 'partial_timeout',
          currentServerStage: event.stage,
          mcpDetail: event.stage === 'checking_mcp' ? event.detail ?? next.finalization?.mcpDetail : next.finalization?.mcpDetail,
          showRetryHint: tier >= 3 || event.type === 'partial_timeout',
        },
      };
    } else if (event.stage === 'checking_mcp' && event.detail) {
      next = {
        ...next,
        finalization: {
          phase: next.finalization?.phase ?? 'deterministic',
          statusLine: next.finalization?.statusLine ?? 'Checking MCP…',
          timeoutTier: next.finalization?.timeoutTier ?? 0,
          partialFallback: false,
          mcpDetail: event.detail,
          showRetryHint: false,
        },
      };
    }
    return next;
  };

  const startFinalizationTimers = (
    progressId: string,
    epoch: number,
    getState: () => InvestigationProgressState | undefined,
  ) => {
    const tiers: Array<{ ms: number; tier: 1 | 2 | 3 }> = [
      { ms: 10_000, tier: 1 },
      { ms: 25_000, tier: 2 },
      { ms: 45_000, tier: 3 },
    ];
    const timers = tiers.map(({ ms, tier }) =>
      window.setTimeout(() => {
        const current = getState();
        if (!current?.finalization || current.finalization.phase === 'complete') return;
        updateProgressMessage(progressId, epoch, {
          ...current,
          finalization: {
            ...current.finalization,
            phase: tier >= 3 ? 'partial' : 'finalizing',
            timeoutTier: tier,
            statusLine: finalizationLineForTier(tier, current.finalization.currentServerStage as ChatProgressEvent['stage'] | undefined),
            showRetryHint: tier >= 3,
          },
        });
      }, ms),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  };

  const failInvestigation = (
    progressId: string,
    epoch: number,
    error: InvestigationProgressError,
    snapshot?: InvestigationProgressState,
  ) => {
    if (isStaleInvestigation(epoch)) return;
    const base = snapshot ?? {
      steps: [],
      activeStepIndex: 0,
      completedStepIds: [],
    };
    updateProgressMessage(progressId, epoch, {
      ...base,
      error,
      finalization: { ...base.finalization, phase: 'error', statusLine: error.message, timeoutTier: 0, partialFallback: false, showRetryHint: Boolean(error.recoverable) },
    });
    toast.error(error.message);
  };

  const finishInvestigation = async (
    progressId: string,
    epoch: number,
    response: PlaceholderResponse,
  ) => {
    if (isStaleInvestigation(epoch)) return;
    if (response.session_context_status?.session_id) {
      sessionIdRef.current = response.session_context_status.session_id;
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem('ai_soc_session_id', response.session_context_status.session_id);
      }
    }
    onTrace?.(response);
    if (response.synthesis_status?.status === 'degraded' && response.synthesis_status.reason) {
      toast.warning(response.synthesis_status.reason, { duration: 10_000 });
    }
    const payload = assistantMessageFromResponse(response);
    setMessages((current) =>
      current.map((message) =>
        message.id === progressId
          ? {
              id: response.trace_id,
              role: 'assistant',
              displayStage: 'summary',
              investigationProgress: undefined,
              ...payload,
            }
          : message,
      ),
    );
    await delay(550);
    if (isStaleInvestigation(epoch)) return;
    setMessages((current) =>
      current.map((message) =>
        message.id === response.trace_id ? { ...message, displayStage: 'complete' } : message,
      ),
    );
  };

  const runStagedInvestigation = async (options: {
    fetcher?: () => Promise<PlaceholderResponse>;
    expectedSkill?: string | null;
    expectedSources?: string[];
    demoMode: boolean;
    userMessage?: string;
  }) => {
    const epoch = investigationEpochRef.current;
    const progressId = `progress-${crypto.randomUUID()}`;
    const { demoMode, fetcher, userMessage } = options;
    const steps = buildInvestigationProgressSteps({
      expectedSkill: options.expectedSkill,
      expectedSources: options.expectedSources,
      demoMode,
    });
    let progressSnapshot: InvestigationProgressState = {
      steps,
      activeStepIndex: 0,
      completedStepIds: [],
    };

    setMessages((current) => [
      ...current,
      {
        id: progressId,
        role: 'assistant',
        content: 'Running governed investigation pipeline…',
        displayStage: 'progress',
        investigationProgress: progressSnapshot,
        progressDemoMode: demoMode,
      },
    ]);
    setLoading(true);

    try {
      if (!demoMode && userMessage) {
        let clearFinalizationTimers: (() => void) | undefined;
        const response = await streamChatMessage(
          userMessage,
          (event) => {
          if (
            event.type === 'progress' ||
            event.type === 'heartbeat' ||
            event.type === 'llm_degraded' ||
            event.type === 'partial_timeout'
          ) {
            if (event.stage === 'generating_answer' && !clearFinalizationTimers) {
              clearFinalizationTimers = startFinalizationTimers(progressId, epoch, () => progressSnapshot);
            }
            progressSnapshot = applyChatProgressEvent(progressSnapshot, event);
            updateProgressMessage(progressId, epoch, progressSnapshot);
          }
          if (event.type === 'failed') {
            throw new Error(event.message ?? 'Chat stream failed');
          }
          },
          undefined,
          sessionIdRef.current,
        );
        clearFinalizationTimers?.();
        await finishInvestigation(progressId, epoch, response);
        return;
      }

      if (!fetcher) {
        throw new Error('Demo investigation requires a fetcher');
      }
      const fetchPromise = fetcher();
      await playInvestigationProgress(
        steps,
        (investigationProgress) => {
          progressSnapshot = investigationProgress;
          updateProgressMessage(progressId, epoch, investigationProgress);
        },
        { skipCompletion: true },
      );
      let clearTimers: (() => void) | undefined;
      clearTimers = startFinalizationTimers(progressId, epoch, () => progressSnapshot);
      const response = await fetchPromise;
      clearTimers();
      await finishInvestigation(progressId, epoch, response);
    } catch (error) {
      if (!isStaleInvestigation(epoch)) {
        const message = formatChatStreamError(error);
        const httpMatch =
          error instanceof Error ? error.message.match(/Chat stream failed:?\s*(\d+)/) : null;
        const code = httpMatch ? `http_${httpMatch[1]}` : null;
        failInvestigation(
          progressId,
          epoch,
          { message, code, recoverable: true },
          progressSnapshot,
        );
      }
    } finally {
      if (!isStaleInvestigation(epoch)) {
        setLoading(false);
      }
    }
  };

  const handleClear = useCallback(() => {
    investigationEpochRef.current += 1;
    setLoading(false);
    sessionIdRef.current = null;
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem('ai_soc_session_id');
    }
    setMessages([welcome]);
    onClear?.();
  }, [onClear, welcome]);

  const handleSend = async (message: string) => {
    if (isClearChatCommand(message)) {
      handleClear();
      return;
    }
    const userMessage: SocChatMessage = { id: crypto.randomUUID(), role: 'user', content: message };
    lastUserMessageRef.current = message;
    setMessages((current) => [...current, userMessage]);
    await runStagedInvestigation({ demoMode: false, userMessage: message });
  };

  const handleRunDemo = async (scenario: DemoScenarioSummary) => {
    const userMessage: SocChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: scenario.query,
    };
    setMessages((current) => [...current, userMessage]);
    await runStagedInvestigation({
      fetcher: () => runDemoScenario(scenario.scenario_id),
      expectedSkill: scenario.expected_skill,
      expectedSources: scenario.expected_sources,
      demoMode: true,
    });
  };

  return (
    <Card
      className={cn(
        'flex h-full min-h-0 flex-col overflow-hidden',
        flush ? 'rounded-none border-0 bg-transparent shadow-none' : 'soc-panel',
      )}
    >
      <CardHeader className={compactHeader ? 'border-b border-slate-800/70 py-3' : 'border-b border-slate-800/70'}>
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
        {!conversationStarted ? (
          <>
            <StarterPrompts disabled={loading} onPick={handleSend} />
            <DemoScenarioPicker disabled={loading} onRun={handleRunDemo} />
          </>
        ) : null}
      </CardHeader>
      <CardContent className="min-h-0 flex-1 p-0">
        <ScrollArea className="h-full">
          <div className="space-y-4 px-5 pb-8 pt-4">
            {messages.map((message) => (
              <ChatBubble
                key={message.id}
                message={message}
                onRetryFinalSynthesis={
                  message.displayStage === 'progress' && lastUserMessageRef.current
                    ? () => {
                        if (lastUserMessageRef.current) {
                          void handleSend(lastUserMessageRef.current);
                        }
                      }
                    : undefined
                }
              />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
      <ChatInput disabled={loading} onClear={handleClear} onSend={handleSend} />
    </Card>
  );
}
