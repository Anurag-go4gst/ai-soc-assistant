import { Cpu, Database, Terminal } from 'lucide-react';
import type { EcVisualLanes } from '@/types/api';
import { cn } from '@/lib/utils';

export function EcVisualLanesPanel({ lanes }: { lanes: EcVisualLanes }) {
  return (
    <div className="space-y-3">
      {lanes.hil_banner ? (
        <div
          className={cn(
            'rounded-lg border px-4 py-3 text-sm',
            lanes.hil_banner.severity === 'error'
              ? 'border-red-400/40 bg-red-500/10 text-red-100'
              : 'border-amber-400/40 bg-amber-500/10 text-amber-50',
          )}
        >
          <p className="font-semibold">Analyst review required</p>
          <p className="mt-1 leading-6">{lanes.hil_banner.message}</p>
        </div>
      ) : null}
      {lanes.coe_logic ? (
        <div className="rounded-lg border border-slate-700 bg-slate-800/80 p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">
            <Database className="h-4 w-4 text-slate-200" />
            <Cpu className="h-4 w-4 text-slate-200" />
            <span>Application logic</span>
          </div>
          <p className="mt-2 text-sm font-medium text-slate-100">{lanes.coe_logic.title}</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">{lanes.coe_logic.body}</p>
          {lanes.coe_logic.slot_transitions?.length ? (
            <ul className="mt-3 space-y-1.5 font-mono text-xs text-cyan-200">
              {lanes.coe_logic.slot_transitions.map((item) => (
                <li key={`${item.from}-${item.to}`}>
                  {item.from} → {item.to}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {lanes.mcp_console ? (
        <div className="rounded-lg border border-emerald-500/30 bg-slate-950 p-4 font-mono text-xs text-emerald-300 shadow-inner">
          <div className="mb-2 flex items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-emerald-400">
            <Terminal className="h-3.5 w-3.5" />
            Splunk MCP console
          </div>
          {lanes.mcp_console.lines.map((line, index) => (
            <div key={`${line}-${index}`} className="leading-6">
              {line}
            </div>
          ))}
        </div>
      ) : null}
      {lanes.llm_insight?.markdown ? (
        <div className="rounded-lg border border-amber-400/30 bg-amber-500/[0.06] p-4">
          <p className="text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-amber-200">LLM insight</p>
          <div className="prose prose-invert prose-sm mt-2 max-w-none whitespace-pre-wrap text-slate-100">
            {lanes.llm_insight.markdown}
          </div>
          {lanes.llm_insight.timeline?.length ? (
            <ul className="mt-3 space-y-2 text-sm text-slate-200">
              {lanes.llm_insight.timeline.map((item) => (
                <li key={`${item.time}-${item.event}`}>
                  <span className="font-mono text-amber-200">{item.time}</span> — {item.event}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
