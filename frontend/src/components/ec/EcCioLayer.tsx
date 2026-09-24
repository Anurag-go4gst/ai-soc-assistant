import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import type { EcAgentPlanStep, EcExecutiveBrief, EcStoryThread, EcToolFabricEntry } from '@/components/ec/types';
import { cn } from '@/lib/utils';

/** One-line "Why" for a plan step, with the decision / reversibility detail on demand. */
export function EcStepWhy({ step }: { step: EcAgentPlanStep }) {
  const [open, setOpen] = useState(false);
  if (!step.rationale) return null;
  const detail: Array<[string, string | undefined]> = [
    ['Decides', step.decides],
    ['If skipped', step.if_skipped],
    ['Reversible', step.reversible],
    ['Approver', step.approver],
    ['Risk if skipped', step.risk_if_skipped],
  ];
  const rows = detail.filter((row): row is [string, string] => Boolean(row[1]));
  return (
    <div className="mt-1.5 text-xs leading-relaxed" data-ec-step-why={step.id}>
      <button
        type="button"
        className="flex items-start gap-1 text-left text-cyan-200/85 hover:text-cyan-100"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        disabled={!rows.length}
      >
        {rows.length ? (
          open ? (
            <ChevronDown className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          ) : (
            <ChevronRight className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          )
        ) : null}
        <span>
          <span className="font-semibold">Why: </span>
          {step.rationale}
        </span>
      </button>
      {open && rows.length ? (
        <dl className="mt-1.5 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 pl-4 text-slate-400">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="font-medium text-slate-300">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function riskClass(risk?: string): string {
  switch ((risk ?? '').toUpperCase()) {
    case 'HIGH':
    case 'CRITICAL':
      return 'border-rose-400/40 text-rose-200';
    case 'MEDIUM':
      return 'border-amber-400/40 text-amber-200';
    case 'LOW':
      return 'border-emerald-400/40 text-emerald-200';
    default:
      return 'border-slate-600 text-slate-300';
  }
}

/** Verdict-first brief for a CIO: impact, risk movement, confidence, and the decision asked. */
export function EcExecutiveBrief({ brief }: { brief: EcExecutiveBrief }) {
  const rows: Array<[string, string | undefined]> = [
    ['Business impact', brief.business_impact],
    ['Confidence', brief.confidence],
    ['Would change if', brief.would_change_if],
    ['Will not do', brief.will_not_do],
  ];
  return (
    <section
      className="space-y-3 rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-4"
      data-ec-section="executive-brief"
    >
      <EcSectionHeading>Executive brief</EcSectionHeading>
      <p className="text-base font-semibold leading-snug text-slate-50">{brief.verdict}</p>
      {brief.risk_from || brief.risk_to ? (
        <p className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span>Risk</span>
          <span className={cn('rounded border px-1.5 py-0.5 font-semibold', riskClass(brief.risk_from))}>
            {brief.risk_from ?? '—'}
          </span>
          <span aria-hidden="true">→</span>
          <span className={cn('rounded border px-1.5 py-0.5 font-semibold', riskClass(brief.risk_to))}>
            {brief.risk_to ?? '—'}
          </span>
        </p>
      ) : null}
      <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[10rem,1fr]">
        {rows
          .filter((row): row is [string, string] => Boolean(row[1]))
          .map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
              <dd className="text-slate-200">{value}</dd>
            </div>
          ))}
      </dl>
      {brief.decision_needed ? (
        <div className="rounded-md border border-cyan-400/30 bg-slate-950/40 px-3 py-2 text-sm text-cyan-50">
          <span className="font-semibold">Decision needed: </span>
          {brief.decision_needed}
        </div>
      ) : null}
    </section>
  );
}

/** The connected tool fabric: every catalog tool, lit when this plan uses it. */
export function EcToolFabric({ tools }: { tools: EcToolFabricEntry[] }) {
  if (!tools.length) return null;
  const anyDemo = tools.some((tool) => tool.demo_fixture);
  return (
    <section className="space-y-2" data-ec-section="tool-fabric">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <EcSectionHeading>Connected tools</EcSectionHeading>
        {anyDemo ? (
          <span className="text-[11px] text-slate-500">Demo connectors · deterministic responses</span>
        ) : null}
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {tools.map((tool) => (
          <li
            key={tool.tool_id}
            title={tool.role}
            data-tool-used={tool.used ? 'true' : 'false'}
            className={cn(
              'rounded-full border px-2.5 py-1 text-xs',
              tool.used
                ? 'border-cyan-400/50 bg-cyan-950/40 text-cyan-100'
                : 'border-slate-800 text-slate-500',
            )}
          >
            {tool.name}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Where this question sits in a multi-day incident, so related questions read as one story. */
export function EcStoryThreadBadge({ thread }: { thread: EcStoryThread }) {
  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-amber-400/30 bg-amber-950/15 px-3 py-2 text-xs"
      data-ec-section="story-thread"
    >
      <span className="font-semibold text-amber-100">
        Incident {thread.thread_id} · Day {thread.day}
      </span>
      <span className="text-amber-50/90">{thread.title}</span>
      <span className="text-slate-400">So far: {thread.verdict_so_far}</span>
      {thread.next ? <span className="text-slate-400">Next in this incident: {thread.next.label}</span> : null}
    </div>
  );
}
