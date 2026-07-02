import { Badge } from '@/components/ui/badge';
import type React from 'react';
import {
  BookOpen,
  ChevronRight,
  Cpu,
  Crosshair,
  Database,
  FileSearch,
  ListChecks,
  ShieldAlert,
  Terminal,
} from 'lucide-react';
import type { AnalystResponseEnvelope, FoundationSecGovernance } from '@/types/api';
import { cn } from '@/lib/utils';

type PhaseAccent = 'cyan' | 'violet' | 'emerald' | 'amber';

interface Phase {
  key: string;
  label: string;
  icon: React.ReactNode;
  accent: PhaseAccent;
  chips: { text: string; variant?: 'secondary' | 'outline' | 'success' | 'warning' }[];
  content: React.ReactNode;
}

const PHASE_ACCENT: Record<PhaseAccent, { node: string; label: string }> = {
  cyan: { node: 'border-cyan-400/40 bg-cyan-500/10 text-cyan-100', label: 'text-cyan-200' },
  violet: { node: 'border-violet-400/40 bg-violet-500/10 text-violet-100', label: 'text-violet-200' },
  emerald: { node: 'border-emerald-400/40 bg-emerald-500/10 text-emerald-100', label: 'text-emerald-200' },
  amber: { node: 'border-amber-400/40 bg-amber-500/10 text-amber-100', label: 'text-amber-200' },
};

