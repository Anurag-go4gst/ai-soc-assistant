import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Circle, Clock, Loader2, MinusCircle, ShieldCheck } from 'lucide-react';
import { scrollIntoScrollParent } from '@/lib/scrollIntoScrollParent';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  EXPERIENCE_EXECUTION_PANEL_CHROME,
  defaultExperienceExecutionHeader,
  experienceExecutionCounter,
  type ExperienceExecutionProgressView,
  type ExperienceExecutionStageStatus,
  type ExperienceExecutionStageView,
} from '@/lib/experienceCenterExecution';

interface ExperienceExecutionProgressPanelProps {
  state: ExperienceExecutionProgressView;
  onRetry?: () => void;
}

function StepDescription({
  step,
  isActive,
  isComplete,
}: {
  step: ExperienceExecutionStageView;
  isActive: boolean;
  isComplete: boolean;
}) {
  const lines = step.activity ?? [];
  const [lineIndex, setLineIndex] = useState(0);

  useEffect(() => {
    if (!isActive || lines.length <= 1) {
      setLineIndex(0);
      return undefined;
    }
    setLineIndex(0);
    const intervalMs = Math.max(1100, Math.floor(step.durationMs / lines.length));
    const timer = window.setInterval(() => {
      setLineIndex((current) => (current >= lines.length - 1 ? current : current + 1));
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [isActive, lines, step.durationMs]);

  const activityLine =
    lines.length === 0
      ? null
      : isActive
        ? lines[lineIndex]
        : isComplete
          ? lines[lines.length - 1]
          : null;

  return (
    <div className="min-w-0">
      <p className="text-sm font-medium text-slate-100">{step.label}</p>
      <p className="mt-0.5 text-xs leading-5 text-slate-400">{step.description}</p>
      {activityLine ? (
        <p
          key={activityLine}
          className={cn(
            'mt-1.5 font-mono text-[0.65rem] leading-4 transition-colors duration-300 animate-in fade-in',
            isActive ? 'text-cyan-200/95' : 'text-slate-500',
          )}
        >
          {activityLine}
        </p>
      ) : null}
    </div>
  );
}

function LiveElapsed({ className }: { className?: string }) {
  const [ms, setMs] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const timer = window.setInterval(() => setMs(Date.now() - start), 100);
    return () => window.clearInterval(timer);
  }, []);
  return <span className={cn('font-mono tabular-nums', className)}>{(ms / 1000).toFixed(1)}s</span>;
}

function rowStatus(
  stepItem: ExperienceExecutionStageView,
  index: number,
  state: ExperienceExecutionProgressView,
  allDone: boolean,
  inFinalization: boolean,
): ExperienceExecutionStageStatus {
  const explicit = state.stepStatuses?.[stepItem.id];
  if (explicit) return explicit;
  const completed = new Set(state.completedStepIds);
  if (completed.has(stepItem.id)) return 'completed';
  if (!allDone && !inFinalization && index === state.activeStepIndex) return 'active';
  return 'pending';
}

export function ExperienceExecutionProgressPanel({ state, onRetry }: ExperienceExecutionProgressPanelProps) {
  const { steps, finalization } = state;
  const hasError = Boolean(state.error);
  const inFinalization =
    !hasError && (finalization?.phase === 'finalizing' || finalization?.phase === 'partial');
  const waiting = Object.values(state.stepStatuses ?? {}).some((status) => status === 'waiting');
  const verifying = Object.values(state.stepStatuses ?? {}).some((status) => status === 'verifying');
  const allDone = state.activeStepIndex >= steps.length && !inFinalization && !hasError && !waiting && !verifying;
  const headerLabel = defaultExperienceExecutionHeader(state);
  const counter = experienceExecutionCounter(state);
  const listRef = useRef<HTMLOListElement | null>(null);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const activeRow = list.querySelector('[data-ec-step-active="true"]');
    if (activeRow instanceof HTMLElement) {
      window.requestAnimationFrame(() => {
        scrollIntoScrollParent(activeRow, { block: 'center', behavior: 'smooth' });
      });
    }
  }, [state.activeStepIndex, state.completedStepIds, state.stepStatuses]);

  const headerIcon = hasError ? (
    <Circle className="h-4 w-4 text-red-300" />
  ) : allDone ? (
    <CheckCircle2 className="h-4 w-4 text-emerald-300" />
  ) : waiting ? (
    <Clock className="h-4 w-4 text-amber-200" />
  ) : (
    <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
  );

  return (
    <div
      className={EXPERIENCE_EXECUTION_PANEL_CHROME.root}
      data-testid="experience-execution-progress-panel"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {headerIcon}
        <span className="text-sm font-semibold text-cyan-100">{headerLabel}</span>
        {state.demoMode ? <Badge variant="outline">Experience Center</Badge> : null}
        {state.resourceBadge ? (
          <Badge variant="outline" className="font-mono text-[0.6rem] border-slate-600/60 text-slate-400">
            {state.resourceBadge}
          </Badge>
        ) : null}
        {counter ? (
          <Badge variant="secondary" className="font-mono text-[0.65rem]">
            {counter.current}/{counter.total}
          </Badge>
        ) : null}
        {inFinalization ? (
          <Badge variant="secondary" className="flex items-center gap-1.5 font-mono text-[0.65rem]">
            <span>Finalizing</span>
            <LiveElapsed className="text-cyan-200/90" />
          </Badge>
        ) : null}
      </div>

      <ol ref={listRef} className="space-y-2">
        {steps.map((stepItem, index) => {
          const status = rowStatus(stepItem, index, state, allDone, inFinalization);
          const isComplete = status === 'completed';
          const isSkipped = status === 'skipped';
          const isBlocked = status === 'blocked' || status === 'failed';
          const isFallback = status === 'fallback';
          const isWaiting = status === 'waiting';
          const isVerifying = status === 'verifying';
          const isActive = status === 'active' || isVerifying;
          const isPending = status === 'pending';
          const displayText = state.stepDisplayText?.[stepItem.id];

          return (
            <li
              key={stepItem.id}
              data-stage-status={status}
              data-ec-step-active={isActive || isWaiting ? 'true' : undefined}
              className={cn(
                'flex gap-3 rounded-lg border px-3 py-2.5 transition-colors duration-300',
                isActive && EXPERIENCE_EXECUTION_PANEL_CHROME.activeRow,
                isComplete && EXPERIENCE_EXECUTION_PANEL_CHROME.completeRow,
                isSkipped && 'border-slate-800/50 bg-slate-950/20 opacity-70',
                isBlocked && EXPERIENCE_EXECUTION_PANEL_CHROME.blockedRow,
                (isFallback || isWaiting) && EXPERIENCE_EXECUTION_PANEL_CHROME.waitingRow,
                isPending && EXPERIENCE_EXECUTION_PANEL_CHROME.pendingRow,
                inFinalization && isComplete && 'opacity-90',
              )}
            >
              <div className="mt-0.5 shrink-0">
                {isBlocked ? (
                  <AlertTriangle className="h-4 w-4 text-red-300" />
                ) : isWaiting ? (
                  <Clock className="h-4 w-4 text-amber-200" />
                ) : isFallback ? (
                  <CheckCircle2 className="h-4 w-4 text-amber-300" />
                ) : isSkipped ? (
                  <MinusCircle className="h-4 w-4 text-slate-500" />
                ) : isComplete ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                ) : isVerifying ? (
                  <ShieldCheck className="h-4 w-4 animate-pulse text-cyan-300" />
                ) : isActive ? (
                  <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
                ) : (
                  <Circle className="h-4 w-4 text-slate-600" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <StepDescription
                  step={stepItem}
                  isActive={isActive || isWaiting}
                  isComplete={isComplete || isSkipped || isFallback}
                />
                {displayText ? (
                  <p className="mt-1.5 text-xs leading-5 text-slate-300">{displayText}</p>
                ) : null}
              </div>
              {isActive ? (
                <LiveElapsed key={stepItem.id} className="mt-0.5 shrink-0 self-start text-[0.65rem] text-cyan-200/70" />
              ) : null}
            </li>
          );
        })}
      </ol>

      {state.llmWarning ? (
        <div
          className="mt-3 rounded-lg border border-amber-500/35 bg-amber-500/[0.08] px-3 py-3"
          data-testid="investigation-llm-warning"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-amber-200/90">Live LLM unavailable</p>
          <p className="mt-1 text-sm leading-5 text-amber-50/95">{state.llmWarning.message}</p>
          {state.llmWarning.code ? (
            <p className="mt-1 font-mono text-[0.65rem] text-slate-500">Code: {state.llmWarning.code}</p>
          ) : null}
          <p className="mt-1.5 text-xs text-slate-400">Continuing with the governed deterministic answer…</p>
        </div>
      ) : null}

      {state.error ? (
        <div
          className="mt-3 rounded-lg border border-red-500/40 bg-red-500/[0.08] px-3 py-3"
          data-testid="investigation-error-panel"
          role="alert"
          aria-live="assertive"
        >
          <p className="text-sm font-medium text-red-100">{state.error.message}</p>
          {state.error.code ? (
            <p className="mt-1 font-mono text-[0.65rem] text-slate-500">Code: {state.error.code}</p>
          ) : null}
          {state.error.recoverable && onRetry ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2 h-8 border-red-500/40 text-xs text-red-100"
              onClick={onRetry}
            >
              Retry investigation
            </Button>
          ) : null}
        </div>
      ) : null}

      {inFinalization ? (
        <div
          className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/[0.06] px-3 py-3"
          data-testid="investigation-finalization-panel"
          aria-live="polite"
        >
          <div className="flex items-start gap-2">
            <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-amber-200" />
            <div className="min-w-0 space-y-1">
              <p className="text-sm font-medium text-amber-100">{finalization?.statusLine}</p>
              {finalization?.mcpDetail ? (
                <p className="text-xs leading-5 text-slate-400">{finalization.mcpDetail}</p>
              ) : null}
              {finalization?.showRetryHint && onRetry ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2 h-8 border-amber-500/40 text-xs text-amber-100"
                  onClick={onRetry}
                >
                  Retry final synthesis
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <p className="mt-3 text-[0.65rem] leading-5 text-slate-500">
        {state.demoMode
          ? 'Pipeline mirrors production routing and evidence gates. Experience Center uses COE fixtures; MCP search and final LLM synthesis stay disabled.'
          : 'Pipeline mirrors production routing and evidence gates. MCP execution and final synthesis follow platform settings.'}
      </p>
    </div>
  );
}
