import type {
  EcAttackChainStep,
  EcDetectionOpportunity,
  EcEvidenceFindingRow,
  EcSiemCoverageAssessment,
  EcSiemToolTrace,
} from '@/components/ec/types';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcDataTable } from '@/components/ec/EcDataTable';
import { EcSplCodeBlock } from '@/components/ec/EcSplCodeBlock';
import { Badge } from '@/components/ui/badge';

function chainStatusClass(status: string): string {
  const token = status.toLowerCase();
  if (token === 'confirmed' || token === 'denied') return 'border-cyan-500/40 bg-cyan-950/30 text-cyan-100';
  if (token === 'none_observed' || token === 'not_confirmed') return 'border-amber-500/30 bg-amber-950/20 text-amber-100';
  return 'border-slate-600 text-slate-200';
}

export function EcAttackChain({ steps }: { steps: EcAttackChainStep[] }) {
  if (!steps.length) return null;
  return (
    <section data-ec-section="attack-chain">
      <EcSectionHeading>Attack → tool → authorization → execution → data</EcSectionHeading>
      <ol className="mt-4 space-y-0">
        {steps.map((step, index) => (
          <li key={step.label} className="flex flex-col items-center">
            <div className={`w-full max-w-md rounded-lg border px-4 py-3 text-center text-sm ${chainStatusClass(step.status)}`}>
              <p className="font-medium text-slate-50">{step.label}</p>
              {step.detail ? <p className="mt-1 text-xs text-slate-300">{step.detail}</p> : null}
              <Badge variant="outline" className="mt-2 border-slate-600 text-xs uppercase tracking-wide">
                {step.status.replace(/_/g, ' ')}
              </Badge>
            </div>
            {index < steps.length - 1 ? (
              <span className="my-1 text-slate-500" aria-hidden="true">↓</span>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function EcSiemCoverageCard({ coverage }: { coverage: EcSiemCoverageAssessment }) {
  const rows = coverage.coverage_rows ?? [];
  return (
    <section data-ec-section="siem-coverage">
      <div className="flex flex-wrap items-center gap-2">
        <EcSectionHeading>SIEM coverage</EcSectionHeading>
        <Badge variant="outline" className="border-cyan-600/50 text-cyan-200">
          {coverage.siem} · {coverage.coverage_status}
        </Badge>
      </div>
      <p className="mt-2 text-sm text-slate-300">
        What Splunk already knew, what was reused, and what required additional governed search.
      </p>
      {rows.length ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-700/80">
          <EcDataTable
            columns={[
              { key: 'investigation_need', label: 'Investigation need' },
              { key: 'siem_status', label: 'Splunk coverage' },
              { key: 'decision', label: 'AI SOC decision' },
            ]}
            rows={rows.map((row) => ({
              investigation_need: row.investigation_need,
              siem_status: row.siem_status,
              decision: row.decision,
            }))}
          />
        </div>
      ) : null}
      {coverage.remaining_gaps?.length ? (
        <ul className="mt-4 space-y-1 text-sm text-slate-400">
          {coverage.remaining_gaps.map((gap) => (
            <li key={gap}>Remaining gap: {gap}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function EcEvidenceFindingsTable({ rows }: { rows: EcEvidenceFindingRow[] }) {
  if (!rows.length) return null;
  return (
    <section data-ec-section="evidence-findings">
      <EcSectionHeading>Evidence findings</EcSectionHeading>
      <div className="mt-4 overflow-x-auto rounded-lg border border-slate-700/80">
        <EcDataTable
          columns={[
            { key: 'investigation_point', label: 'Investigation point' },
            { key: 'finding', label: 'Finding' },
            { key: 'evidence_basis', label: 'Evidence basis' },
          ]}
          rows={rows.map((row) => ({
            investigation_point: row.investigation_point,
            finding: row.finding,
            evidence_basis: row.evidence_basis,
          }))}
        />
      </div>
    </section>
  );
}

export function EcDetectionOpportunityCard({
  opportunity,
  compact = false,
  variant = 'default',
}: {
  opportunity: EcDetectionOpportunity;
  compact?: boolean;
  variant?: 'default' | 'improvement';
}) {
  const isImprovement = variant === 'improvement' || compact;
  return (
    <section
      className={
        isImprovement
          ? 'rounded-md border border-slate-800/70 bg-slate-900/25 px-3 py-2.5'
          : 'rounded-lg border border-violet-500/30 bg-violet-950/20 p-4'
      }
      data-ec-section="detection-opportunity"
      data-ec-detection-variant={isImprovement ? 'improvement' : 'default'}
    >
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-400">
          {isImprovement ? 'Detection improvement' : opportunity.title}
        </p>
        {!isImprovement ? (
          <EcSectionHeading variant="default">{opportunity.title}</EcSectionHeading>
        ) : null}
        <Badge variant="outline" className="border-slate-600 text-slate-400 text-[10px]">
          {opportunity.status}
        </Badge>
      </div>
      <p className="mt-1.5 text-sm text-slate-300">{opportunity.summary}</p>
      {isImprovement ? (
        <p className="mt-1 text-xs text-slate-500">
          Follow-up detection work — not an immediate response action. {opportunity.recommended_action}
        </p>
      ) : (
        <p className="mt-2 text-sm font-medium text-violet-200">Action: {opportunity.recommended_action}</p>
      )}
      {opportunity.notes && !isImprovement ? <p className="mt-2 text-xs text-slate-400">{opportunity.notes}</p> : null}
    </section>
  );
}

export function EcSiemToolTraces({ traces }: { traces: EcSiemToolTrace[] }) {
  if (!traces.length) return null;
  return (
    <section data-ec-section="siem-tool-traces" className="md:col-span-2">
      <EcSectionHeading>MCP tool trace (Splunk)</EcSectionHeading>
      <ul className="mt-4 space-y-3">
        {traces.map((trace, index) => (
          <li key={`${trace.mcp_tool}-${index}`} className="rounded-lg border border-slate-700/80 bg-slate-950/50 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-slate-100">{trace.purpose}</span>
              <Badge variant="outline" className="font-mono text-xs">{trace.mcp_tool}</Badge>
              <Badge variant="outline">{trace.mode}</Badge>
            </div>
            <p className="mt-2 text-slate-300">{trace.capability}</p>
            {trace.detail ? <p className="mt-1 text-xs text-slate-400">{trace.detail}</p> : null}
            {trace.candidate_spl ? (
              <div className="mt-2 min-w-0">
                <EcSplCodeBlock
                  spl={trace.candidate_spl}
                  label="Candidate SPL (not executed)"
                  maxHeightClass="max-h-48"
                />
              </div>
            ) : null}
            {trace.normalized_spl && !trace.candidate_spl ? (
              <EcSplCodeBlock spl={trace.normalized_spl} label="Normalized SPL" maxHeightClass="max-h-48" className="mt-2" />
            ) : null}
            {trace.normalized_spl && trace.candidate_spl ? (
              <EcSplCodeBlock spl={trace.normalized_spl} label="Normalized SPL (authorized)" maxHeightClass="max-h-48" className="mt-2" />
            ) : null}
            {trace.validator_status ? (
              <p className="mt-2 text-xs text-slate-400">
                Validator: {trace.validator_status}
                {trace.exact_call_authorization ? ` · Exact-call authorization: ${trace.exact_call_authorization}` : ''}
              </p>
            ) : null}
            <p className="mt-1 text-xs text-slate-500">Provenance: {trace.provenance}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