export function AnalystResponseCard({
  response,
  foundationSecGovernance,
}: {
  response: AnalystResponseEnvelope;
  foundationSecGovernance?: FoundationSecGovernance | null;
}) {
  const playbookTitle = formatPlaybook(response.retrieved_playbook);
  const triageSteps = stringList(response.sop_guidance?.triage_steps);
  const validationNotes = stringList(response.sop_guidance?.validation_notes);
  const hasInvestigationTable = Boolean(response.splunk_results_table?.length);
  const hasSopSections = Boolean(response.escalation_criteria?.length || response.closure_conditions?.length);
  const title = stripSeverityPrefix(response.finding_title);
  const policyChecks = validationNotes.length ? validationNotes : triageSteps;
  const priorityActions = response.recommended_actions ?? [];
  const renderSections = response.render_sections ?? {};
  const splOnly = response.response_profile === 'spl_only';
  const isKnowledgeRecall = response.response_profile === 'knowledge_recall';
  const isHybridAlertReview = response.response_profile === 'hybrid_alert_review';
  const wasExecuted = response.execution_status === 'executed';
  const splReviewNotice =
    response.spl_code && !wasExecuted && !response.spl_status_detail
      ? response.execution_status_label ?? response.review_notice ?? 'Review only — not executed'
      : null;
  const summaryText = response.direct_answer_summary ?? response.one_sentence_finding;
  const showSummaryInHeader = Boolean(
    summaryText
      && (response.direct_answer_summary || isHybridAlertReview || !response.spl_code || response.draft_spl_code),
  );
  const missingEvidence = formatMissingEvidence(response);
  const investigationSteps = response.investigation_steps?.length
    ? response.investigation_steps
    : response.analyst_checklist ?? [];
  const investigationStepKeys = new Set(investigationSteps.map(normalizeSectionItem));
  const uniquePriorityActions = priorityActions.filter((action) => {
    const key = normalizeSectionItem(action);
    return key && !investigationStepKeys.has(key);
  });
  const hasPriorityInvestigation = hasPriorityActions(uniquePriorityActions);
  const showInvestigationSteps = Boolean(!isKnowledgeRecall && investigationSteps.length);
  const showRequiredEvidence = Boolean(!isKnowledgeRecall && response.required_evidence?.length);
  const showMissingEvidence = Boolean(!isKnowledgeRecall && missingEvidence.length);
  const showGuidanceLimitations = Boolean(
    !isKnowledgeRecall &&
      response.limitations?.length &&
      (renderSections.investigation_guidance ?? renderSections.limitations ?? true),
  );
  const showInvestigationGuidance =
    showInvestigationSteps || showRequiredEvidence || showMissingEvidence || showGuidanceLimitations;
  const showLimitations = Boolean(
    response.limitations?.length &&
      (renderSections.limitations ?? true) &&
      !showInvestigationGuidance &&
      !isKnowledgeRecall,
  );
  const severityShowsReviewRequired = /review required/i.test(response.severity_label ?? '');
  const showReviewRequiredBadge = Boolean(
    response.review_notice && !severityShowsReviewRequired && !response.spl_status_detail,
  );
  const draftSplCode = response.draft_spl_code?.trim() || null;
  const draftPreview = response.spl_draft_preview;
  const unresolvedSplBindings = formatDraftUnboundConstraints(
    response.spl_unbound_constraints?.length
      ? response.spl_unbound_constraints
      : (draftPreview?.unbound_constraints ?? []),
  );
  // Review-only SPL draft: the dedicated renderer owns the answer shape, so the
  // investigation-steps phase is the SOC review checklist (not a competing "Analyst
  // workflow" heading).
  const isReviewOnlySplDraft = splOnly && Boolean(draftSplCode);
  const isUniversalUtilitySplDraft =
    isReviewOnlySplDraft && !response.spl_status_detail && !response.spl_code;
  const llmSplCandidate = response.llm_spl_candidate;
  const showLlmSplCandidate = Boolean(llmSplCandidate);
  const showSpl = Boolean(response.spl_code && (renderSections.spl_artifact ?? true));
  // Lab draft preview is independent of governed spl_artifact visibility.
  const showDraftSpl = Boolean(draftSplCode);
  const showLiveResults =
    (renderSections.live_results ?? true) &&
    Boolean(response.splunk_status_line || hasInvestigationTable);
  const showFooterReviewNotice = Boolean(
    response.review_notice && !response.spl_code && !response.spl_status_detail && !showDraftSpl,
  );
  const showInvestigationPlan =
    !splOnly && !isKnowledgeRecall && uniquePriorityActions.length > 0 && (hasPriorityInvestigation || !response.spl_code);
  const showPolicyBridge = !isKnowledgeRecall && policyChecks.length > 0 && showInvestigationPlan && hasPriorityInvestigation;
  const governedAnalysis = splOnly ? null : foundationSecGovernance?.governed_analysis ?? null;
  const hasReasoning = !splOnly && Boolean(governedAnalysis || response.foundation_sec_analysis);
  const hasMitre =
    (renderSections.mitre_mapping ?? !splOnly) && Boolean(response.mitre_mappings?.length);
  const hasNotClaimed =
    (renderSections.not_claimed ?? !splOnly) && Boolean(response.not_claimed?.length);
  const showPlaybook =
    (renderSections.policy_citation ?? !splOnly) &&
    Boolean(playbookTitle || policyChecks.length);
  const playbookVersion =
    typeof response.retrieved_playbook?.version === 'string' ? (response.retrieved_playbook.version as string) : null;
  const tableRows = response.splunk_results_table?.length ?? 0;
  const initialAssessment = response.initial_assessment?.filter(Boolean) ?? [];

  // Phases are built from the fields that are actually present, so the same
  // timeline renders the full Experience Center fixture and the partial live
  // /chat answer (where MCP/LLM/RAG phases may be absent). Step numbers are
  // assigned by render order, never hardcoded.
  const phases: Phase[] = [];

  if (showInvestigationSteps) {
    phases.push({
      key: 'steps',
      label: isReviewOnlySplDraft ? 'SOC review checklist before execution' : 'Investigation steps',
      icon: <ListChecks className="h-3.5 w-3.5" />,
      accent: 'amber',
      chips: isReviewOnlySplDraft ? [] : [{ text: 'Analyst workflow', variant: 'outline' }],
      content: <StepList items={investigationSteps} />,
    });
  }

  if (showRequiredEvidence) {
    phases.push({
      key: 'required-evidence',
      label: 'Evidence required',
      icon: <Database className="h-3.5 w-3.5" />,
      accent: 'amber',
      chips: [{ text: `${response.required_evidence?.length ?? 0} item(s)`, variant: 'outline' }],
      content: <BulletList items={response.required_evidence ?? []} />,
    });
  }

  if (showMissingEvidence) {
    phases.push({
      key: 'missing-evidence',
      label: 'Missing evidence',
      icon: <FileSearch className="h-3.5 w-3.5" />,
      accent: 'amber',
      chips: [{ text: `${missingEvidence.length} gap(s)`, variant: 'outline' }],
      content: <BulletList items={missingEvidence} />,
    });
  }

  if (showGuidanceLimitations) {
    phases.push({
      key: 'limitations',
      label: 'Limitations',
      icon: <ShieldAlert className="h-3.5 w-3.5" />,
      accent: 'amber',
      chips: [{ text: 'Governed caveats', variant: 'outline' }],
      content: <BulletList items={response.limitations ?? []} />,
    });
  }

  if (showPlaybook) {
    phases.push({
      key: 'knowledge',
      label: 'SOC knowledge',
      icon: <BookOpen className="h-3.5 w-3.5" />,
      accent: 'emerald',
      chips: [
        { text: 'Governed RAG', variant: 'secondary' },
        ...(playbookVersion ? [{ text: playbookVersion, variant: 'outline' as const }] : []),
      ],
      content: (
        <>
          {playbookTitle ? (
            <>
              <p className="font-medium text-cyan-100">{playbookTitle}</p>
              <PlaybookProvenance playbook={response.retrieved_playbook} />
              {typeof response.retrieved_playbook?.purpose === 'string' ? (
                <div className="mt-3">
                  <SectionTitle>Purpose</SectionTitle>
                  <p className="mt-1 leading-6 text-slate-200">{response.retrieved_playbook.purpose}</p>
                </div>
              ) : null}
            </>
          ) : null}
          {policyChecks.length ? (
            <div className={playbookTitle ? 'mt-3' : ''}>
              <SectionTitle>Policy checks required by SOP</SectionTitle>
              <StepList items={policyChecks} />
            </div>
          ) : null}
        </>
      ),
    });
  }

  if (hasMitre || hasNotClaimed) {
    phases.push({
      key: 'mitre',
      label: 'MITRE status',
      icon: <Crosshair className="h-3.5 w-3.5" />,
      accent: 'violet',
      chips: [{ text: 'local MITRE KB', variant: 'outline' }],
      content: (
        <>
          {hasMitre ? <DataTable rows={response.mitre_mappings ?? []} /> : null}
          {hasNotClaimed ? (
            <div className={hasMitre ? 'mt-4' : ''}>
              <SectionTitle>Not claimed</SectionTitle>
              <DataTable rows={response.not_claimed ?? []} />
            </div>
          ) : null}
        </>
      ),
    });
  }

  if (showSpl || showDraftSpl || response.spl_status_detail) {
    phases.push({
      key: 'spl',
      label: wasExecuted ? 'Executed detection' : isUniversalUtilitySplDraft ? 'Universal SPL draft' : showDraftSpl && !showSpl ? 'Draft SPL preview' : 'SPL status',
      icon: <Terminal className="h-3.5 w-3.5" />,
      accent: showDraftSpl && !showSpl ? 'amber' : 'cyan',
      chips: isUniversalUtilitySplDraft
        ? [{ text: 'Template-free', variant: 'outline' as const }, { text: 'Review only', variant: 'warning' as const }]
        : showDraftSpl && !showSpl
        ? [
            { text: 'Lab only', variant: 'warning' as const },
            { text: 'Not catalog-approved', variant: 'outline' as const },
          ]
        : [{ text: splStatusChip(response), variant: 'secondary' }],
      content: (
        <>
          {response.spl_status_detail ? <SplStatusDetail detail={response.spl_status_detail} /> : null}
          {unresolvedSplBindings.length && (showSpl || showDraftSpl) ? (
            <div className={response.spl_status_detail ? 'mt-3' : ''}>
              <SectionTitle>Unresolved source bindings</SectionTitle>
              <BulletList items={unresolvedSplBindings} />
            </div>
          ) : null}
          {showDraftSpl ? (
            <>
              {!isUniversalUtilitySplDraft ? (
              <p
                className={cn(
                  'text-sm leading-6 text-amber-100/95',
                  response.spl_status_detail ? 'mt-3' : '',
                )}
              >
                {draftPreview?.not_catalog_approved_notice ?? 'Not catalog-approved / review required.'}{' '}
                {response.review_notice ?? draftPreview?.warning}
              </p>
              ) : null}
              {draftPreview?.assumptions?.length ? (
                <div className="mt-3">
                  <SectionTitle>Assumptions and placeholders</SectionTitle>
                  <BulletList items={draftPreview.assumptions} />
                </div>
              ) : null}
              <pre
                className={cn(
                  'max-h-96 overflow-auto rounded-lg border border-amber-400/25 bg-slate-950 p-3 text-xs leading-6 text-amber-100',
                  'mt-3',
                )}
              >
                <code className="whitespace-pre-wrap break-words">{formatSplForDisplay(draftSplCode ?? '')}</code>
              </pre>
            </>
          ) : null}
          {showSpl ? (
            <>
              {!wasExecuted && splReviewNotice ? (
                <p className={response.spl_status_detail ? 'mt-3 text-sm leading-6 text-amber-100/95' : 'text-sm leading-6 text-amber-100/95'}>
                  {splReviewNotice}
                </p>
              ) : null}
              <pre
                className={cn(
                  'max-h-96 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs leading-6 text-cyan-100',
                  splReviewNotice || response.spl_status_detail || showDraftSpl ? 'mt-3' : '',
                )}
              >
                <code className="whitespace-pre-wrap break-words">{formatSplForDisplay(response.spl_code ?? '')}</code>
              </pre>
            </>
          ) : null}
          {wasExecuted && response.executed_spl && response.executed_spl !== response.spl_code ? (
            <div className="mt-3">
              <SectionTitle>Executed normalized SPL</SectionTitle>
              <pre className="mt-2 max-h-96 overflow-auto rounded-lg border border-emerald-400/20 bg-slate-950 p-3 text-xs leading-6 text-emerald-100">
                <code className="whitespace-pre-wrap break-words">{formatSplForDisplay(response.executed_spl)}</code>
              </pre>
            </div>
          ) : null}
          {response.key_fields?.length ? (
            <div className="mt-3">
              <SectionTitle>Key returned fields</SectionTitle>
              <BulletList items={response.key_fields} />
            </div>
          ) : null}
        </>
      ),
    });
  }

  if (showLlmSplCandidate && llmSplCandidate) {
    phases.push({
      key: 'llm-spl-candidate',
      label: 'LLM SPL Candidate',
      icon: <Terminal className="h-3.5 w-3.5" />,
      accent: 'amber',
      chips: [
        { text: 'Lab only', variant: 'warning' },
        { text: llmSplCandidate.llm_spl_candidate_status, variant: 'outline' },
        { text: `confidence ${formatConfidence(llmSplCandidate.llm_spl_confidence_score)}`, variant: 'outline' },
      ],
      content: <LlmSplCandidatePanel candidate={llmSplCandidate} />,
    });
  }

  if (showLiveResults) {
    phases.push({
      key: 'evidence',
      label: 'Evidence retrieved',
      icon: <Database className="h-3.5 w-3.5" />,
      accent: 'cyan',
      chips: [
        { text: response.splunk_status_line?.toLowerCase().includes('fixture') ? 'Splunk MCP fixture' : 'Splunk MCP', variant: 'secondary' },
        ...(tableRows ? [{ text: `${tableRows} row${tableRows === 1 ? '' : 's'}`, variant: 'outline' as const }] : []),
      ],
      content: (
        <>
          {response.splunk_status_line ? (
            <p className="font-mono text-xs text-cyan-100">{response.splunk_status_line}</p>
          ) : null}
          {hasInvestigationTable ? <DataTable rows={response.splunk_results_table ?? []} /> : null}
          {response.evidence_summary ? (
            <p className="mt-3 rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-2 text-xs leading-5 text-slate-300">
              {response.evidence_summary}
            </p>
          ) : null}
        </>
      ),
    });
  }

  if (hasReasoning) {
    phases.push({
      key: 'reasoning',
      label: 'Model reasoning',
      icon: <Cpu className="h-3.5 w-3.5" />,
      accent: 'violet',
      chips: [
        { text: 'Foundation-sec', variant: 'secondary' },
        { text: 'governed', variant: 'outline' },
      ],
      content: (
        <>
          {governedAnalysis ? (
            <FoundationSecReasoning governance={foundationSecGovernance!} />
          ) : response.foundation_sec_analysis ? (
            <div className="space-y-3 leading-6 text-slate-200">
              {splitParagraphs(response.foundation_sec_analysis).map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>
          ) : null}
        </>
      ),
    });
  }

  if (showInvestigationPlan || response.escalation_criteria?.length || response.closure_conditions?.length) {
    phases.push({
      key: 'plan',
      label: hasPriorityInvestigation ? 'Investigation plan' : 'What to look for',
      icon: <ListChecks className="h-3.5 w-3.5" />,
      accent: 'amber',
      chips: [{ text: 'V.AI SOC governed', variant: 'outline' }],
      content: (
        <>
          {showPolicyBridge ? (
            <p className="mb-3 text-sm leading-6 text-slate-300">
              Complete the policy checks above, then execute the prioritized investigation steps below.
            </p>
          ) : null}
          {showInvestigationPlan ? (
            hasPriorityInvestigation ? (
              <RecommendationList items={uniquePriorityActions} />
            ) : (
              <BulletList items={uniquePriorityActions} />
            )
          ) : null}
          {response.escalation_criteria?.length ? (
            <div className="mt-4">
              <SectionTitle>Escalation criteria</SectionTitle>
              <BulletList items={response.escalation_criteria} />
            </div>
          ) : null}
          {response.closure_conditions?.length ? (
            <div className="mt-4">
              <SectionTitle>Closure conditions</SectionTitle>
              <BulletList items={response.closure_conditions} />
            </div>
          ) : null}
        </>
      ),
    });
  }

  return (
    <div className="w-full min-w-0 max-w-full rounded-xl border border-cyan-500/20 bg-slate-950/70 px-4 py-5 text-[15px] text-slate-100 shadow-sm sm:px-6 xl:max-w-[1120px]">
      <div className="flex flex-wrap items-center gap-2">
        {response.severity_label && !isKnowledgeRecall && !isReviewOnlySplDraft ? (
          <SeverityBadge label={response.severity_label} />
        ) : null}
        {response.severity_confidence ? (
          <Badge variant="outline">Confidence: {response.severity_confidence}</Badge>
        ) : null}
        {showReviewRequiredBadge ? <Badge variant="warning">Review required</Badge> : null}
      </div>

      {title ? <h3 className="mt-3 text-xl font-semibold text-slate-50">{title}</h3> : null}

      {response.severity_rationale ? (
        <p className="mt-2 text-sm leading-6 text-slate-300">{response.severity_rationale}</p>
      ) : null}

      {response.severity_safety_note ? (
        <p className="mt-2 text-sm leading-6 text-slate-200">{response.severity_safety_note}</p>
      ) : null}

      {initialAssessment.length ? (
        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2">
          <SectionTitle>Initial assessment</SectionTitle>
          <BulletList items={initialAssessment} />
        </div>
      ) : showSummaryInHeader && summaryText ? (
        <div className="mt-2 space-y-2">
          {(isReviewOnlySplDraft ? summaryText.split('\n') : splitParagraphs(summaryText))
            .map((paragraph) => paragraph.trim())
            .filter(Boolean)
            .map((paragraph) => (
            <p key={paragraph} className="leading-6 text-slate-200">
              {paragraph}
            </p>
          ))}
        </div>
      ) : null}

      {showLimitations ? (
        <div className="mt-3 rounded-lg border border-slate-700/80 bg-slate-900/60 px-3 py-2">
          <SectionTitle>Limitations</SectionTitle>
          <BulletList items={response.limitations ?? []} />
        </div>
      ) : null}

      {phases.length ? <PhaseTimeline phases={phases} /> : null}

      {showFooterReviewNotice ? (
        <p className="mt-5 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
          {response.review_notice}
        </p>
      ) : null}
    </div>
  );
}

function PhaseTimeline({ phases }: { phases: Phase[] }) {
  return (
    <ol className="mt-5">
      {phases.map((phase, index) => {
        const accent = PHASE_ACCENT[phase.accent];
        const isLast = index === phases.length - 1;
        return (
          <li key={phase.key} className="relative pb-7 pl-14 last:pb-0">
            {!isLast ? (
              <span
                aria-hidden
                className="absolute bottom-1 left-[19px] top-11 w-px bg-gradient-to-b from-slate-600/70 to-slate-800/40"
              />
            ) : null}
            <span
              className={cn(
                'absolute left-0 top-0 flex h-10 w-10 items-center justify-center rounded-full border text-base',
                accent.node,
              )}
            >
              {phase.icon}
            </span>
            <div className="flex min-h-[2.5rem] flex-wrap items-center gap-2 pt-1.5">
              <span
                className={cn(
                  'flex items-center gap-1.5 text-[0.72rem] font-semibold uppercase tracking-[0.08em]',
                  accent.label,
                )}
              >
                {phase.icon}
                {phase.label}
              </span>
              {phase.chips.map((chip) => (
                <Badge key={chip.text} variant={chip.variant ?? 'outline'}>
                  {chip.text}
                </Badge>
              ))}
            </div>
            <div className="mt-2.5">{phase.content}</div>
          </li>
        );
      })}
    </ol>
  );
}

function FoundationSecReasoning({ governance }: { governance: FoundationSecGovernance }) {
  const analysis = governance.governed_analysis;
  if (!analysis) return null;
  const captured = governance.captured_outputs ?? [];
  const overrides = analysis.governance_overrides ?? [];
  const evidenceUsed = analysis.evidence_used ?? [];
  const missingEvidence = analysis.missing_evidence ?? [];
  const notes = analysis.guardrail_notes ?? [];

  return (
    <div>
      <div className="grid gap-3 lg:grid-cols-2">
        {analysis.model_signal ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
            <p className="text-[0.68rem] font-medium uppercase tracking-[0.05em] text-slate-400">Advisory model signal</p>
            <p className="mt-1 leading-6 text-slate-100">{analysis.model_signal}</p>
          </div>
        ) : null}
        {analysis.vai_soc_decision ? (
          <div className="rounded-md border border-cyan-400/25 bg-cyan-400/[0.05] p-3">
            <p className="text-[0.68rem] font-medium uppercase tracking-[0.05em] text-cyan-300/80">V.AI SOC decision</p>
            <p className="mt-1 leading-6 text-slate-100">{analysis.vai_soc_decision}</p>
          </div>
        ) : null}
      </div>

      {evidenceUsed.length ? (
        <div className="mt-3">
          <SectionTitle>Evidence used</SectionTitle>
          <BulletList items={evidenceUsed} />
        </div>
      ) : null}

      {missingEvidence.length ? (
        <div className="mt-3">
          <SectionTitle>Evidence still required</SectionTitle>
          <BulletList items={missingEvidence} />
        </div>
      ) : null}

      {notes.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {notes.map((note) => (
            <Badge key={note} variant="outline">
              {note}
            </Badge>
          ))}
        </div>
      ) : null}

      {overrides.length || captured.length ? (
        <details className="group mt-4 rounded-md border border-slate-800 bg-slate-950/60">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-300 transition hover:text-cyan-200">
            <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
            Model output governance
            <Badge variant="outline">collapsed</Badge>
          </summary>
          <div className="space-y-3 border-t border-slate-800 p-3">
            {captured.length ? (
              <div>
                <SectionTitle>Captured contribution</SectionTitle>
                <div className="mt-2 space-y-2">
                  {captured.map((item) => (
                    <div key={`${item.model_role}-${item.captured_prompt_type}`} className="rounded border border-slate-800 bg-slate-950/50 p-2">
                      <div className="flex flex-wrap gap-1.5">
                        {item.model_role ? <Badge variant="secondary">{item.model_role}</Badge> : null}
                        {item.model_name ? <Badge variant="outline">{item.model_name}</Badge> : null}
                      </div>
                      {item.captured_summary ? <p className="mt-2 leading-6 text-slate-200">{item.captured_summary}</p> : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {overrides.length ? (
              <div>
                <SectionTitle>Governance applied</SectionTitle>
                <div className="mt-2 space-y-2">
                  {overrides.map((override) => (
                    <div key={`${override.rule}-${override.model_suggested}`} className="rounded border border-slate-800 bg-slate-950/50 p-2">
                      {override.model_suggested ? <p className="text-slate-400">Model suggested: <span className="text-slate-100">{override.model_suggested}</span></p> : null}
                      {override.vai_soc_governed ? <p className="mt-1 text-slate-400">V.AI SOC governed: <span className="text-cyan-100">{override.vai_soc_governed}</span></p> : null}
                      {override.reason ? <p className="mt-1 text-slate-300">{override.reason}</p> : null}
                      {override.rule ? <Badge className="mt-2" variant="outline">{override.rule}</Badge> : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
}

function LlmSplCandidatePanel({
  candidate,
}: {
  candidate: NonNullable<AnalystResponseEnvelope['llm_spl_candidate']>;
}) {
  const spl = candidate.llm_spl_candidate?.trim();
  const qualityFindings = (candidate.quality_findings ?? []).map(formatFinding);
  const validationFindings = candidate.validation_findings ?? [];
  const questions = candidate.clarifying_questions ?? [];
  return (
    <div className="rounded-lg border border-amber-400/25 bg-amber-500/10 px-3 py-3">
      <p className="text-sm font-medium text-amber-100">LLM SPL Candidate — lab only</p>
      <p className="mt-1 text-xs leading-5 text-amber-100/90">
        Not governed · Not approved · Not executed · SOC review required
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge variant="outline">status: {candidate.llm_spl_candidate_status}</Badge>
        <Badge variant="outline">quality: {candidate.quality_status ?? 'not run'}</Badge>
        <Badge variant="outline">validator: {candidate.validator_status ?? 'not run'}</Badge>
        <Badge variant="outline">confidence: {formatConfidence(candidate.llm_spl_confidence_score)} {candidate.llm_spl_confidence_label}</Badge>
      </div>
      {candidate.detection_family ? (
        <p className="mt-3 text-sm text-slate-200">
          <span className="text-slate-400">Detection family:</span> {candidate.detection_family}
        </p>
      ) : null}
      {questions.length ? (
        <div className="mt-3">
          <SectionTitle>Clarification questions</SectionTitle>
          <BulletList items={questions} />
        </div>
      ) : null}
      {candidate.missing_details?.length ? (
        <div className="mt-3">
          <SectionTitle>Missing details</SectionTitle>
          <BulletList items={candidate.missing_details} />
        </div>
      ) : null}
      {spl && candidate.llm_spl_candidate_status === 'candidate_generated' ? (
        <pre className="mt-3 max-h-96 overflow-auto rounded-lg border border-amber-400/25 bg-slate-950 p-3 text-xs leading-6 text-amber-100">
          <code className="whitespace-pre-wrap break-words">{formatSplForDisplay(spl)}</code>
        </pre>
      ) : null}
      {candidate.assumptions?.length ? (
        <div className="mt-3">
          <SectionTitle>Assumptions</SectionTitle>
          <BulletList items={candidate.assumptions} />
        </div>
      ) : null}
      {candidate.required_fields?.length ? (
        <div className="mt-3">
          <SectionTitle>Required fields</SectionTitle>
          <BulletList items={candidate.required_fields} />
        </div>
      ) : null}
      {qualityFindings.length ? (
        <div className="mt-3">
          <SectionTitle>Quality findings</SectionTitle>
          <BulletList items={qualityFindings} />
        </div>
      ) : null}
      {validationFindings.length ? (
        <div className="mt-3">
          <SectionTitle>Validator findings</SectionTitle>
          <BulletList items={validationFindings} />
        </div>
      ) : null}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h4 className="text-xs font-medium uppercase tracking-[0.05em] text-slate-400">{children}</h4>;
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return null;
  const columns = Object.keys(rows[0]);
  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-slate-800">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-800 text-left text-[13px]">
          <thead className="bg-slate-900/80 text-slate-400">
            <tr>
              {columns.map((column) => (
                <th key={column} className={cn('whitespace-nowrap px-3 py-2 font-medium', isNumericColumn(column) && 'text-right')}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-950/70">
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column} className={cn('whitespace-nowrap px-3 py-2 text-slate-100', isNumericValue(row[column]) && 'text-right font-medium')}>{String(row[column] ?? '')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="mt-2 space-y-1.5 text-slate-200">
      {items.map((item) => <li key={item}>- {item}</li>)}
    </ul>
  );
}

function RecommendationList({ items }: { items: string[] }) {
  return (
    <div className="mt-3 space-y-2">
      {items.map((item) => {
        const normalized = normalizePriorityAction(item);
        return (
          <div
            key={item}
            className={cn('rounded-lg border py-3 pl-4 pr-3 leading-6', recommendationTone(normalized.priority))}
          >
            <span className="mr-2 text-xs font-bold uppercase tracking-[0.05em]">{normalized.priority}</span>
            <span className="text-slate-100">{normalized.text}</span>
          </div>
        );
      })}
    </div>
  );
}

function SeverityBadge({ label }: { label: string }) {
  const className = label.startsWith('P1')
    ? 'border-red-400/40 bg-red-500/15 text-red-100'
    : label.startsWith('P2')
      ? 'border-amber-400/40 bg-amber-500/15 text-amber-100'
      : label.startsWith('P3')
        ? 'border-blue-400/40 bg-blue-500/15 text-blue-100'
        : 'border-slate-500/40 bg-slate-500/15 text-slate-200';
  return <span className={cn('inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold', className)}>{label}</span>;
}

function recommendationTone(priority: string) {
  if (priority === 'P1') return 'border-l-4 border-red-400/70 bg-red-500/10 text-red-100';
  if (priority === 'P2') return 'border-l-4 border-amber-400/70 bg-amber-500/10 text-amber-100';
  if (priority === 'P4') return 'border-l-4 border-slate-500/70 bg-slate-500/10 text-slate-200';
  return 'border-l-4 border-blue-400/70 bg-blue-500/10 text-blue-100';
}

function formatSplForDisplay(spl: string): string {
  const trimmed = spl.trim();
  if (trimmed.includes('\n')) {
    return trimmed;
  }
  const parts = spl.split('|').map((part) => part.trim()).filter(Boolean);
  if (parts.length <= 1) {
    return trimmed;
  }
  return parts.map((part, index) => (index === 0 ? part : `| ${part}`)).join('\n');
}

function splitParagraphs(value: string) {
  return value.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
}

function stripSeverityPrefix(value?: string | null) {
  return value?.replace(/^P[1-4]\s+(Critical|High|Medium|Low)\s*[-—]\s*/i, '') ?? null;
}

function isNumericColumn(column: string) {
  return /count|logins|users|failures|success|total/i.test(column);
}

function isNumericValue(value: unknown) {
  return typeof value === 'number';
}

function hasPriorityActions(items: string[]) {
  return items.some((item) => /^P[1-4]\s*[—-]\s*/.test(item));
}

function normalizeSectionItem(item: string) {
  return item
    .replace(/^P[1-4]\s*[—\-–:]\s*/i, '')
    .replace(/^Step\s+\d+\s*:\s*/i, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function StepList({ items }: { items: string[] }) {
  return (
    <ul className="mt-2 space-y-1.5 text-slate-200">
      {items.map((item, index) => (
        <li key={`${index}-${item}`}>
          <span className="font-medium text-slate-300">Step {index + 1}:</span> {humanizeStep(item)}
        </li>
      ))}
    </ul>
  );
}

function SplStatusDetail({
  detail,
}: {
  detail: NonNullable<AnalystResponseEnvelope['spl_status_detail']>;
}) {
  const generationStatus = detail.generation_status ?? detail.generation;
  const generationLabel =
    generationStatus === 'blocked'
      ? 'blocked / review required'
      : generationStatus === 'review_required'
        ? 'review required'
        : generationStatus === 'generated'
          ? 'generated / review required'
          : generationStatus ?? 'unknown';
  return (
    <div className="rounded-lg border border-amber-400/25 bg-amber-500/10 px-3 py-2 text-sm leading-6 text-amber-50">
      <ul className="space-y-1 text-slate-100">
        <li>
          <span className="text-slate-400">SPL template status:</span> {detail.template_status ?? 'unknown'}
        </li>
        <li>
          <span className="text-slate-400">SPL generation:</span> {generationLabel}
        </li>
        {detail.reason_display || detail.reason ? (
          <li>
            <span className="text-slate-400">Reason:</span> {detail.reason_display ?? detail.reason}
          </li>
        ) : null}
        {detail.message ? (
          <li>
            <span className="text-slate-400">Grounding:</span> {detail.message}
          </li>
        ) : null}
        {detail.environment_fields_used?.length ? (
          <li>
            <span className="text-slate-400">Environment fields used:</span> {detail.environment_fields_used.join(', ')}
          </li>
        ) : null}
        {detail.query_complexity ? (
          <li>
            <span className="text-slate-400">Query complexity:</span> {detail.query_complexity}
          </li>
        ) : null}
        {detail.required_fields?.length ? (
          <li>
            <span className="text-slate-400">Required fields:</span> {detail.required_fields.join(', ')}
          </li>
        ) : null}
      </ul>
    </div>
  );
}

function splStatusChip(response: AnalystResponseEnvelope): string {
  const detail = response.spl_status_detail;
  if (response.spl_status === 'not_required') {
    return 'SPL skipped';
  }
  if (
    detail?.template_status === 'active' &&
    detail.generation_status === 'blocked' &&
    detail.block_reason === 'spl_template_active_source_profile_missing'
  ) {
    return 'SPL blocked — source profile missing';
  }
  if (!response.spl_code && detail?.generation_status === 'blocked') {
    return 'SPL blocked';
  }
  return 'Candidate SPL';
}

function formatMissingEvidence(response: AnalystResponseEnvelope): string[] {
  const raw = response.missing_evidence ?? [];
  const limitationLabels = new Set(response.limitations ?? []);
  return raw.map((item) => {
    const normalized = item.replace(/_/g, ' ');
    if (/missing/i.test(item)) {
      return item;
    }
    const candidate = `${normalized} missing`;
    if (limitationLabels.has(candidate)) {
      return candidate;
    }
    return candidate;
  });
}

function humanizeStep(value: string): string {
  return value.replace(/_/g, ' ');
}

function formatDraftUnboundConstraints(value?: Array<Record<string, unknown>>): string[] {
  if (!Array.isArray(value)) return [];
  const labels = value.map((item) => {
    const slot = String(item.slot ?? 'binding').replace(/_/g, ' ');
    const reason = String(item.reason ?? 'unresolved').replace(/_/g, ' ');
    const source = typeof item.source === 'string'
      ? item.source
      : typeof item.dropped_source === 'string'
        ? item.dropped_source
        : null;
    const valueLabel = item.value ?? item.dropped_value;
    const valueText = valueLabel == null || valueLabel === '' ? '' : ` (${String(valueLabel)})`;
    const sourceText = source ? ` from ${source.replace(/_/g, ' ')}` : '';
    return `${slot}${valueText}: ${reason}${sourceText}`;
  });
  return Array.from(new Set(labels));
}

function normalizePriorityAction(item: string): { priority: string; text: string } {
  let cleaned = item.trim();
  const glued = cleaned.match(/^(P[1-4])([A-Za-z])/);
  if (glued) {
    cleaned = `${glued[1]} — ${cleaned.slice(glued[1].length).replace(/^[\s-—]+/, '')}`;
  }
  const matched = cleaned.match(/^(P[1-4])\s*[:—-]\s*(.*)$/);
  if (matched) {
    return { priority: matched[1], text: humanizeStep(matched[2]) };
  }
  return { priority: 'P3', text: humanizeStep(cleaned) };
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function formatConfidence(value?: number | null): string {
  return typeof value === 'number' ? value.toFixed(2) : '0.00';
}

function formatFinding(value: Record<string, unknown>): string {
  const rule = typeof value.rule_id === 'string' ? value.rule_id : 'quality';
  const severity = typeof value.severity === 'string' ? value.severity : 'finding';
  const message = typeof value.message === 'string' ? value.message : '';
  return [rule, severity, message].filter(Boolean).join(': ');
}

function formatPlaybook(playbook?: Record<string, unknown> | null): string | null {
  if (!playbook) return null;
  const title = typeof playbook.title === 'string' ? playbook.title : null;
  const id = typeof playbook.id === 'string' ? playbook.id : null;
  const version = typeof playbook.version === 'string' ? playbook.version : null;
  return [title, id, version].filter(Boolean).join(' - ') || null;
}

function PlaybookProvenance({ playbook }: { playbook?: Record<string, unknown> | null }) {
  if (!playbook) return null;
  const citation = typeof playbook.citation === 'string' ? playbook.citation : null;
  const retrievalMode = typeof playbook.retrieval_mode === 'string' ? playbook.retrieval_mode : null;
  const confidence = playbook.confidence;
  const evidenceId = typeof playbook.source_evidence_id === 'string' ? playbook.source_evidence_id : null;
  if (!citation && !retrievalMode && confidence == null && !evidenceId) return null;

  const parts: string[] = [];
  if (citation) parts.push(`Citation: ${citation}`);
  if (retrievalMode) parts.push(`Retrieval: ${retrievalMode}`);
  if (typeof confidence === 'number') parts.push(`Confidence: ${confidence.toFixed(2)}`);
  if (evidenceId) parts.push(`Evidence ref: ${evidenceId}`);

  return <p className="mt-2 font-mono text-[0.7rem] leading-5 text-slate-400">{parts.join(' · ')}</p>;
}
