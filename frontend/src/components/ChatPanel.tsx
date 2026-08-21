import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { runDemoScenario } from '@/api/client';
import { FlaskConical } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
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
  applyStageLatencies,
  buildInvestigationProgressSteps,
  delay,
  type InvestigationProgressError,
  type InvestigationProgressState,
  type InvestigationProgressStepStatus,
} from '@/lib/investigationProgress';
import {
  injectLegacyCoordinationStep,
  type LegacyDemoCoordinationAction,
} from '@/lib/legacyDemoCoordination';
import { playLegacyDemoInvestigationWithCoordination } from '@/lib/legacyDemoCoordinationPlayer';
import { executeLegacyDemoCoordination } from '@/lib/legacyDemoEmail';
import type { ChatExecutionReviewOptions, ChatInvestigationReviewOptions, ChatRemediationReviewOptions, ChatReviewOptions, DemoScenarioSummary, PlaceholderResponse } from '@/types/api';

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
  const [llmSplDraftMode, setLlmSplDraftMode] = useState(false);
  const investigationEpochRef = useRef(0);
  const coordinationWaitRef = useRef<{
    progressId: string | null;
    resolve: ((decision: 'confirm' | 'skip') => void) | null;
  }>({ progressId: null, resolve: null });
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
    coordinationAction?: LegacyDemoCoordinationAction | null,
  ) => {
    if (isStaleInvestigation(epoch)) return;
    setMessages((current) =>
      current.map((message) =>
        message.id === progressId
          ? {
              ...message,
              investigationProgress,
              coordinationAction: coordinationAction ?? message.coordinationAction ?? null,
            }
          : message,
      ),
    );
  };

  const applyChatProgressEvent = (
    base: InvestigationProgressState,
    event: ChatProgressEvent,
  ): InvestigationProgressState => {
    if (event.type === 'llm_degraded') {
      const stepStatuses = {
        ...(base.stepStatuses ?? initialStepStatuses(base.steps)),
        llm_governance: 'fallback' as InvestigationProgressStepStatus,
      };
      const stepDisplayText = {
        ...(base.stepDisplayText ?? {}),
        llm_governance: event.message ?? 'Using governed deterministic answer while LLM narration is unavailable.',
      };
      return {
        ...base,
        stepStatuses,
        stepDisplayText,
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

  const initialStepStatuses = (steps: InvestigationProgressState['steps']): Record<string, InvestigationProgressStepStatus> =>
    Object.fromEntries(steps.map((step) => [step.id, 'pending' as InvestigationProgressStepStatus]));

  const composerFallbackReason = (response: PlaceholderResponse): string | null => {
    const composer = response.control_plane_trace?.llm_composer as
      | { llm_blocked_reason?: string | null; provider_skip_reason?: string | null; llm_guard_status?: string | null }
      | undefined;
    return composer?.llm_blocked_reason ?? composer?.provider_skip_reason ?? composer?.llm_guard_status ?? null;
  };

  const settleProgressFromResponse = (
    snapshot: InvestigationProgressState,
    response: PlaceholderResponse,
  ): InvestigationProgressState => {
    const statuses = { ...initialStepStatuses(snapshot.steps), ...(snapshot.stepStatuses ?? {}) };
    const text = { ...(snapshot.stepDisplayText ?? {}) };
    for (const step of snapshot.steps) {
      if (statuses[step.id] === 'active') statuses[step.id] = 'completed';
    }
    if (!response.candidate_spl && !response.spl_validation && !response.spl_draft_preview && !response.llm_spl_candidate) {
      statuses.spl_evidence = statuses.spl_evidence === 'completed' ? 'completed' : 'skipped';
      text.spl_evidence = 'No governed SPL preparation was required for this response.';
    } else {
      statuses.spl_evidence = 'completed';
      text.spl_evidence = 'Prepared governed SPL / evidence path for review.';
    }
    if (!response.execution) {
      statuses.mcp_gate = 'skipped';
      text.mcp_gate = 'MCP execution was not required for this response.';
    } else if (response.human_review?.required && response.execution.status !== 'skipped') {
      statuses.mcp_gate = 'blocked';
      text.mcp_gate = 'MCP execution remains blocked by policy / review gate.';
    } else {
      statuses.mcp_gate = statuses.mcp_gate === 'blocked' ? 'blocked' : 'completed';
      text.mcp_gate = 'MCP gate checked; no live execution is implied.';
    }
    if (response.source_evidence?.some((item) => item.source_type === 'rag')) {
      statuses.rag = 'completed';
      text.rag = 'Retrieved governed SOC knowledge.';
    } else {
      statuses.rag = statuses.rag === 'completed' ? 'completed' : 'skipped';
      text.rag = 'SOC knowledge retrieval was not required or returned no approved match.';
    }
    statuses.mitre_severity = response.mitre_decision || response.severity_decision || response.context_sufficiency ? 'completed' : 'skipped';
    const packagingStatus = response.response_packaging_status;
    if (packagingStatus === 'blocked_review_required') {
      statuses.llm_governance = statuses.llm_governance === 'completed' ? 'completed' : 'skipped';
      statuses.package = 'blocked';
      text.package = response.human_review?.safe_message_for_user ?? 'Blocked pending analyst review.';
    } else if (packagingStatus === 'deterministic_fallback' || packagingStatus === 'llm_timeout') {
      statuses.llm_governance = 'fallback';
      statuses.package = 'completed';
      text.llm_governance = composerFallbackReason(response)
        ? `Using governed deterministic answer while LLM narration is unavailable: ${composerFallbackReason(response)}.`
        : 'Using governed deterministic answer while LLM narration is unavailable.';
    } else if (packagingStatus === 'llm_skipped') {
      statuses.llm_governance = 'skipped';
      statuses.package = 'completed';
      text.llm_governance = 'LLM narration skipped; using governed deterministic answer.';
    } else {
      statuses.llm_governance = statuses.llm_governance === 'skipped' ? 'skipped' : 'completed';
      statuses.package = 'completed';
    }
    return {
      ...snapshot,
      activeStepIndex: snapshot.steps.length,
      completedStepIds: Object.entries(statuses)
        .filter(([, status]) => status === 'completed')
        .map(([id]) => id),
      stepStatuses: statuses,
      stepDisplayText: text,
      finalization: {
        phase: packagingStatus === 'blocked_review_required' ? 'error' : 'complete',
        statusLine:
          packagingStatus === 'blocked_review_required'
            ? 'Blocked pending analyst review.'
            : 'Final analyst answer packaged.',
        timeoutTier: 0,
        partialFallback: packagingStatus === 'deterministic_fallback' || packagingStatus === 'llm_timeout',
        showRetryHint: false,
      },
    };
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
    if (response.response_packaging_status === 'deterministic_fallback' || response.response_packaging_status === 'llm_timeout') {
      toast.warning(
        composerFallbackReason(response)
          ? `Using governed deterministic answer. LLM narration unavailable: ${composerFallbackReason(response)}`
          : 'Using governed deterministic answer while LLM narration is unavailable.',
        { duration: 10_000 },
      );
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
    demoScenarioId?: string | null;
    userMessage?: string;
    reviewOptions?: ChatReviewOptions;
  }) => {
    const epoch = investigationEpochRef.current;
    const progressId = `progress-${crypto.randomUUID()}`;
    const { demoMode, fetcher, userMessage, reviewOptions, demoScenarioId } = options;
    const builtSteps = buildInvestigationProgressSteps({
      expectedSkill: options.expectedSkill,
      expectedSources: options.expectedSources,
      demoMode,
    });
    const injected = injectLegacyCoordinationStep(builtSteps, demoScenarioId ?? null);
    const steps = injected.steps;
    let coordinationAction = injected.action;
    let progressSnapshot: InvestigationProgressState = {
      steps,
      activeStepIndex: 0,
      completedStepIds: [],
      stepStatuses: initialStepStatuses(steps),
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
        demoScenarioId: demoScenarioId ?? null,
        coordinationAction,
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
          llmSplDraftMode,
          reviewOptions,
        );
        clearFinalizationTimers?.();
        progressSnapshot = settleProgressFromResponse(progressSnapshot, response);
        updateProgressMessage(progressId, epoch, progressSnapshot);
        await delay(250);
        await finishInvestigation(progressId, epoch, response);
        return;
      }

      if (!fetcher) {
        throw new Error('Demo investigation requires a fetcher');
      }
      // Resolve the frozen capture first so we can replay its real (capped) per-stage
      // latency (B4). The EC fixture resolves quickly; the staged playback below is
      // what gives the live end-to-end execution feel.
      const response = await fetcher();
      if (isStaleInvestigation(epoch)) return;
      // Surface the capture provenance (MCP-transport honesty badge) on the progress
      // message so it shows during the staged MCP handshake replay (B6).
      if (response.ec_provenance) {
        const provenance = response.ec_provenance;
        setMessages((current) =>
          current.map((message) =>
            message.id === progressId ? { ...message, ecProvenance: provenance } : message,
          ),
        );
      }
      // Override step durations with the captured stage_latencies when present;
      // otherwise the steps keep their synthetic jitter (non-captured scenarios).
      const replaySteps = applyStageLatencies(steps, response.ec_stage_latencies);
      let clearTimers: (() => void) | undefined;
      clearTimers = startFinalizationTimers(progressId, epoch, () => progressSnapshot);
      await playLegacyDemoInvestigationWithCoordination(
        replaySteps,
        ({ progress, action }) => {
          progressSnapshot = progress;
          if (action) coordinationAction = action;
          updateProgressMessage(progressId, epoch, progressSnapshot, coordinationAction);
        },
        {
          coordinationAction: injected.action,
          skipCompletion: true,
          isStale: () => isStaleInvestigation(epoch),
          executeCoordination: (current) =>
            executeLegacyDemoCoordination(current, sessionIdRef.current),
          onCoordinationUpdate: (action) => {
            coordinationAction = action;
            updateProgressMessage(progressId, epoch, progressSnapshot, coordinationAction);
          },
          waitForAnalyst: () =>
            new Promise<'confirm' | 'skip'>((resolve) => {
              coordinationWaitRef.current = {
                progressId,
                resolve: (decision) => {
                  if (isStaleInvestigation(epoch)) return;
                  resolve(decision);
                },
              };
            }),
        },
      );
      coordinationWaitRef.current = { progressId: null, resolve: null };
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
    coordinationWaitRef.current = { progressId: null, resolve: null };
    setLoading(false);
    sessionIdRef.current = null;
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem('ai_soc_session_id');
    }
    setMessages([welcome]);
    onClear?.();
  }, [onClear, welcome]);

  // Clicking the already-active "Chat" item in the left nav starts a fresh chat
  // (React Router no-ops same-route navigation, so the nav dispatches this event).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onNewChat = () => handleClear();
    window.addEventListener('soc:new-chat', onNewChat);
    return () => window.removeEventListener('soc:new-chat', onNewChat);
  }, [handleClear]);

  const handleExecutionReview = async (payload: ChatExecutionReviewOptions, label: string) => {
    const userMessage: SocChatMessage = { id: crypto.randomUUID(), role: 'user', content: label };
    setMessages((current) => [...current, userMessage]);
    await runStagedInvestigation({ demoMode: false, userMessage: label, reviewOptions: payload });
  };

  const handleInvestigationReview = async (
    payload: ChatInvestigationReviewOptions,
    label: string,
    originalQuery: string,
  ) => {
    const userMessage: SocChatMessage = { id: crypto.randomUUID(), role: 'user', content: label };
    setMessages((current) => [...current, userMessage]);
    await runStagedInvestigation({ demoMode: false, userMessage: originalQuery, reviewOptions: payload });
  };

  const handleRemediationReview = async (
    payload: ChatRemediationReviewOptions,
    label: string,
    originalQuery: string,
  ) => {
    const userMessage: SocChatMessage = { id: crypto.randomUUID(), role: 'user', content: label };
    setMessages((current) => [...current, userMessage]);
    await runStagedInvestigation({ demoMode: false, userMessage: originalQuery, reviewOptions: payload });
  };

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

  const handleCoordinationConfirm = (progressId: string) => {
    if (coordinationWaitRef.current.progressId !== progressId || !coordinationWaitRef.current.resolve) return;
    const resolve = coordinationWaitRef.current.resolve;
    coordinationWaitRef.current = { progressId: null, resolve: null };
    resolve('confirm');
  };

  const handleCoordinationSkip = (progressId: string) => {
    if (coordinationWaitRef.current.progressId !== progressId || !coordinationWaitRef.current.resolve) return;
    const resolve = coordinationWaitRef.current.resolve;
    coordinationWaitRef.current = { progressId: null, resolve: null };
    resolve('skip');
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
      demoScenarioId: scenario.scenario_id,
    });
  };

  return (
    <Card
      className={cn(
        'flex h-full min-h-0 w-full min-w-0 max-w-full flex-col overflow-hidden',
        flush ? 'rounded-none border-0 bg-transparent shadow-none' : 'soc-panel',
      )}
    >
      <CardHeader className={cn('min-w-0 shrink-0 space-y-3 overflow-x-hidden', compactHeader ? 'border-b border-slate-800/70 py-3' : 'border-b border-slate-800/70')}>
        <div className="flex min-w-0 items-center justify-between gap-3">
          <span className="soc-eyebrow flex items-center gap-2">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_8px_2px_hsl(192_88%_52%/0.6)]" />
            V.AI · SOC Assistant
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={llmSplDraftMode}
            disabled={loading}
            onClick={() => setLlmSplDraftMode(!llmSplDraftMode)}
            title="Lab-only: LLM generates non-governed SPL candidates for review. Never executed."
            className={cn(
              'soc-toggle-pill inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.7rem] font-medium transition disabled:cursor-not-allowed disabled:opacity-60',
              llmSplDraftMode
                ? 'border-amber-400/50 bg-amber-400/15 text-amber-100'
                : 'border-slate-700 bg-slate-900/60 text-slate-400 hover:border-slate-600 hover:text-slate-200',
            )}
          >
            <FlaskConical className="h-3.5 w-3.5" />
            Lab draft
            <span
              className={cn(
                'ml-0.5 h-1.5 w-1.5 rounded-full',
                llmSplDraftMode ? 'bg-amber-400 shadow-[0_0_6px_1px_rgba(251,191,36,0.7)]' : 'bg-slate-600',
              )}
            />
          </button>
        </div>
        {!conversationStarted ? (
          <>
            <StarterPrompts disabled={loading} onPick={handleSend} />
            <DemoScenarioPicker disabled={loading} onRun={handleRunDemo} />
          </>
        ) : null}
      </CardHeader>
      <CardContent className="min-h-0 min-w-0 flex-1 overflow-hidden p-0">
        <ScrollArea className="soc-chat-canvas h-full w-full min-w-0">
          <div className="soc-stream min-w-0 max-w-full space-y-4 overflow-x-hidden px-5 pb-8 pt-4">
            {messages.map((message) => (
              <ChatBubble
                key={message.id}
                message={message}
                investigationBusy={loading}
                onExecutionReview={handleExecutionReview}
                onInvestigationReview={handleInvestigationReview}
                onRemediationReview={handleRemediationReview}
                onCoordinationConfirm={handleCoordinationConfirm}
                onCoordinationSkip={handleCoordinationSkip}
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
