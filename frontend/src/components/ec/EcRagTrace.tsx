import { useState } from 'react';
import { BookOpen, FilterX, Quote } from 'lucide-react';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import type { EcRagTrace as EcRagTracePayload } from '@/components/ec/types';
import { cn } from '@/lib/utils';

const EXCLUSION_LABELS: Record<string, string> = {
  draft: 'draft',
  rejected: 'rejected',
  superseded: 'superseded',
  expired: 'expired',
  retired: 'retired',
  wrong_environment: 'wrong environment',
  wrong_allowed_use: 'not approved for this use',
};

/**
 * "How RAG answered this": the governed retrieval behind a knowledge answer — what was searched,
 * what was excluded and why, which passages were used, and a citation on every sentence.
 */
export function EcRagTrace({ trace }: { trace: EcRagTracePayload }) {
  const [focused, setFocused] = useState<string | null>(null);
  return (
    <section className="space-y-4 rounded-lg border border-violet-500/25 bg-violet-950/10 p-4" data-ec-section="rag-trace">
      <div className="flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-violet-300" aria-hidden="true" />
        <EcSectionHeading>How RAG answered this</EcSectionHeading>
      </div>

      <div className="grid gap-2 text-sm sm:grid-cols-3">
        <div className="rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2">
          <p className="text-[11px] uppercase tracking-wide text-slate-500">Searched</p>
          <p className="text-slate-100">{trace.collections.join(' · ')}</p>
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2">
          <p className="text-[11px] uppercase tracking-wide text-slate-500">Excluded before ranking</p>
          <p className="text-slate-100">
            {trace.excluded_total} ·{' '}
            <span className="text-slate-400">
              {trace.excluded.map((item) => `${item.count} ${EXCLUSION_LABELS[item.reason] ?? item.reason}`).join(', ')}
            </span>
          </p>
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2">
          <p className="text-[11px] uppercase tracking-wide text-slate-500">Passages used</p>
          <p className="text-slate-100">
            {trace.passages.filter((passage) => passage.used).length}
            {typeof trace.top_confidence === 'number' ? (
              <span className="text-slate-400"> · top match {trace.top_confidence.toFixed(2)}</span>
            ) : null}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-semibold text-slate-50">{trace.answer.headline}</p>
        <ol className="space-y-1.5 text-sm text-slate-200">
          {trace.answer.sentences.map((sentence) => (
            <li key={sentence.text} className="flex flex-wrap items-baseline gap-x-2 gap-y-1 leading-relaxed">
              <span>{sentence.text}</span>
              {sentence.citations.map((label) => (
                <button
                  key={label}
                  type="button"
                  className={cn(
                    'rounded border px-1.5 py-0 text-[11px] font-medium',
                    focused === label
                      ? 'border-violet-300 bg-violet-500/30 text-violet-50'
                      : 'border-violet-400/40 text-violet-200 hover:bg-violet-500/20',
                  )}
                  onMouseEnter={() => setFocused(label)}
                  onMouseLeave={() => setFocused(null)}
                  onFocus={() => setFocused(label)}
                  onBlur={() => setFocused(null)}
                  data-ec-citation={label}
                >
                  {label}
                </button>
              ))}
            </li>
          ))}
        </ol>
        {trace.answer.gaps.length ? (
          <div className="rounded-md border border-amber-500/25 bg-amber-950/10 px-3 py-2 text-sm">
            <p className="flex items-center gap-1.5 font-medium text-amber-100">
              <FilterX className="h-3.5 w-3.5" aria-hidden="true" />
              Not in our knowledge base — not answered
            </p>
            <ul className="mt-1 space-y-1 text-amber-50/85">
              {trace.answer.gaps.map((gap) => (
                <li key={gap}>· {gap}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Retrieved passages</p>
        <ul className="space-y-2">
          {trace.passages.map((passage) => (
            <li
              key={passage.entry_id}
              data-ec-passage={passage.label}
              className={cn(
                'rounded-md border px-3 py-2 text-sm transition-colors',
                focused === passage.label ? 'border-violet-300/70 bg-violet-950/30' : 'border-slate-800 bg-slate-950/30',
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded border border-violet-400/40 px-1.5 text-[11px] font-medium text-violet-200">{passage.label}</span>
                <span className="text-slate-100">{passage.doc_title}</span>
                <span className="text-xs text-slate-500">v{passage.doc_version} · {passage.approval_status.replace('_', ' ')}</span>
                <span className="ml-auto flex items-center gap-1.5 text-xs text-slate-400">
                  <span className="relative h-1.5 w-16 overflow-hidden rounded bg-slate-800" aria-hidden="true">
                    <span className="absolute inset-y-0 left-0 bg-violet-400" style={{ width: `${Math.round(passage.confidence * 100)}%` }} />
                  </span>
                  {passage.confidence.toFixed(2)}
                </span>
              </div>
              <p className="mt-1.5 flex gap-1.5 text-slate-300">
                <Quote className="mt-0.5 h-3 w-3 shrink-0 text-slate-500" aria-hidden="true" />
                <span>{passage.excerpt}</span>
              </p>
              {passage.used_for ? <p className="mt-1 text-xs text-slate-500">{passage.used_for}</p> : null}
            </li>
          ))}
        </ul>
      </div>

      {trace.governance?.length ? (
        <ul className="space-y-1 border-t border-slate-800 pt-3 text-xs text-slate-400">
          {trace.governance.map((line) => (
            <li key={line}>· {line}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
