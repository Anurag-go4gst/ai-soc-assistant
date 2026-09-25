import { Fragment, useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronRight, Circle, Loader2 } from 'lucide-react';
import { CompactFindingDetails } from '@/components/ec/EcInvestigationResultList';
import type { EcAgentPlanStep } from '@/components/ec/types';
import { cn } from '@/lib/utils';

function StatusIcon({ status }: { status: string }) {
  if (status === 'RUNNING') return <Loader2 className="h-4 w-4 animate-spin text-cyan-300" aria-label="Running" />;
  if (status === 'COMPLETE') return <CheckCircle2 className="h-4 w-4 text-emerald-400" aria-label="Done" />;
  return <Circle className="h-4 w-4 text-slate-600" aria-label={status.toLowerCase()} />;
}

/** Investigation results as one clean table: check · result · source, evidence on demand. */
export function EcFindingsTable({
  steps,
  anomalousAssetIds = [],
}: {
  steps: EcAgentPlanStep[];
  anomalousAssetIds?: string[];
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <section className="space-y-2" data-ec-section="investigation-results">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Investigation results</p>
      <div className="overflow-hidden rounded-lg border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900/70 text-[11px] uppercase tracking-wide text-slate-400">
            <tr>
              <th className="w-8 px-3 py-2" />
              <th className="px-3 py-2">Check</th>
              <th className="px-3 py-2">Result</th>
              <th className="hidden px-3 py-2 sm:table-cell">Source</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((step) => {
              const status = String(step.status ?? 'QUEUED').toUpperCase();
              const result = step.finding?.headline_finding ?? step.result ?? '';
              const open = openId === step.id;
              const expandable = Boolean(step.finding) && status === 'COMPLETE';
              return (
                <Fragment key={step.id}>
                  <tr
                    key={step.id}
                    data-ec-result-row={step.id}
                    className={cn('border-t border-slate-800/80 align-top', expandable && 'cursor-pointer hover:bg-slate-900/40')}
                    onClick={() => expandable && setOpenId(open ? null : step.id)}
                  >
                    <td className="px-3 py-2.5">
                      <StatusIcon status={status} />
                    </td>
                    <td className="px-3 py-2.5 text-slate-100">
                      {step.title}
                      {step.added_by_agent ? (
                        <span className="ml-2 rounded border border-violet-400/40 px-1.5 py-0.5 text-[10px] text-violet-200">
                          added by agent
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5 text-slate-200">
                      <span className="flex items-start gap-1.5">
                        {expandable ? (
                          open ? (
                            <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
                          ) : (
                            <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />
                          )
                        ) : null}
                        <span>{result}</span>
                      </span>
                    </td>
                    <td className="hidden px-3 py-2.5 text-xs text-slate-400 sm:table-cell">{(step.tools ?? []).join(' · ')}</td>
                  </tr>
                  {open && step.finding ? (
                    <tr key={`${step.id}-details`} className="bg-slate-950/40">
                      <td />
                      <td colSpan={3} className="px-3 pb-3">
                        <CompactFindingDetails step={step} finding={step.finding} anomalousAssetIds={anomalousAssetIds} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Remediation plan as a clean action table: approve per row; email drafts shown in full. */
export function EcActionsTable({
  steps,
  selectedIds,
  editable,
  onToggle,
}: {
  steps: EcAgentPlanStep[];
  selectedIds?: Set<string>;
  editable: boolean;
  onToggle?: (id: string, checked: boolean) => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <div className="overflow-hidden rounded-lg border border-slate-800" data-ec-section="remediation-actions">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-900/70 text-[11px] uppercase tracking-wide text-slate-400">
          <tr>
            <th className="w-8 px-3 py-2" />
            <th className="px-3 py-2">Action</th>
            <th className="hidden px-3 py-2 sm:table-cell">Tool</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((step) => {
            const details = (step.finding?.details ?? {}) as Record<string, unknown>;
            const email = (details.email_draft ?? null) as Record<string, unknown> | null;
            const spl = typeof details.normalized_spl === 'string' ? details.normalized_spl : '';
            const status = String(step.status ?? 'QUEUED').toUpperCase();
            const done = !['QUEUED', 'RUNNING', 'SKIPPED', 'PROPOSED', 'FAILED'].includes(status);
            const label =
              step.status_label ?? (done ? 'Done' : status === 'RUNNING' ? 'Running' : 'Pending approval');
            const result = step.result ?? step.finding?.headline_finding ?? null;
            const open = openId === step.id;
            return (
              <Fragment key={step.id}>
                <tr className="border-t border-slate-800/80 align-top" data-ec-action-row={step.id}>
                  <td className="px-3 py-2.5">
                    {editable ? (
                      <input
                        type="checkbox"
                        aria-label={`Include ${step.title}`}
                        checked={selectedIds?.has(step.id) ?? true}
                        onChange={(event) => onToggle?.(step.id, event.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500"
                      />
                    ) : (
                      <StatusIcon status={done ? 'COMPLETE' : status} />
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <p className="text-slate-100">{step.title}</p>
                    {(done || status === 'FAILED') && result ? (
                      <p className={cn('mt-0.5 text-xs', status === 'FAILED' ? 'text-rose-300' : 'text-emerald-300/90')}>
                        {result}
                      </p>
                    ) : step.summary ? (
                      <p className="mt-0.5 text-xs text-slate-400">{step.summary}</p>
                    ) : null}
                    {spl ? (
                      <button
                        type="button"
                        className="mt-1 text-xs text-cyan-400 hover:text-cyan-300"
                        onClick={() => setOpenId(open ? null : step.id)}
                      >
                        {open ? 'Hide query' : 'View query'}
                      </button>
                    ) : null}
                    {open && spl ? (
                      <pre className="mt-2 overflow-x-auto rounded-md bg-slate-950/70 p-2 font-mono text-[11px] text-slate-300">{spl}</pre>
                    ) : null}
                    {email ? (
                      <div className="mt-2 rounded-md border border-slate-700/80 bg-slate-950/60 p-3 text-xs" data-ec-email-preview={step.id}>
                        <p className="text-slate-400">
                          To: <span className="text-slate-200">{String(email.to ?? '')}</span>
                        </p>
                        <p className="mt-0.5 font-medium text-slate-100">{String(email.subject ?? '')}</p>
                        <pre className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap font-sans leading-relaxed text-slate-300">
                          {String(email.body ?? '')}
                        </pre>
                      </div>
                    ) : null}
                  </td>
                  <td className="hidden px-3 py-2.5 text-xs text-slate-400 sm:table-cell">{(step.tools ?? []).join(' · ')}</td>
                  <td className="px-3 py-2.5 text-xs">
                    <span
                      className={cn(
                        'whitespace-nowrap rounded border px-1.5 py-0.5',
                        status === 'FAILED'
                          ? 'border-rose-500/40 text-rose-200'
                          : done
                            ? 'border-emerald-500/40 text-emerald-200'
                            : 'border-slate-600 text-slate-300',
                      )}
                    >
                      {label}
                    </span>
                  </td>
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
