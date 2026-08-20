import { Badge } from '@/components/ui/badge';
import type { EcAffectedSystem, EcSourceEvidenceItem, ExperienceCenterResponse } from '@/components/ec/types';
import { EcAnswerTitle, EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcAnswerReveal, EcRevealBlock, EcStreamingText } from '@/components/ec/EcAnswerReveal';
import { EcAffectedSystemsTable } from '@/components/ec/EcAffectedSystemsTable';
import { EcDataTable } from '@/components/ec/EcDataTable';
import { EcCollapsibleEvidencePanel } from '@/components/ec/EcCollapsibleEvidence';
import { EcSplArtifactPanel } from '@/components/ec/EcSplArtifactPanel';
import { EcSplCodeBlock } from '@/components/ec/EcSplCodeBlock';
import { EcSourceEvidencePanel } from '@/components/ec/EcSourceEvidencePanel';
import { EcWhatWeFoundBlock } from '@/components/ec/EcWhatWeFoundBlock';
import { EcAgentWorkflow } from '@/components/ec/EcAgentWorkflow';
import { isAgentWorkflowMode } from '@/lib/ecAgentWorkflow';
import {
  EcAgilusPatchPanel,
  EcCapabilityPlanPanel,
  EcExecutiveSummaryPanel,
  EcInvestigationPhasesPanel,
  EcOpeningBriefingPanel,
  EcVpnGatewayPosturePanel,
} from '@/components/ec/EcInvestigationPosture';
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
  EcEvidenceReusePanel,
  EcGapSplNotice,
  EcInvestigationPivotCard,
  EcInvestigationScopeCard,
  EcResourceCompositionPanel,
  EcSplGovernanceSummary,
  EcWorkflowTransitionPanel,
} from '@/components/ec/EcInvestigationQuality';

