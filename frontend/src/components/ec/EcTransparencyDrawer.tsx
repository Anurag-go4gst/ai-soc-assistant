import type {
  EcEvidenceStateItem,
  EcInvestigationOutcomePayload,
  EcProjectionView,
  EcSplGovernance,
  ExperienceCenterResponse,
} from '@/components/ec/types';
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

function statusVariant(status: string): 'success' | 'warning' | 'outline' {
  if (status === 'OBTAINED' || status === 'VERIFIED') return 'success';
  if (status === 'MISSING' || status === 'CONFLICTING' || status === 'NOT_AVAILABLE') return 'warning';
  return 'outline';
}

export function EcInvestigationOutcomeCard({
  view,
  outcome,
}: {
  view: EcProjectionView;
  outcome?: EcInvestigationOutcomePayload;
}) {
  if (!outcome) return <PathCard view={view} />;
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-950/50 p-4" data-ec-section="investigation-outcome">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-100">InvestigationOutcome</h4>
        <Badge>{outcome.disposition}</Badge>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-400/80">Confirmed</p>
          <ul className="mt-1 space-y-1 text-xs text-slate-300">
            {outcome.confirmed.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-400/80">Unconfirmed</p>
          <ul className="mt-1 space-y-1 text-xs text-amber-100/80">
            {outcome.unconfirmed.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Supported</p>
          <ul className="mt-1 space-y-1 text-xs text-slate-400">
            {outcome.supported.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Missing evidence</p>
          <ul className="mt-1 space-y-1 text-xs text-slate-400">
            {outcome.missing_evidence.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>
    </article>
  );
}

export function EcEvidenceStateBoard({
  view,
  items,
}: {
  view: EcProjectionView;
  items?: EcEvidenceStateItem[];
}) {
  if (!items?.length) return <PathCard view={view} />;
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-950/50 p-4" data-ec-section="evidence-state">
      <h4 className="text-sm font-semibold text-slate-100">Evidence state</h4>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-start justify-between gap-3 text-xs">
            <div>
              <p className="text-slate-200">{item.label}</p>
              {item.detail ? <p className="mt-0.5 text-slate-500">{item.detail}</p> : null}
            </div>
            <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
          </li>
        ))}
      </ul>
    </article>
  );
}

export function EcSplGovernancePanel({
  view,
  governance,
}: {
  view: EcProjectionView;
  governance?: EcSplGovernance;
}) {
  if (!governance) return <PathCard view={view} />;
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-950/50 p-4 md:col-span-2" data-ec-section="spl-governance">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-100">SPL governance</h4>
        <Badge variant={governance.validation.search_1_approved && governance.validation.search_2_approved ? 'success' : 'warning'}>
          {governance.validation.search_1_approved && governance.validation.search_2_approved ? 'validate_spl approved' : 'validation failed'}
        </Badge>
      </div>
      <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-slate-500">User request</dt>
          <dd className="mt-1 text-slate-300">{governance.user_request}</dd>
          <p className="mt-1 text-xs text-slate-500">{governance.time_range_supplied ? 'Time range supplied.' : 'No time range supplied.'}</p>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-slate-500">Environment governance</dt>
          <dd className="mt-1 text-slate-300">{governance.environment_governance}</dd>
          <p className="mt-1 text-xs text-slate-500">{governance.why}</p>
        </div>
      </dl>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {governance.searches.map((search) => (
          <div key={search.search_id} className="rounded-md border border-slate-800 p-3">
            <p className="text-sm font-medium text-slate-100">{search.label}</p>
            <p className="mt-1 text-xs text-slate-500">{search.earliest} → {search.latest}</p>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px] text-slate-400">{search.normalized_spl || search.candidate_spl}</pre>
            <p className="mt-2 text-xs text-slate-500">Validator {search.approved ? 'approved' : 'rejected'} · {search.provenance}</p>
          </div>
        ))}
      </div>
      <div className="mt-3">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Controls applied</p>
        <p className="mt-1 text-xs text-slate-400">{governance.controls.join(' · ')}</p>
      </div>
      <p className="mt-3 text-xs text-slate-400">{governance.evidence_merge}</p>
      <p className="mt-1 text-xs text-slate-500">
        {governance.spl_not_required ? 'SPL not required' : 'Candidate SPL is review-only. Production MCP was not executed.'}
      </p>
    </article>
  );
}

export function EcTransparencyDrawer({
  envelope,
}: {
  envelope: ExperienceCenterResponse;
}) {
  const projection = envelope.ec_projection;
  const path = envelope.ec_layer2_path ?? [
    'Understanding',
    'Resources',
    'Controls',
    'Evidence',
    'Outcome',
  ];
  return (
    <details className="soc-panel rounded-xl p-5" data-ec-layer="investigation-path">
      <summary className="cursor-pointer list-none">
        <p className="soc-eyebrow text-cyan-400">Investigation Path</p>
        <p className="mt-1 text-sm text-slate-300">{path.join(' → ')}</p>
      </summary>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <PathCard view={projection.understanding} />
        <PathCard view={projection.resource_plan} />
        <EcSplGovernancePanel view={projection.phase_contract} governance={envelope.ec_spl_governance} />
        <EcEvidenceStateBoard view={projection.evidence_state} items={envelope.ec_evidence_state} />
        <div className="md:col-span-2">
          <EcInvestigationOutcomeCard
            view={projection.investigation_outcome}
            outcome={envelope.ec_investigation_outcome}
          />
        </div>
      </div>
    </details>
  );
}
