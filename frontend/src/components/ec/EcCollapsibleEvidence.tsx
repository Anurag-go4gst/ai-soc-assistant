import type { ReactNode } from 'react';

export function EcCollapsibleEvidencePanel({
  summary = 'View full evidence',
  hint = 'SIEM coverage, scope, reuse, and governance detail — full trace in Investigation path.',
  children,
}: {
  summary?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <details
      className="rounded-lg border border-slate-800/80 bg-slate-900/30 p-3 open:bg-slate-900/45"
      data-ec-section="collapsible-evidence"
    >
      <summary className="cursor-pointer list-none text-sm font-medium text-cyan-400/90 [&::-webkit-details-marker]:hidden">
        {summary}
        <span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span>
      </summary>
      <div className="mt-4 space-y-6">{children}</div>
    </details>
  );
}
