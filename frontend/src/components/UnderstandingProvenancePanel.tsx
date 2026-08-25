import type { UnderstandingProvenanceLine } from '@/types/api';

interface UnderstandingProvenancePanelProps {
  provenance: {
    schema_version?: string;
    acceptance_decision?: string;
    lines?: UnderstandingProvenanceLine[];
  };
}

export function UnderstandingProvenancePanel({ provenance }: UnderstandingProvenancePanelProps) {
  const lines = provenance.lines ?? [];
  if (!lines.length) {
    return null;
  }

  return (
    <div className="mb-3 rounded-md border border-slate-800 bg-slate-950/60 px-3 py-3 text-xs text-slate-300">
      <p className="font-semibold text-slate-100">Understanding authority path</p>
      <dl className="mt-2 space-y-1 font-mono text-[0.72rem] leading-5">
        {lines.map((line) => (
          <div key={line.label} className="grid grid-cols-[minmax(8rem,11rem)_1fr] gap-2">
            <dt className="text-slate-500">{line.label}</dt>
            <dd className="text-slate-200">{line.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
