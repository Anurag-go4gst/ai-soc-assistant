import type {
  EcActionReadinessRow,
  EcEvidenceReuseRow,
  EcInvestigationPivot,
  EcInvestigationScope,
  EcResourceCompositionRow,
  ExperienceCenterResponse,
} from '@/components/ec/types';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcDataTable } from '@/components/ec/EcDataTable';
import { Badge } from '@/components/ui/badge';

function statusBadgeClass(status: string): string {
  const token = status.toUpperCase();
  if (token === 'OBTAINED' || token === 'VERIFIED' || token === 'READY' || token === 'RECOMMENDED' || token === 'REUSED') {
    return 'border-cyan-500/40 text-cyan-100';
  }
  if (token.includes('NOT_RECOMMENDED') || token === 'MISSING') {
    return 'border-amber-500/40 text-amber-100';
  }
  return 'border-slate-600 text-slate-300';
}

export function EcInvestigationScopeCard({ scope }: { scope: EcInvestigationScope }) {
  return (
    <section data-ec-section="investigation-scope">
      <EcSectionHeading>Investigation scope</EcSectionHeading>
      <p className="ec-prose-wrap mt-3 text-sm text-slate-200">
        <span className="font-medium text-slate-100">Time: </span>{scope.time_range}
      </p>
      {scope.telemetry_queried?.length ? (
        <p className="ec-prose-wrap mt-2 text-sm text-slate-300">
          <span className="font-medium text-slate-200">Telemetry evaluated: </span>
          {scope.telemetry_queried.join(' · ')}
        </p>
      ) : null}
      {scope.telemetry_sources?.length ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-700/80">
          <EcDataTable
            columns={[
              { key: 'source', label: 'Communication source' },
              { key: 'status', label: 'Status' },
              { key: 'detail', label: 'Detail' },
            ]}
            rows={scope.telemetry_sources.map((row) => ({
              source: row.source,
              status: row.status,
              detail: row.detail ?? '',
            }))}
          />
        </div>
      ) : null}
      {scope.scope_note ? (
        <p className="ec-prose-wrap mt-3 text-sm text-slate-400">{scope.scope_note}</p>
      ) : null}
    </section>
  );
}

export function EcInvestigationPivotCard({ pivot }: { pivot: EcInvestigationPivot }) {
  return (
    <section
      className="rounded-lg border border-cyan-500/25 bg-cyan-950/20 p-4"
      data-ec-section="investigation-pivot"
    >
      <EcSectionHeading>{pivot.title}</EcSectionHeading>
      {pivot.subject ? (
        <p className="mt-2 text-sm font-medium text-cyan-100">{pivot.subject}</p>
      ) : null}
      <p className="ec-prose-wrap mt-2 text-sm leading-relaxed text-slate-200">{pivot.summary}</p>
    </section>
  );
}

export function EcClosureSummaryCard({ summary }: { summary: string }) {
  if (!summary.trim()) return null;
  return (
    <section data-ec-section="closure-summary">
      <EcSectionHeading>Closure summary</EcSectionHeading>
      <p className="ec-prose-wrap mt-3 text-sm leading-relaxed text-slate-200">{summary}</p>
    </section>
  );
}

function fixtureDataBadgeVisible(envelope: ExperienceCenterResponse): boolean {
  const splWarnings = envelope.spl_validation?.warnings ?? [];
  if (splWarnings.includes('demo_fixture_not_live_data')) return true;
  return (envelope.source_evidence ?? []).some((item) =>
    (item.warnings ?? []).some(
      (warning) => warning === 'coe_synthetic_fixture' || warning === 'no_live_customer_data',
    ),
  );
}

export function EcCredibilityStrip({ envelope }: { envelope: ExperienceCenterResponse }) {
  const provenance = envelope.ec_provenance ?? {};
  const liveFlags: Array<{ key: string; label: string }> = [
    { key: 'live_llm_called', label: 'Live model: off' },
    { key: 'live_mcp_called', label: 'Live MCP: off' },
    { key: 'live_rag_called', label: 'Live RAG: off' },
  ];
  const liveBadges = liveFlags
    .filter(({ key }) => provenance[key] === false)
    .map(({ label }) => label);
  const splValidator =
    envelope.ec_spl_governance?.validation?.provenance === 'production_validator_read_only' ||
    provenance.production_validator_read_only === true;
  const showFixtureBadge = fixtureDataBadgeVisible(envelope);
  const isS5 = envelope.scenario_id === 's5_cisco_hardening_remediation';

  if (!liveBadges.length && !splValidator && !showFixtureBadge && !isS5) return null;

  return (
    <section data-ec-section="credibility-strip" className="mt-2 space-y-2 border-t border-slate-800/80 pt-4">
      <div className="flex flex-wrap gap-2">
        {liveBadges.map((label) => (
          <Badge key={label} variant="outline" className="border-slate-600 text-slate-300">
            {label}
          </Badge>
        ))}
        {splValidator ? (
          <Badge variant="outline" className="border-cyan-500/40 text-cyan-100">
            SPL: production validate_spl
          </Badge>
        ) : null}
        {showFixtureBadge ? (
          <Badge variant="outline" className="border-amber-500/40 text-amber-100">
            Fixture data · not live customer telemetry
          </Badge>
        ) : null}
      </div>
      {isS5 ? (
        <p className="text-xs text-slate-400">
          Cisco device MCP (simulated router API) on this path — Foundation-Sec 8B LLM is not used here.
        </p>
      ) : null}
    </section>
  );
}

