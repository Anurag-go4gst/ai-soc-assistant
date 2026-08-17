/**
 * Shared Experience Center execution-progress view model.
 * Pure presentation types — no live /chat sequencing and no RACES fixture orchestration.
 */

export type ExperienceExecutionStageStatus =
  | 'pending'
  | 'active'
  | 'completed'
  | 'skipped'
  | 'blocked'
  | 'fallback'
  | 'waiting'
  | 'failed'
  | 'verifying';

export interface ExperienceExecutionStageView {
  id: string;
  label: string;
  description: string;
  durationMs: number;
  activity?: string[];
}

export interface ExperienceExecutionError {
  message: string;
  code?: string | null;
  recoverable?: boolean;
}

export interface ExperienceExecutionFinalization {
  phase: 'deterministic' | 'finalizing' | 'partial' | 'complete' | 'error';
  statusLine: string;
  mcpDetail?: string | null;
  showRetryHint?: boolean;
}

export interface ExperienceExecutionProgressView {
  steps: ExperienceExecutionStageView[];
  activeStepIndex: number;
  completedStepIds: string[];
  stepStatuses?: Record<string, ExperienceExecutionStageStatus>;
  stepDisplayText?: Record<string, string>;
  header?: string | null;
  resourceBadge?: string | null;
  demoMode?: boolean;
  error?: ExperienceExecutionError | null;
  llmWarning?: { message: string; code?: string | null } | null;
  finalization?: ExperienceExecutionFinalization | null;
}

export const EXPERIENCE_EXECUTION_PANEL_CHROME = {
  root:
    'rounded-xl border border-cyan-500/25 bg-cyan-500/[0.05] p-4 shadow-sm',
  activeRow:
    'border-cyan-500/40 bg-cyan-500/10 shadow-[0_0_12px_rgba(34,211,238,0.08)]',
  completeRow: 'border-slate-800 bg-slate-950/50',
  pendingRow: 'border-slate-800/60 bg-slate-950/30 opacity-60',
  waitingRow: 'border-amber-500/35 bg-amber-500/[0.08]',
  blockedRow: 'border-red-500/35 bg-red-500/[0.08]',
} as const;

export function defaultExperienceExecutionHeader(view: ExperienceExecutionProgressView): string {
  if (view.header) return view.header;
  const hasError = Boolean(view.error);
  const inFinalization =
    !hasError && (view.finalization?.phase === 'finalizing' || view.finalization?.phase === 'partial');
  const waiting = Object.values(view.stepStatuses ?? {}).some((status) => status === 'waiting');
  const verifying = Object.values(view.stepStatuses ?? {}).some((status) => status === 'verifying');
  const allDone = view.activeStepIndex >= view.steps.length && !inFinalization && !hasError && !waiting;
  if (hasError) return 'Investigation could not finish';
  if (allDone) return 'Investigation pipeline complete';
  if (inFinalization) return 'Finalizing governed answer';
  if (waiting) return 'Waiting';
  if (verifying) return 'Verifying';
  return 'Running governed investigation pipeline';
}

export function experienceExecutionCounter(
  view: ExperienceExecutionProgressView,
): { current: number; total: number } | null {
  const hasError = Boolean(view.error);
  const inFinalization =
    !hasError && (view.finalization?.phase === 'finalizing' || view.finalization?.phase === 'partial');
  const waiting = Object.values(view.stepStatuses ?? {}).some((status) => status === 'waiting');
  const allDone = view.activeStepIndex >= view.steps.length && !inFinalization && !hasError;
  if (allDone || inFinalization || !view.steps[view.activeStepIndex]) return null;
  if (waiting) return { current: Math.min(view.activeStepIndex + 1, view.steps.length), total: view.steps.length };
  return {
    current: Math.min(view.activeStepIndex + 1, view.steps.length),
    total: view.steps.length,
  };
}
