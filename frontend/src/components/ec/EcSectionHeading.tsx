import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export function EcSectionHeading({
  children,
  variant = 'default',
  className,
}: {
  children: ReactNode;
  variant?: 'default' | 'warning' | 'success';
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 border-b pb-2',
        variant === 'warning' ? 'border-amber-500/30' : variant === 'success' ? 'border-emerald-500/30' : 'border-cyan-500/25',
        className,
      )}
    >
      <h4
        className={cn(
          'min-w-0 shrink text-sm font-semibold uppercase tracking-[0.12em]',
          variant === 'warning' ? 'text-amber-200' : variant === 'success' ? 'text-emerald-200' : 'text-cyan-100',
        )}
      >
        {children}
      </h4>
      <span
        className={cn(
          'h-px flex-1',
          variant === 'warning' ? 'bg-amber-500/20' : variant === 'success' ? 'bg-emerald-500/20' : 'bg-cyan-500/15',
        )}
      />
    </div>
  );
}

export function EcAnswerTitle({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 px-4 py-3 ring-1 ring-cyan-500/10">
      <p className="soc-eyebrow text-cyan-300">SOC Answer</p>
      <div className="mt-1 break-words text-lg font-semibold leading-snug text-slate-50">{children}</div>
    </div>
  );
}
