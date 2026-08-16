import type { EcProjection, EcProjectionView } from '@/components/ec/types';
import { Badge } from '@/components/ui/badge';

function PathCard({ view }: { view: EcProjectionView }) {
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-100">{view.title}</h4>
        <Badge variant="outline">{view.provenance.kind}</Badge>
      </div>
      <p className="mt-2 text-sm text-slate-400">{view.summary}</p>
      {view.items.length ? (
        <ul className="mt-2 space-y-1 text-xs text-slate-500">
          {view.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

export function EcInvestigationOutcomeCard({ view }: { view: EcProjectionView }) {
  return <PathCard view={view} />;
}

export function EcEvidenceStateBoard({ view }: { view: EcProjectionView }) {
  return <PathCard view={view} />;
}

export function EcSplGovernancePanel({ view }: { view: EcProjectionView }) {
  return <PathCard view={view} />;
}

export function EcTransparencyDrawer({ projection }: { projection: EcProjection }) {
  return (
    <details className="soc-panel rounded-xl p-5" data-ec-layer="investigation-path">
      <summary className="cursor-pointer list-none">
        <p className="soc-eyebrow text-cyan-400">Investigation Path</p>
        <p className="mt-1 text-sm text-slate-300">Understanding → resources → controls → evidence → outcome</p>
      </summary>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <PathCard view={projection.understanding} />
        <PathCard view={projection.resource_plan} />
        <EcSplGovernancePanel view={projection.phase_contract} />
        <EcEvidenceStateBoard view={projection.evidence_state} />
        <div className="md:col-span-2">
          <EcInvestigationOutcomeCard view={projection.investigation_outcome} />
        </div>
      </div>
    </details>
  );
}
