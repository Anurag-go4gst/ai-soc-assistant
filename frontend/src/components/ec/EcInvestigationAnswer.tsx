import type { EcAffectedSystem, ExperienceCenterResponse } from '@/components/ec/types';
import { EcAnswerTitle, EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcAnswerReveal, EcRevealBlock, EcStreamingText } from '@/components/ec/EcAnswerReveal';
import { EcAffectedSystemsTable } from '@/components/ec/EcAffectedSystemsTable';
import { EcDataTable } from '@/components/ec/EcDataTable';
import { EcCollapsibleEvidencePanel } from '@/components/ec/EcCollapsibleEvidence';
import { EcSplArtifactPanel } from '@/components/ec/EcSplArtifactPanel';
import { EcSourceEvidencePanel } from '@/components/ec/EcSourceEvidencePanel';
import {
  EcAttackChain,
  EcDetectionOpportunityCard,
  EcEvidenceFindingsTable,
  EcSiemCoverageCard,
} from '@/components/ec/EcSiemCoverage';
import {
  EcApplicabilityPanel,
  EcClosureSummaryCard,
  EcConflictSourcesCard,
  EcCredibilityStrip,
  EcEvidenceReusePanel,
  EcGapSplNotice,
  EcInvestigationPivotCard,
  EcInvestigationScopeCard,
  EcResourceCompositionPanel,
  EcSplGovernanceSummary,
  EcWorkflowTransitionPanel,
} from '@/components/ec/EcInvestigationQuality';
import { Badge } from '@/components/ui/badge';

function systemsFrom(envelope: ExperienceCenterResponse): EcAffectedSystem[] {
  const analyst = envelope.analyst ?? envelope.analyst_response ?? {};
  if (envelope.ec_affected_systems?.length) return envelope.ec_affected_systems;
  if (analyst.affected_systems?.length) return analyst.affected_systems;
  return [];
}

function layer1SplHidden(envelope: ExperienceCenterResponse): boolean {
  const analyst = envelope.analyst ?? envelope.analyst_response ?? {};
  return Boolean(
    envelope.ec_gap_spl_layer2_only ||
    envelope.ec_spl_governance ||
    envelope.ec_siem_coverage ||
    analyst.spl_code,
  );
}

