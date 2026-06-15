import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Circle, Loader2, MinusCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { InvestigationProgressState, InvestigationProgressStep } from '@/lib/investigationProgress';

interface InvestigationProgressPanelProps {
  state: InvestigationProgressState;
  demoMode?: boolean;
  onRetryFinalSynthesis?: () => void;
}

function StepDescription({ step, isActive, isComplete }: { step: InvestigationProgressStep; isActive: boolean; isComplete: boolean }) {
  const lines = step.activity ?? [];
  const [lineIndex, setLineIndex] = useState(0);

  useEffect(() => {
    if (!isActive || lines.length <= 1) {
      setLineIndex(0);
      return undefined;
    }
    const intervalMs = Math.max(380, Math.floor(step.durationMs / lines.length));
    const timer = window.setInterval(() => {
      setLineIndex((current) => (current + 1) % lines.length);
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
          className={cn(
            'mt-1.5 font-mono text-[0.65rem] leading-4 transition-colors',
            isActive ? 'text-cyan-200/95' : 'text-slate-500',
          )}
        >
          {activityLine}
        </p>
      ) : null}
    </div>
  );
}

/** Ticking elapsed timer; reads as a live, still-working connection while a step is active. */
function LiveElapsed({ className }: { className?: string }) {
  const [ms, setMs] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const timer = window.setInterval(() => setMs(Date.now() - start), 100);
    return () => window.clearInterval(timer);
  }, []);
  return <span className={cn('font-mono tabular-nums', className)}>{(ms / 1000).toFixed(1)}s</span>;
}

export function InvestigationProgressPanel({ state, demoMode, onRetryFinalSynthesis }: InvestigationProgressPanelProps) {
  const { steps, activeStepIndex, completedStepIds, finalization } = state;
  const completed = new Set(completedStepIds);
  const hasError = Boolean(state.error);
  const inFinalization =
    !hasError && (finalization?.phase === 'finalizing' || finalization?.phase === 'partial');
  const allDone = activeStepIndex >= steps.length && !inFinalization && !hasError;

  const headerLabel = hasError
    ? 'Investigation could not finish'
    : allDone
      ? 'Investigation pipeline complete'
      : inFinalization
        ? 'Finalizing governed answer'
        : 'Running governed investigation pipeline';

  return (
    <div
      className="rounded-xl border border-cyan-500/25 bg-cyan-500/[0.05] p-4 shadow-sm"
      data-testid="investigation-progress-panel"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {hasError ? (
          <Circle className="h-4 w-4 text-red-300" />
        ) : allDone ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-300" />
        ) : (
          <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
        )}
        <span className="text-sm font-semibold text-cyan-100">{headerLabel}</span>
        {demoMode ? <Badge variant="outline">Experience Center</Badge> : null}
        {!allDone && !inFinalization && steps[activeStepIndex] ? (
          <Badge variant="secondary" className="font-mono text-[0.65rem]">
            {Math.min(activeStepIndex + 1, steps.length)}/{steps.length}
          </Badge>
        ) : null}
        {inFinalization ? (
          <Badge variant="secondary" className="flex items-center gap-1.5 font-mono text-[0.65rem]">
            <span>Finalizing</span>
            <LiveElapsed className="text-cyan-200/90" />
          </Badge>
        ) : null}
      </div>

      <ol className="space-y-2">
        {steps.map((stepItem, index) => {
          const explicitStatus = state.stepStatuses?.[stepItem.id];
          const isComplete = explicitStatus === 'completed' || (!explicitStatus && completed.has(stepItem.id));
          const isSkipped = explicitStatus === 'skipped';
          const isBlocked = explicitStatus === 'blocked';
          const isFallback = explicitStatus === 'fallback';
          const isActive = explicitStatus === 'active' || (!explicitStatus && !allDone && !inFinalization && index === activeStepIndex);
          const isPending = !isComplete && !isActive && !isSkipped && !isBlocked && !isFallback;
          const displayText = state.stepDisplayText?.[stepItem.id];

          return (
            <li
              key={stepItem.id}
              className={cn(
                'flex gap-3 rounded-lg border px-3 py-2.5 transition-colors duration-300',
                isActive && 'border-cyan-500/40 bg-cyan-500/10 shadow-[0_0_12px_rgba(34,211,238,0.08)]',
                isComplete && 'border-slate-800 bg-slate-950/50',
                isSkipped && 'border-slate-800/50 bg-slate-950/20 opacity-70',
                isBlocked && 'border-red-500/35 bg-red-500/[0.08]',
                isFallback && 'border-amber-500/35 bg-amber-500/[0.08]',
                isPending && 'border-slate-800/60 bg-slate-950/30 opacity-60',
                inFinalization && isComplete && 'opacity-90',
              )}
            >
              <div className="mt-0.5 shrink-0">
                {isBlocked ? (
                  <AlertTriangle className="h-4 w-4 text-red-300" />
                ) : isFallback ? (
                  <CheckCircle2 className="h-4 w-4 text-amber-300" />
                ) : isSkipped ? (
                  <MinusCircle className="h-4 w-4 text-slate-500" />
                ) : isComplete ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                ) : isActive ? (
                  <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
                ) : (
                  <Circle className="h-4 w-4 text-slate-600" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <StepDescription step={stepItem} isActive={isActive} isComplete={isComplete || isSkipped || isFallback} />
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
        >
          <p className="text-sm font-medium text-red-100">{state.error.message}</p>
          {state.error.code ? (
            <p className="mt-1 font-mono text-[0.65rem] text-slate-500">Code: {state.error.code}</p>
          ) : null}
          {state.error.recoverable && onRetryFinalSynthesis ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2 h-8 border-red-500/40 text-xs text-red-100"
              onClick={onRetryFinalSynthesis}
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
        >
          <div className="flex items-start gap-2">
            <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-amber-200" />
            <div className="min-w-0 space-y-1">
              <p className="text-sm font-medium text-amber-100">{finalization?.statusLine}</p>
              {finalization?.mcpDetail ? (
                <p className="text-xs leading-5 text-slate-400">{finalization.mcpDetail}</p>
              ) : null}
              {finalization?.showRetryHint && onRetryFinalSynthesis ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2 h-8 border-amber-500/40 text-xs text-amber-100"
                  onClick={onRetryFinalSynthesis}
                >
                  Retry final synthesis
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <p className="mt-3 text-[0.65rem] leading-5 text-slate-500">
        {demoMode
          ? 'Pipeline mirrors production routing and evidence gates. Experience Center uses COE fixtures; live MCP search and final LLM synthesis stay disabled.'
          : 'Pipeline mirrors production routing and evidence gates. Live MCP execution and final synthesis follow platform settings.'}
      </p>
    </div>
  );
}