function sourceEvidenceHint(items: EcSourceEvidenceItem[]): string {
  const labels: string[] = [];
  const seen = new Set<string>();
  const add = (label: string) => {
    if (seen.has(label)) return;
    seen.add(label);
    labels.push(label);
  };
  for (const item of items) {
    const blob = `${item.source_type} ${item.source_name} ${item.tool_name ?? ''} ${item.provenance ?? ''}`.toLowerCase();
    if (blob.includes('agilus')) add('Agilus');
    if (blob.includes('splunk')) add('Splunk MCP');
    if (
      blob.includes('soc-kb') ||
      blob.includes('retrieve_soc_kb') ||
      blob.includes('rag') ||
      blob.includes('knowledge')
    ) {
      add('SOC-KB / RAG');
    }
    if (blob.includes('identity') || blob.includes('inventory')) add('inventory fixture');
    if (blob.includes('itsm') || blob.includes('ticket')) add('ITSM');
  }
  if (!labels.length) return `${items.length} items`;
  return `${items.length} items — collected from ${labels.join(', ')}.`;
}

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
  onEvidenceLinkClick,
  onStepAction,
  stepActionBusy = false,
  onAgentRunInvestigation,
  onAgentRunRemediation,
  onAgentHilApprove,
  onAgentHilSkip,
  onCreateRemediationPlan,
  onDeclineRemediationPlan,
  agentExecutionProgress = null,
  onViewEvidence,
  onEcActionUpdate,
  onRevealStart,
  onRevealComplete,
}: {
  envelope: ExperienceCenterResponse;
  embedded?: boolean;
  revealActive?: boolean;
  revealKey?: number;
  highlightEvidenceId?: string | null;
  onEvidenceLinkClick?: (evidenceId: string) => void;
  onStepAction?: (followUpId: string) => void;
  stepActionBusy?: boolean;
  onAgentRunInvestigation?: (selectedStepIds: string[]) => void;
  onAgentRunRemediation?: (selectedStepIds: string[]) => void;
  onAgentHilApprove?: () => void;
  onAgentHilSkip?: () => void;
  onCreateRemediationPlan?: () => void;
  onDeclineRemediationPlan?: () => void;
  agentExecutionProgress?: import('@/lib/experienceCenterExecution').ExperienceExecutionProgressView | null;
  onViewEvidence?: () => void;
  onEcActionUpdate?: (action: import('@/components/ec/types').EcActionRecord) => void;
  onRevealStart?: () => void;
  onRevealComplete?: () => void;
}) {
  const analyst = envelope.analyst ?? envelope.analyst_response ?? {};
  const title = analyst.finding_title || envelope.message;
  const directLine = analyst.direct_answer_line?.trim();
  const assessment = analyst.assessment || analyst.direct_answer_summary || envelope.analyst_summary;
  const found = analyst.what_we_found || analyst.one_sentence_finding || envelope.analyst_summary;
  const systems = systemsFrom(envelope);
  const important = (analyst.important_evidence ?? []).filter((item) => item.trim());
  const unconfirmed = (analyst.unconfirmed_findings?.length
    ? analyst.unconfirmed_findings
    : envelope.ec_investigation_outcome?.unconfirmed ?? []
  ).filter((item) => item.trim());
  const missing = (analyst.missing_evidence ?? envelope.ec_investigation_outcome?.missing_evidence ?? []).filter(
    (item) => item.trim(),
  );
  const statusSummary = envelope.ec_status_summary;
  const applicability = envelope.ec_applicability ?? [];
  const tableRows = systems.length ? [] : (analyst.splunk_results_table ?? []);
  const hideSpl = layer1SplHidden(envelope);

  const isS1 = envelope.scenario_id === 's1_governed_splunk_investigation';
  const isS4 = envelope.scenario_id === 's4_zero_day_no_playbook';
  const agentWorkflow = envelope.ec_agent_workflow;
  const agentMode = isAgentWorkflowMode(envelope);
  const actionPlan = analyst.recommended_actions ?? [];
  const attackChainPrimary = Boolean(envelope.ec_attack_chain?.length);
  const showNarrative =
    !agentMode &&
    !attackChainPrimary &&
    !isS4 &&
    assessment &&
    assessment.trim() !== (directLine?.trim() ?? '');
  const showWhatWeFound =
    !agentMode &&
    !attackChainPrimary &&
    !isS4 &&
    found &&
    found.trim() !== (assessment?.trim() ?? '') &&
    found.trim() !== (directLine?.trim() ?? '');
  const showFindingsTable =
    !agentMode && Boolean(envelope.ec_evidence_findings?.length) && !attackChainPrimary;

  const collapsibleEvidence =
    !agentMode &&
    Boolean(
      envelope.ec_siem_coverage ||
        envelope.ec_spl_governance_summary ||
        envelope.ec_evidence_reuse?.length ||
        envelope.ec_investigation_scope,
    );
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

      {agentMode && agentWorkflow ? (
        <EcRevealBlock>
          <EcAgentWorkflow
            workflow={agentWorkflow}
            busy={stepActionBusy}
            executionProgress={agentExecutionProgress}
            onRunInvestigation={(ids) => onAgentRunInvestigation?.(ids)}
            onRunRemediation={(ids) => onAgentRunRemediation?.(ids)}
            onHilApprove={() => onAgentHilApprove?.()}
            onHilSkip={() => onAgentHilSkip?.()}
            onCreateRemediationPlan={() => onCreateRemediationPlan?.()}
            onDeclineRemediationPlan={() => onDeclineRemediationPlan?.()}
            onViewEvidence={onViewEvidence}
            scenarioId={envelope.scenario_id}
            sessionId={envelope.ec_session_state?.session_id}
            ecActions={envelope.ec_actions}
            onEcActionUpdate={onEcActionUpdate}
          />
        </EcRevealBlock>
      ) : null}

      {!agentMode && envelope.ec_opening_briefing ? (
        <EcRevealBlock>
          <EcOpeningBriefingPanel text={envelope.ec_opening_briefing} />
        </EcRevealBlock>
      ) : null}

      {attackChainPrimary ? (
        <EcRevealBlock>
          <EcAttackChain steps={envelope.ec_attack_chain!} />
        </EcRevealBlock>
      ) : null}

      {directLine && !envelope.ec_investigation_phases?.length ? (
        <EcRevealBlock>
          <p className="text-base font-medium leading-relaxed text-slate-50">
            <EcStreamingText text={directLine} active={revealActive} />
          </p>
        </EcRevealBlock>
      ) : null}

      {directLine && envelope.ec_investigation_phases?.length ? (
        <EcRevealBlock>
          <p className="text-base font-semibold leading-relaxed text-slate-50">{directLine}</p>
        </EcRevealBlock>
      ) : null}

      {!agentMode && envelope.ec_investigation_phases?.length ? (
        <EcRevealBlock>
          <EcInvestigationPhasesPanel
            phases={envelope.ec_investigation_phases}
            onStepAction={onStepAction}
            actionBusy={stepActionBusy}
          />
        </EcRevealBlock>
      ) : null}

      {!agentMode && envelope.ec_executive_summary?.length ? (
        <EcRevealBlock>
          <EcExecutiveSummaryPanel bullets={envelope.ec_executive_summary} />
        </EcRevealBlock>
      ) : null}

      {envelope.ec_vpn_gateway_posture?.length && !agentMode ? (
        <EcRevealBlock>
          <EcVpnGatewayPosturePanel rows={envelope.ec_vpn_gateway_posture} />
        </EcRevealBlock>
      ) : null}

      {envelope.ec_capability_plan?.length && !isS4 ? (
        <EcRevealBlock>
          <EcCapabilityPlanPanel rows={envelope.ec_capability_plan} />
        </EcRevealBlock>
      ) : null}

      {envelope.ec_agilus_patch && !envelope.ec_investigation_phases?.length ? (
        <EcRevealBlock>
          <EcAgilusPatchPanel patch={envelope.ec_agilus_patch} />
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
          <EcWhatWeFoundBlock
            segments={analyst.what_we_found_segments}
            fallbackText={found}
            onEvidenceLinkClick={onEvidenceLinkClick}
          />
        </EcRevealBlock>
      ) : null}

      {!agentMode ? <EcWorkflowTransitionPanel envelope={envelope} /> : null}

      {!agentMode && systems.length ? (
        <EcAffectedSystemsTable systems={systems} />
      ) : !agentMode && tableRows.length ? (
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

      {envelope.ec_investigation_pivot && !agentMode ? (
        <EcRevealBlock>
          <EcInvestigationPivotCard pivot={envelope.ec_investigation_pivot} />
        </EcRevealBlock>
      ) : null}

      {!agentMode && important.length ? (
        <EcRevealBlock>
          <EcSectionHeading>{isS4 ? 'Claim verification' : 'Key evidence'}</EcSectionHeading>
          <ul className="mt-3 space-y-2 text-sm text-slate-100">
            {important.slice(0, isS1 ? 5 : 8).map((item) => (
              <li key={item} className="rounded-md border border-slate-800/80 bg-slate-900/40 px-3 py-2">{item}</li>
            ))}
          </ul>
        </EcRevealBlock>
      ) : null}

      {actionPlan.length && !envelope.ec_investigation_phases?.length && !agentMode ? (
        <EcRevealBlock>
          <EcSectionHeading>Action plan</EcSectionHeading>
          <ul className="mt-3 space-y-2 text-sm text-slate-100">
            {actionPlan.map((item) => (
              <li
                key={item}
                className={
                  item.startsWith('DONE')
                    ? 'rounded-md border border-cyan-500/25 bg-cyan-950/20 px-3 py-2 text-cyan-50'
                    : item.startsWith('NEXT')
                      ? 'rounded-md border border-amber-500/30 bg-amber-950/15 px-3 py-2 text-amber-50'
                      : 'rounded-md border border-slate-800/80 bg-slate-900/40 px-3 py-2'
                }
              >
                {item}
              </li>
            ))}
          </ul>
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

      {!agentMode && envelope.ec_gap_spl_notice ? (
        <EcRevealBlock>
          <EcGapSplNotice notice={envelope.ec_gap_spl_notice} />
        </EcRevealBlock>
      ) : null}

      {envelope.candidate_spl?.candidate_spl && !analyst.spl_code && !hideSpl ? (
        <EcRevealBlock>
          <EcSectionHeading>Candidate SPL</EcSectionHeading>
          <p className="mt-2 text-sm text-slate-400">Review-only candidate — not executed.</p>
          <EcSplCodeBlock spl={envelope.candidate_spl.candidate_spl} className="mt-3" />
        </EcRevealBlock>
      ) : null}

      {!agentMode && unconfirmed.length ? (
        <EcRevealBlock>
          <EcSectionHeading variant="warning">What remains unconfirmed</EcSectionHeading>
          <ul className="mt-3 space-y-2 text-sm text-amber-50/95">
            {unconfirmed.map((item) => (
              <li key={item} className="rounded-md border border-amber-500/20 bg-amber-950/20 px-3 py-2">{item}</li>
            ))}
          </ul>
        </EcRevealBlock>
      ) : null}

      {!agentMode && missing.length ? (
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

      {envelope.source_evidence?.length ? (
        <EcRevealBlock>
          <EcCollapsibleEvidencePanel
            summary="Source evidence"
            hint={sourceEvidenceHint(envelope.source_evidence)}
          >
            <EcSourceEvidencePanel items={envelope.source_evidence} highlightEvidenceId={highlightEvidenceId} />
          </EcCollapsibleEvidencePanel>
        </EcRevealBlock>
      ) : null}

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
