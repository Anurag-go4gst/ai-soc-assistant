import { formatSplForDisplay } from '@/lib/formatSplForDisplay';
import { cn } from '@/lib/utils';

export function EcSplCodeBlock({
  spl,
  label,
  className,
  maxHeightClass = 'max-h-[min(52vh,28rem)]',
}: {
  spl: string;
  label?: string;
  className?: string;
  maxHeightClass?: string;
}) {
  const text = formatSplForDisplay(spl);
  if (!text) return null;

  return (
    <div className={cn('min-w-0 w-full max-w-full', className)}>
      {label ? (
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.1em] text-slate-400">{label}</p>
      ) : null}
      <pre
        className={cn(
          'ec-spl-code scrollbar-thin w-full max-w-full overflow-y-auto rounded-lg border border-cyan-500/20 bg-slate-950 p-4 text-xs leading-relaxed text-cyan-50/95 shadow-inner ring-1 ring-cyan-500/10',
          maxHeightClass,
        )}
        data-ec-section="spl-code"
      >
        {text}
      </pre>
    </div>
  );
}
