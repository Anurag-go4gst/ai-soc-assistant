import type {
  EcEvidenceStateItem,
  EcInvestigationOutcomePayload,
  EcProjectionView,
  EcSplGovernance,
  ExperienceCenterResponse,
} from '@/components/ec/types';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcSplCodeBlock } from '@/components/ec/EcSplCodeBlock';
import { EcSiemToolTraces } from '@/components/ec/EcSiemCoverage';
import { Badge } from '@/components/ui/badge';

function EcGapSplPanel({ envelope }: { envelope: ExperienceCenterResponse }) {
  if (!envelope.ec_gap_spl_layer2_only && !envelope.candidate_spl?.candidate_spl) return null;
  const spl = envelope.candidate_spl?.candidate_spl;
  if (!spl) return null;
  return (
    <article className="md:col-span-2 rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 ring-1 ring-slate-800/50" data-ec-section="gap-spl-layer2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-50">Governed gap SPL</h4>
        <Badge variant="outline" className="border-slate-600 text-slate-300">Layer 2 · review only</Badge>
      </div>
      {envelope.ec_gap_spl_notice ? (
        <p className="mt-3 text-sm text-slate-300">{envelope.ec_gap_spl_notice}</p>
      ) : null}
      <EcSplCodeBlock spl={spl} maxHeightClass="max-h-64" className="mt-3" />
      {envelope.spl_validation ? (
        <p className="mt-2 text-xs text-slate-400">
          Validator approved: {envelope.spl_validation.approved ? 'yes' : 'no'} · execution_eligible=false
        </p>
      ) : null}
    </article>
  );
}

function PathCard({ view }: { view: EcProjectionView }) {
  const items = (view.items ?? []).filter((item) => item.trim() && item.trim() !== '-');
  const summary = view.summary?.trim() ?? '';
  if (!summary && !items.length) return null;
  return (
    <article
      className="rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 ring-1 ring-slate-800/50"
      data-ec-path-card={view.title}
    >
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-50">{view.title}</h4>
        <Badge variant="outline" className="border-slate-600 text-slate-300">{view.provenance.kind}</Badge>
      </div>
      {view.summary?.trim() ? (
        <p className="mt-3 text-sm font-medium leading-relaxed text-slate-200">{view.summary}</p>
      ) : null}
      {items.length ? (
        <ul className="mt-3 space-y-1.5 text-sm text-slate-300">
          {items.map((item) => (
            <li key={item} className="ec-prose-wrap rounded border border-slate-800/60 bg-slate-950/40 px-2 py-1 font-mono text-xs text-slate-400">
              {item}
            </li>
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
    <article className="rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 ring-1 ring-slate-800/50" data-ec-section="investigation-outcome">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-50">Investigation outcome</h4>
        <Badge>{outcome.disposition}</Badge>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {outcome.confirmed?.length ? (
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-emerald-300">Confirmed</p>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-200">
            {outcome.confirmed.filter(Boolean).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        ) : null}
        {outcome.unconfirmed?.length ? (
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-amber-300">Unconfirmed</p>
          <ul className="mt-2 space-y-1.5 text-sm text-amber-50/90">
            {outcome.unconfirmed.filter(Boolean).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        ) : null}
        {outcome.supported?.length ? (
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-300">Supported</p>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-300">
            {outcome.supported.filter(Boolean).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        ) : null}
        {outcome.missing_evidence?.length ? (
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-300">Missing evidence</p>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-400">
            {outcome.missing_evidence.filter(Boolean).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        ) : null}
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
    <article className="rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 ring-1 ring-slate-800/50" data-ec-section="evidence-state">
      <h4 className="text-sm font-semibold text-slate-50">Evidence state</h4>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-start justify-between gap-3 rounded-md border border-slate-800/60 bg-slate-950/40 px-3 py-2 text-sm">
            <div>
              <p className="text-slate-100">{item.label}</p>
              {item.detail ? <p className="mt-0.5 text-slate-400">{item.detail}</p> : null}
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
    <article className="rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 ring-1 ring-slate-800/50 md:col-span-2" data-ec-section="spl-governance">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-50">SPL governance</h4>
        <Badge variant={governance.validation.search_1_approved && governance.validation.search_2_approved ? 'success' : 'warning'}>
          {governance.validation.search_1_approved && governance.validation.search_2_approved ? 'validate_spl approved' : 'validation failed'}
        </Badge>
      </div>
      <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-cyan-200/90">User request</dt>
          <dd className="mt-2 text-slate-100">{governance.user_request}</dd>
          <p className="mt-1 text-xs text-slate-400">{governance.time_range_supplied ? 'Time range supplied.' : 'No time range supplied.'}</p>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-[0.1em] text-cyan-200/90">Environment governance</dt>
          <dd className="mt-2 text-slate-100">{governance.environment_governance}</dd>
          <p className="mt-1 text-xs text-slate-300">{governance.why}</p>
        </div>
      </dl>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {governance.searches.map((search) => (
          <div key={search.search_id} className="rounded-md border border-slate-700/70 bg-slate-950/50 p-3">
            <p className="text-sm font-medium text-slate-50">{search.label}</p>
            <p className="mt-1 text-xs text-slate-400">{search.earliest} → {search.latest}</p>
            <EcSplCodeBlock
              spl={search.normalized_spl || search.candidate_spl}
              maxHeightClass="max-h-64"
              className="mt-2"
            />
            <p className="mt-2 text-xs text-slate-400">Validator {search.approved ? 'approved' : 'rejected'} · {search.provenance}</p>
          </div>
        ))}
      </div>
      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-300">Controls applied</p>
        <p className="mt-2 text-sm text-slate-300">{governance.controls.join(' · ')}</p>
      </div>
      <p className="mt-3 text-sm text-slate-300">{governance.evidence_merge}</p>
      <p className="mt-1 text-xs text-slate-400">
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
  const path = (envelope.ec_layer2_path ?? [
    'Understanding',
    'Resources',
    'Controls',
    'Evidence',
    'Outcome',
  ]).filter((item) => item.trim());
  return (
    <details
      className="rounded-xl border border-slate-700/80 bg-slate-900/40 p-5 ring-1 ring-slate-800/50 open:bg-slate-900/55"
      data-ec-layer="investigation-path"
    >
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
        <EcSectionHeading>Investigation path</EcSectionHeading>
        <p className="mt-3 text-sm font-medium leading-relaxed text-slate-100">{path.join(' → ')}</p>
        <p className="mt-1 text-xs text-cyan-400/80">Expand for governed pipeline trace (Layer 2)</p>
      </summary>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <EcGapSplPanel envelope={envelope} />
        <PathCard view={projection.understanding} />
        <PathCard view={projection.resource_plan} />
        <EcSplGovernancePanel view={projection.phase_contract} governance={envelope.ec_spl_governance} />
        <EcEvidenceStateBoard view={projection.evidence_state} items={envelope.ec_evidence_state} />
        <EcSiemToolTraces traces={envelope.ec_siem_tool_traces ?? []} />
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