export function EcActionReadinessPanel({
  rows,
  highlightAction = null,
}: {
  rows: EcActionReadinessRow[];
  highlightAction?: string | null;
}) {
  if (!rows.length) return null;
  const normalizedHighlight = highlightAction?.trim().toLowerCase() ?? '';
  return (
    <section data-ec-section="action-readiness">
      <EcSectionHeading>Action readiness</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-400">Readiness reflects current evidence — destructive actions stay conditional.</p>
      <ul className="mt-4 space-y-2">
        {rows.map((row) => {
          const isHighlighted =
            normalizedHighlight.length > 0 &&
            (row.action.toLowerCase().includes(normalizedHighlight) ||
              normalizedHighlight.includes(row.action.toLowerCase().slice(0, 14)));
          return (
            <li
              key={row.action}
              data-ec-readiness-highlight={isHighlighted ? 'true' : undefined}
              className={
                isHighlighted
                  ? 'flex flex-wrap items-center justify-between gap-2 rounded-md border border-cyan-400/50 bg-cyan-950/35 px-3 py-2 ring-1 ring-cyan-400/25'
                  : 'flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-800/80 bg-slate-900/40 px-3 py-2'
              }
            >
              <span className="ec-prose-wrap text-sm text-slate-100">{row.action}</span>
              <Badge variant="outline" className={statusBadgeClass(row.state)}>{row.state.replace(/_/g, ' ')}</Badge>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function EcEvidenceReusePanel({ rows }: { rows: EcEvidenceReuseRow[] }) {
  if (!rows.length) return null;
  return (
    <section data-ec-section="evidence-reuse">
      <EcSectionHeading>Evidence reuse</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-400">Confirmed prior evidence is reused — no new Splunk search required for coordination.</p>
      <div className="mt-4 overflow-x-auto rounded-lg border border-slate-700/80">
        <EcDataTable
          columns={[
            { key: 'label', label: 'Evidence' },
            { key: 'origin', label: 'Origin' },
            { key: 'status', label: 'Status' },
            { key: 'detail', label: 'Detail' },
          ]}
          rows={rows.map((row) => ({
            label: row.label,
            origin: row.origin,
            status: row.status,
            detail: row.detail ?? '',
          }))}
        />
      </div>
    </section>
  );
}

export function EcResourceCompositionPanel({ rows }: { rows: EcResourceCompositionRow[] }) {
  if (!rows.length) return null;
  return (
    <section data-ec-section="resource-composition">
      <EcSectionHeading>Resource composition</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-400">Each resource has a distinct role — Splunk is not device management.</p>
      <div className="mt-4 overflow-x-auto rounded-lg border border-slate-700/80">
        <EcDataTable
          columns={[
            { key: 'resource', label: 'Resource' },
            { key: 'role', label: 'Role' },
            { key: 'mode', label: 'Mode' },
            { key: 'note', label: 'Note' },
          ]}
          rows={rows.map((row) => ({
            resource: row.resource,
            role: row.role,
            mode: row.mode,
            note: row.note ?? '',
          }))}
        />
      </div>
    </section>
  );
}

export function EcSplGovernanceSummary({ summary }: { summary: string }) {
  return (
    <p className="ec-prose-wrap mt-3 rounded-md border border-slate-800/80 bg-slate-900/30 px-3 py-2 text-sm text-slate-200" data-ec-section="spl-governance-summary">
      {summary}
    </p>
  );
}

function applicabilityBadgeClass(status: string): string {
  const token = status.toUpperCase().replace(/-/g, '_');
  if (token.includes('REUSABLE')) return 'border-cyan-500/40 text-cyan-100 bg-cyan-950/30';
  if (token === 'STALE') return 'border-amber-500/40 text-amber-100 bg-amber-950/25';
  if (token.includes('OUT_OF_SCOPE')) return 'border-slate-500/50 text-slate-300 bg-slate-900/50';
  if (token === 'SUPERSEDED' || token === 'INVALIDATED') return 'border-slate-600 text-slate-400';
  if (token === 'BLOCKED') return 'border-rose-500/40 text-rose-100 bg-rose-950/25';
  return 'border-slate-600 text-slate-300';
}

export function EcApplicabilityPanel({
  rows,
}: {
  rows: Array<{ key?: string; status: string; reason?: string }>;
}) {
  if (!rows.length) return null;
  return (
    <section data-ec-section="evidence-applicability">
      <EcSectionHeading>Evidence applicability</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-400">Prior evidence is classified — reuse intelligence, not identical reruns.</p>
      <ul className="mt-4 flex flex-wrap gap-2">
        {rows.map((item) => (
          <li
            key={`${item.key ?? item.status}-${item.reason ?? ''}`}
            className="min-w-[12rem] max-w-full flex-1 rounded-md border border-slate-800/80 bg-slate-900/40 px-3 py-2"
          >
            <div className="flex flex-wrap items-center gap-2">
              {item.key ? <span className="text-xs font-mono text-slate-400">{item.key}</span> : null}
              <Badge variant="outline" className={applicabilityBadgeClass(item.status)}>
                {item.status.replace(/_/g, ' ')}
              </Badge>
            </div>
            {item.reason ? <p className="ec-prose-wrap mt-2 text-sm text-slate-200">{item.reason}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function EcGapSplNotice({ notice }: { notice: string }) {
  return (
    <p
      className="ec-prose-wrap rounded-md border border-cyan-500/25 bg-cyan-950/20 px-3 py-2 text-sm text-cyan-100/95"
      data-ec-section="gap-spl-notice"
    >
      {notice}
    </p>
  );
}

export function EcConflictSourcesCard({ envelope }: { envelope: { ec_conflict?: { status?: string; sources?: string[] }; analyst?: { splunk_results_table?: Array<Record<string, unknown>> } | null } }) {
  const conflict = envelope.ec_conflict;
  if (!conflict || conflict.status !== 'CONFLICTING') return null;
  const table = envelope.analyst?.splunk_results_table ?? [];
  return (
    <section
      className="rounded-lg border border-amber-500/30 bg-amber-950/15 p-4"
      data-ec-section="conflict-sources"
    >
      <EcSectionHeading variant="warning">Conflicting evidence sources</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-200">
        Telemetry and asset records disagree — resolve before forcing incident disposition or destructive actions.
      </p>
      {table.length ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-700/80">
          <EcDataTable
            columns={Object.keys(table[0] ?? {}).map((key) => ({ key, label: key }))}
            rows={table.map((row) =>
              Object.fromEntries(Object.entries(row).map(([k, v]) => [k, String(v ?? '')])),
            )}
          />
        </div>
      ) : null}
      {conflict.sources?.length ? (
        <p className="mt-3 text-xs text-slate-400">Sources in conflict: {conflict.sources.join(' · ')}</p>
      ) : null}
    </section>
  );
}

const S3_TRANSITION_STEPS = [
  'Awaiting response',
  'Reply received',
  'Evidence updated',
  'Outcome reassessed',
  'Action readiness updated',
] as const;

export function EcWorkflowTransitionPanel({
  envelope,
}: {
  envelope: {
    ec_workflow_state?: string;
    ec_email?: { inbound?: string | null; status?: string };
    ec_session_state?: { awaiting_external?: boolean };
    ec_investigation_outcome?: { disposition?: string };
  };
}) {
  const inbound = Boolean(envelope.ec_email?.inbound);
  const awaiting =
    envelope.ec_session_state?.awaiting_external ||
    envelope.ec_workflow_state === 'AWAITING_FIREWALL_TEAM_CONFIRMATION';
  const postReply =
    inbound ||
    envelope.ec_workflow_state === 'Decision' ||
    envelope.ec_investigation_outcome?.disposition === 'needs_reassessment';

  if (!awaiting && !postReply) return null;

  const activeThrough = inbound || envelope.ec_workflow_state === 'Decision' ? 4 : awaiting ? 0 : -1;
  if (activeThrough < 0) return null;

  const prominent = postReply && !awaiting;

  return (
    <section
      className={
        prominent
          ? 'rounded-lg border-2 border-cyan-400/45 bg-cyan-950/35 p-4 ring-1 ring-cyan-400/20'
          : 'rounded-lg border border-cyan-500/20 bg-cyan-950/15 p-4'
      }
      data-ec-section="workflow-transition"
      data-ec-workflow-prominent={prominent ? 'true' : undefined}
    >
      <p className={prominent ? 'text-sm font-semibold text-cyan-100' : 'soc-eyebrow text-cyan-400'}>
        {prominent ? 'Team reply changed the investigation' : 'Coordination workflow'}
      </p>
      {prominent ? (
        <p className="mt-1 text-xs text-cyan-200/80">
          Inbound evidence updated outcome and action readiness — reassessment required before block or close.
        </p>
      ) : null}
      <ol className="mt-3 flex flex-wrap gap-2">
        {S3_TRANSITION_STEPS.map((step, index) => {
          const done = index <= activeThrough;
          const current = index === activeThrough;
          return (
            <li
              key={step}
              className={
                done
                  ? current
                    ? 'rounded-md border border-cyan-400/50 bg-cyan-950/40 px-3 py-1.5 text-xs font-medium text-cyan-100'
                    : 'rounded-md border border-slate-700/80 bg-slate-900/50 px-3 py-1.5 text-xs text-slate-300'
                  : 'rounded-md border border-slate-800/60 px-3 py-1.5 text-xs text-slate-500'
              }
            >
              {step}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
