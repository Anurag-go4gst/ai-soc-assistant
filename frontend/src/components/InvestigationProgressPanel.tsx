import { useEffect, useState } from 'react';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { InvestigationProgressState, InvestigationProgressStep } from '@/lib/investigationProgress';

interface InvestigationProgressPanelProps {
  state: InvestigationProgressState;
  demoMode?: boolean;
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

export function InvestigationProgressPanel({ state, demoMode }: InvestigationProgressPanelProps) {
  const { steps, activeStepIndex, completedStepIds } = state;
  const completed = new Set(completedStepIds);
  const allDone = activeStepIndex >= steps.length;

  return (
    <div
      className="rounded-xl border border-cyan-500/25 bg-cyan-500/[0.05] p-4 shadow-sm"
      data-testid="investigation-progress-panel"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {allDone ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-300" />
        ) : (
          <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
        )}
        <span className="text-sm font-semibold text-cyan-100">
          {allDone ? 'Investigation pipeline complete' : 'Running governed investigation pipeline'}
        </span>
        {demoMode ? <Badge variant="outline">Experience Center</Badge> : null}
        {!allDone && steps[activeStepIndex] ? (
          <Badge variant="secondary" className="font-mono text-[0.65rem]">
            {activeStepIndex + 1}/{steps.length}
          </Badge>
        ) : null}
      </div>

      <ol className="space-y-2">
        {steps.map((stepItem, index) => {
          const isComplete = completed.has(stepItem.id);
          const isActive = !allDone && index === activeStepIndex;
          const isPending = !isComplete && !isActive;

          return (
            <li
              key={stepItem.id}
              className={cn(
                'flex gap-3 rounded-lg border px-3 py-2.5 transition-colors duration-300',
                isActive && 'border-cyan-500/40 bg-cyan-500/10 shadow-[0_0_12px_rgba(34,211,238,0.08)]',
                isComplete && 'border-slate-800 bg-slate-950/50',
                isPending && 'border-slate-800/60 bg-slate-950/30 opacity-60',
              )}
            >
              <div className="mt-0.5 shrink-0">
                {isComplete ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                ) : isActive ? (
                  <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
                ) : (
                  <Circle className="h-4 w-4 text-slate-600" />
                )}
              </div>
              <StepDescription step={stepItem} isActive={isActive} isComplete={isComplete} />
            </li>
          );
        })}
      </ol>

      <p className="mt-3 text-[0.65rem] leading-5 text-slate-500">
        {demoMode
          ? 'Pipeline mirrors production routing and evidence gates. Experience Center uses COE fixtures; live MCP search and final LLM synthesis stay disabled.'
          : 'Pipeline mirrors production routing and evidence gates. Live MCP execution and final synthesis follow platform settings.'}
      </p>
    </div>
  );
}