export function EcInvestigationAnswer({
  envelope,
  embedded = false,
  revealActive = false,
  revealKey = 0,
  highlightEvidenceId = null,
  onRevealStart,
  onRevealComplete,
}: {
  envelope: ExperienceCenterResponse;
  embedded?: boolean;
  revealActive?: boolean;
  revealKey?: number;
  highlightEvidenceId?: string | null;
  onRevealStart?: () => void;
  onRevealComplete?: () => void;
}) {
  const analyst = envelope.analyst ?? envelope.analyst_response ?? {};
  const title = analyst.finding_title || envelope.message;
  const directLine = analyst.direct_answer_line?.trim();
  const assessment = analyst.assessment || analyst.direct_answer_summary || envelope.analyst_summary;
  const found = analyst.what_we_found || analyst.one_sentence_finding || envelope.analyst_summary;
  const systems = systemsFrom(envelope);
  const important = analyst.important_evidence ?? [];
  const unconfirmed = analyst.unconfirmed_findings?.length
    ? analyst.unconfirmed_findings
    : envelope.ec_investigation_outcome?.unconfirmed ?? [];
  const missing = analyst.missing_evidence ?? envelope.ec_investigation_outcome?.missing_evidence ?? [];
  const statusSummary = envelope.ec_status_summary;
  const applicability = envelope.ec_applicability ?? [];
  const tableRows = systems.length ? [] : (analyst.splunk_results_table ?? []);
  const hideSpl = layer1SplHidden(envelope);

  const isS1 = envelope.scenario_id === 's1_governed_splunk_investigation';
  const attackChainPrimary = Boolean(envelope.ec_attack_chain?.length);
  const showNarrative =
    !attackChainPrimary &&
    assessment &&
    assessment.trim() !== (directLine?.trim() ?? '');
  const showWhatWeFound =
    !attackChainPrimary &&
    found &&
    found.trim() !== (assessment?.trim() ?? '') &&
    found.trim() !== (directLine?.trim() ?? '');
  const showFindingsTable =
    envelope.ec_evidence_findings?.length && !attackChainPrimary;

  const collapsibleEvidence =
    envelope.ec_siem_coverage ||
    envelope.ec_spl_governance_summary ||
    envelope.ec_evidence_reuse?.length ||
    envelope.ec_investigation_scope;
  const inlineResourceComposition = envelope.ec_resource_composition?.length && !isS1;

  const content = (
    <EcAnswerReveal
      active={revealActive}
      revealKey={revealKey}
      onRevealStart={onRevealStart}
      onRevealComplete={onRevealComplete}
    >
      <EcRevealBlock>
        <header className="min-w-0 space-y-2">
          <EcAnswerTitle>{title}</EcAnswerTitle>
          <div className="flex flex-wrap items-center gap-2">
            {analyst.severity_label ? (
              <Badge className="bg-cyan-600/90 text-white hover:bg-cyan-600/90">{analyst.severity_label}</Badge>
            ) : null}
            {envelope.ec_workflow_state ? (
              <Badge variant="outline" className="border-cyan-500/40 text-cyan-100">
                {envelope.ec_workflow_state.replace(/_/g, ' ')}
              </Badge>
            ) : null}
          </div>
          {statusSummary ? (
            <p className="text-sm font-medium leading-relaxed text-cyan-100/90">{statusSummary}</p>
          ) : null}
        </header>
      </EcRevealBlock>

      {attackChainPrimary ? (
        <EcRevealBlock>
          <EcAttackChain steps={envelope.ec_attack_chain!} />
        </EcRevealBlock>
      ) : null}

      {directLine ? (
        <EcRevealBlock>
          <p className="text-base font-medium leading-relaxed text-slate-50">
            <EcStreamingText text={directLine} active={revealActive} />
          </p>
        </EcRevealBlock>
      ) : null}

      {showNarrative ? (
        <EcRevealBlock>
          {directLine || attackChainPrimary ? (
            <p className="ec-prose-wrap text-sm leading-relaxed text-slate-200">
              <EcStreamingText text={assessment ?? ''} active={revealActive} />
            </p>
          ) : (
            <>
              <EcSectionHeading>Assessment</EcSectionHeading>
              <p className="ec-prose-wrap mt-3 text-base leading-relaxed text-slate-100">{assessment}</p>
            </>
          )}
        </EcRevealBlock>
      ) : null}

      {showWhatWeFound ? (
        <EcRevealBlock>
          <EcSectionHeading>What we found</EcSectionHeading>
          <p className="ec-prose-wrap mt-3 text-sm leading-relaxed text-slate-200">{found}</p>
        </EcRevealBlock>
      ) : null}

      <EcWorkflowTransitionPanel envelope={envelope} />

      {systems.length ? (
        <EcAffectedSystemsTable systems={systems} />
      ) : tableRows.length ? (
        <EcRevealBlock>
          <EcSectionHeading>Affected systems</EcSectionHeading>
          <div className="mt-3 overflow-x-auto rounded-lg border border-slate-700/80">
            <EcDataTable
              columns={Object.keys(tableRows[0] ?? {}).slice(0, 7).map((key) => ({ key, label: key }))}
              rows={tableRows.slice(0, 8).map((row) =>
                Object.fromEntries(
                  Object.entries(row).map(([k, v]) => [k, String(v ?? '')]),
                ),
              )}
            />
          </div>
        </EcRevealBlock>
      ) : null}

      {envelope.ec_investigation_pivot ? (
        <EcRevealBlock>
          <EcInvestigationPivotCard pivot={envelope.ec_investigation_pivot} />
        </EcRevealBlock>
      ) : null}

      {important.length ? (
        <EcRevealBlock>
          <EcSectionHeading>Key evidence</EcSectionHeading>
          <ul className="mt-3 space-y-2 text-sm text-slate-100">
            {important.slice(0, isS1 ? 5 : 8).map((item) => (
              <li key={item} className="rounded-md border border-slate-800/80 bg-slate-900/40 px-3 py-2">{item}</li>
            ))}
          </ul>
        </EcRevealBlock>
      ) : null}

      {envelope.source_evidence?.length ? (
        <EcRevealBlock>
          <EcSourceEvidencePanel items={envelope.source_evidence} highlightEvidenceId={highlightEvidenceId} />
        </EcRevealBlock>
      ) : null}

      {envelope.ec_investigation_outcome?.closure_summary ? (
        <EcRevealBlock>
          <EcClosureSummaryCard summary={envelope.ec_investigation_outcome.closure_summary} />
        </EcRevealBlock>
      ) : null}

      {collapsibleEvidence ? (
        <EcRevealBlock>
          <EcCollapsibleEvidencePanel>
            {envelope.ec_siem_coverage ? (
              <EcSiemCoverageCard coverage={envelope.ec_siem_coverage} />
            ) : null}
            {envelope.ec_spl_governance_summary ? (
              <EcSplGovernanceSummary summary={envelope.ec_spl_governance_summary} />
            ) : null}
            {envelope.ec_evidence_reuse?.length ? (
              <EcEvidenceReusePanel rows={envelope.ec_evidence_reuse} />
            ) : null}
            {envelope.ec_investigation_scope ? (
              <EcInvestigationScopeCard scope={envelope.ec_investigation_scope} />
            ) : null}
          </EcCollapsibleEvidencePanel>
        </EcRevealBlock>
      ) : null}

      {inlineResourceComposition ? (
        <EcRevealBlock>
          <EcResourceCompositionPanel rows={envelope.ec_resource_composition!} />
        </EcRevealBlock>
      ) : null}

      {envelope.ec_conflict?.status === 'CONFLICTING' ? (
        <EcRevealBlock>
          <EcConflictSourcesCard envelope={envelope} />
        </EcRevealBlock>
      ) : null}

      {showFindingsTable ? (
        <EcRevealBlock>
          <EcEvidenceFindingsTable rows={envelope.ec_evidence_findings!} />
        </EcRevealBlock>
      ) : null}

      {!hideSpl ? <EcSplArtifactPanel analyst={analyst} /> : null}

      {envelope.ec_gap_spl_notice ? (
        <EcRevealBlock>
          <EcGapSplNotice notice={envelope.ec_gap_spl_notice} />
        </EcRevealBlock>
      ) : null}

      {envelope.candidate_spl?.candidate_spl && !analyst.spl_code && !hideSpl ? (
        <EcRevealBlock>
          <EcSectionHeading>Candidate SPL</EcSectionHeading>
          <p className="mt-2 text-sm text-slate-400">Review-only candidate — see Investigation path for full governance trace.</p>
        </EcRevealBlock>
      ) : null}

      <EcRevealBlock>
        <EcSectionHeading variant="warning">What remains unconfirmed</EcSectionHeading>
        <ul className="mt-3 space-y-2 text-sm text-amber-50/95">
          {unconfirmed.length ? unconfirmed.map((item) => (
            <li key={item} className="rounded-md border border-amber-500/20 bg-amber-950/20 px-3 py-2">{item}</li>
          )) : (
            <li className="text-amber-100/80">No additional unconfirmed claims beyond the governed fixture evidence.</li>
          )}
        </ul>
      </EcRevealBlock>

      {missing.length ? (
        <EcRevealBlock>
          <EcSectionHeading>Evidence still required</EcSectionHeading>
          <ul className="mt-3 space-y-2 text-sm text-slate-300">
            {missing.map((item) => (
              <li key={item} className="rounded-md border border-slate-800 bg-slate-900/30 px-3 py-2">{item}</li>
            ))}
          </ul>
        </EcRevealBlock>
      ) : null}

      {applicability.length ? (
        <EcRevealBlock>
          <EcApplicabilityPanel rows={applicability} />
        </EcRevealBlock>
      ) : null}

      {envelope.ec_detection_opportunity ? (
        <EcRevealBlock>
          <EcDetectionOpportunityCard
            opportunity={envelope.ec_detection_opportunity}
            variant={attackChainPrimary ? 'improvement' : 'default'}
            compact={attackChainPrimary}
          />
        </EcRevealBlock>
      ) : null}

      <EcRevealBlock>
        <EcCredibilityStrip envelope={envelope} />
      </EcRevealBlock>
    </EcAnswerReveal>
  );

  if (embedded) {
    return (
      <section data-ec-layer="soc-answer" className="min-w-0 w-full max-w-full rounded-xl border border-slate-800/60 bg-slate-950/30 p-4 lg:p-5">
        {content}
      </section>
    );
  }

  return (
    <section className="soc-panel min-w-0 w-full max-w-full space-y-5 rounded-xl p-5" data-ec-layer="soc-answer">
      {content}
    </section>
  );
}
