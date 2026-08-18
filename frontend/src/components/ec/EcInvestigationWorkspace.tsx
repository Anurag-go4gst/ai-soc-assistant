import { useEffect, useRef, useState } from 'react';
import { Activity, Bot, Maximize2, Minimize2, Sparkles } from 'lucide-react';
import { followUpEcScenario, runEcScenario } from '@/api/ecClient';
import { EcActionFlow } from '@/components/ec/EcActionFlow';
import { EcChatBubble } from '@/components/ec/EcChatBubble';
import { EcCockpitComposer } from '@/components/ec/EcCockpitComposer';
import { EcCoordinationPanels } from '@/components/ec/EcCoordinationPanels';
import { EcFollowUpBar } from '@/components/ec/EcFollowUpBar';
import { EcInvestigationAnswer } from '@/components/ec/EcInvestigationAnswer';
import { EcActionReadinessPanel } from '@/components/ec/EcInvestigationQuality';
import { EcTransparencyDrawer } from '@/components/ec/EcTransparencyDrawer';
import { playEcExecutionJourney, resolveJourney } from '@/components/ec/ecExecutionJourneyPlayer';
import type { EcActionRecord, EcFollowUpChip, EcScenarioSummary, ExperienceCenterResponse } from '@/components/ec/types';
import { ExperienceExecutionProgressPanel } from '@/components/experience-center/ExperienceExecutionProgressPanel';
import { experienceExecutionIsWaiting, type ExperienceExecutionProgressView } from '@/lib/experienceCenterExecution';
import { scrollIntoScrollParent } from '@/lib/scrollIntoScrollParent';
import { evidenceIdForChip, readinessLabelForActionChip } from '@/lib/ecOperationalLink';
import { EcWelcomeHero } from '@/components/ec/EcWelcomeHero';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

interface EcStreamMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isActionChip(chip?: EcFollowUpChip | null): boolean {
  if (!chip) return false;
  return chip.group === 'action' || Boolean(chip.leads_to_action);
}

function isS4AgentExecutiveSummaryFollowUp(scenarioId: string | undefined, followUpId: string): boolean {
  return scenarioId === 's4_zero_day_no_playbook' && followUpId === 'generate_executive_summary';
}

function isS4AgentInlineProgress(scenarioId: string | undefined, followUpId: string, keepAnswer: boolean): boolean {
  return (
    scenarioId === 's4_zero_day_no_playbook' &&
    keepAnswer &&
    ['run_investigation', 'approve_investigation_vuln_scan', 'skip_investigation_vuln_scan', 'create_remediation_plan', 'run_remediation'].includes(
      followUpId,
    )
  );
}

function scrollAgentSection(selector: string, block: ScrollLogicalPosition = 'start') {
  window.requestAnimationFrame(() => {
    const panel = document.querySelector(selector);
    scrollIntoScrollParent(panel instanceof HTMLElement ? panel : null, { block, behavior: 'smooth' });
  });
}

function isEvidenceContinueChip(chip?: EcFollowUpChip | null): boolean {
  if (!chip || isActionChip(chip)) return false;
  const id = chip.follow_up_id;
  return id.startsWith('show_') || id.startsWith('check_');
}

export function EcInvestigationWorkspace() {
  const [selectedId, setSelectedId] = useState('');
  const [envelope, setEnvelope] = useState<ExperienceCenterResponse | null>(null);
  const [progress, setProgress] = useState<ExperienceExecutionProgressView | null>(null);
  const [actionProgress, setActionProgress] = useState<ExperienceExecutionProgressView | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [answerRevealKey, setAnswerRevealKey] = useState(0);
  const [operationalLink, setOperationalLink] = useState<string | null>(null);
  const [highlightEvidenceId, setHighlightEvidenceId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stream, setStream] = useState<EcStreamMessage[]>([]);
  const [answerMaximized, setAnswerMaximized] = useState(false);
  const epochRef = useRef(0);
  const skipRef = useRef(false);
  const actionJourneyRef = useRef<HTMLDivElement | null>(null);
  const operationalChainRef = useRef<HTMLDivElement | null>(null);
  const answerAnchorRef = useRef<HTMLDivElement | null>(null);
  const progressAnchorRef = useRef<HTMLDivElement | null>(null);
  const streamEndRef = useRef<HTMLDivElement | null>(null);

  const focusEvidence = (evidenceId: string) => {
    setHighlightEvidenceId(evidenceId);
    window.requestAnimationFrame(() => {
      const row = document.querySelector(`[data-evidence-id="${evidenceId}"]`);
      scrollIntoScrollParent(row instanceof HTMLElement ? row : null, { block: 'nearest', behavior: 'smooth' });
    });
  };

  const scrollToAnswerStart = () => {
    window.requestAnimationFrame(() => {
      scrollIntoScrollParent(answerAnchorRef.current, { block: 'start', behavior: 'smooth' });
    });
  };

  useEffect(() => {
    if (!progress) return;
    if (envelope?.scenario_id === 's4_zero_day_no_playbook' && envelope.ec_agent_workflow) return;
    window.requestAnimationFrame(() => {
      scrollIntoScrollParent(progressAnchorRef.current, { block: 'start', behavior: 'smooth' });
    });
  }, [progress?.activeStepIndex, progress?.completedStepIds?.length, progress?.header, envelope?.scenario_id, envelope?.ec_agent_workflow]);

  useEffect(() => {
    if (!actionProgress) return;
    window.requestAnimationFrame(() => {
      scrollIntoScrollParent(operationalChainRef.current ?? actionJourneyRef.current, {
        block: 'nearest',
        behavior: 'smooth',
      });
    });
  }, [actionProgress?.activeStepIndex, actionProgress?.completedStepIds?.length, actionProgress?.header]);

  const scrollToEnd = () => {
    window.requestAnimationFrame(() => {
      const el = streamEndRef.current;
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
    });
  };

  const pushUserMessage = (text: string, options?: { scrollMode?: 'end' | 'answer' | 'none' }) => {
    setStream((current) => [...current, { id: `user-${Date.now()}`, role: 'user', text }]);
    const mode = options?.scrollMode ?? 'end';
    if (mode === 'end') scrollToEnd();
    else if (mode === 'answer') scrollToAnswerStart();
  };

  const playThenReveal = async (
    next: ExperienceCenterResponse,
    epoch: number,
    options?: { keepAnswer?: boolean; agentInlineProgress?: boolean },
  ) => {
    if (options?.agentInlineProgress) {
      skipRef.current = false;
      let last: ExperienceExecutionProgressView | null = null;
      const ok = await playEcExecutionJourney(resolveJourney(next.ec_execution_journey), (view) => {
        last = view;
        setProgress(view);
      }, {
        isStale: () => epoch !== epochRef.current,
        skipRemaining: () => skipRef.current,
      });
      if (!ok || epoch !== epochRef.current) return;
      setProgress(null);
      setEnvelope(next);
      setRevealed(true);
      if (next.ec_agent_lifecycle === 'INVESTIGATION_COMPLETE') {
        scrollAgentSection('[data-ec-section="investigation-summary"]', 'start');
      } else if (next.ec_agent_lifecycle === 'REMEDIATION_PLAN_READY') {
        scrollAgentSection('[data-ec-section="remediation-summary"]', 'start');
      } else if (next.ec_agent_lifecycle === 'INVESTIGATION_NEEDS_APPROVAL') {
        scrollAgentSection('[data-ec-section="agent-hil"]');
      } else {
        scrollToAnswerStart();
      }
      return;
    }

    skipRef.current = false;
    let last: ExperienceExecutionProgressView | null = null;
    const setView = options?.keepAnswer ? setActionProgress : setProgress;
    const ok = await playEcExecutionJourney(resolveJourney(next.ec_execution_journey), (view) => {
      last = view;
      setView(view);
    }, {
      isStale: () => epoch !== epochRef.current,
      skipRemaining: () => skipRef.current,
    });
    if (!ok || epoch !== epochRef.current) return;

    const waiting = experienceExecutionIsWaiting(last);
    setEnvelope(next);

    if (waiting) {
      setSynthesizing(false);
      setRevealed(true);
      if (!options?.keepAnswer) {
        setAnswerRevealKey((key) => key + 1);
      }
    } else if (options?.keepAnswer) {
      setView(null);
      setRevealed(true);
    } else {
      setView(null);
      setSynthesizing(true);
      setRevealed(false);
      await delay(400);
      if (epoch !== epochRef.current) return;
      setSynthesizing(false);
      setRevealed(true);
      setAnswerRevealKey((key) => key + 1);
    }

    if (options?.keepAnswer) {
      window.requestAnimationFrame(() => {
        scrollIntoScrollParent(operationalChainRef.current ?? actionJourneyRef.current, {
          block: 'nearest',
          behavior: 'smooth',
        });
      });
    }
  };

  const load = async (scenario: EcScenarioSummary, queryText: string) => {
    const epoch = epochRef.current + 1;
    epochRef.current = epoch;
    setBusy(true);
    setError(null);
    setRevealed(false);
    setSynthesizing(false);
    setEnvelope(null);
    setProgress(null);
    setActionProgress(null);
    setOperationalLink(null);
    setHighlightEvidenceId(null);
    setSelectedId(scenario.scenario_id);
    pushUserMessage(queryText);
    try {
      const next = await runEcScenario(scenario.scenario_id);
      if (epoch !== epochRef.current) return;
      await playThenReveal(next, epoch);
    } catch (err) {
      if (epoch !== epochRef.current) return;
      setError(err instanceof Error ? err.message : 'Investigation interrupted');
    } finally {
      if (epoch === epochRef.current) setBusy(false);
    }
  };

  const followUp = async (
    followUpId: string,
    chip?: EcFollowUpChip,
    options?: { keepAnswer?: boolean; agentPayload?: Record<string, unknown> },
  ) => {
    if (!envelope) return;
    const epoch = epochRef.current + 1;
    epochRef.current = epoch;
    const executiveSummaryOnly = isS4AgentExecutiveSummaryFollowUp(envelope.scenario_id, followUpId);
    const keepAnswer = options?.keepAnswer ?? (isActionChip(chip) || isEvidenceContinueChip(chip) || executiveSummaryOnly);
    const agentInlineProgress = isS4AgentInlineProgress(envelope.scenario_id, followUpId, Boolean(keepAnswer));
    setBusy(true);
    setError(null);
    pushUserMessage(chip?.label ?? followUpId, { scrollMode: executiveSummaryOnly ? 'none' : agentInlineProgress ? 'answer' : 'end' });
    const link = readinessLabelForActionChip(chip);
    const evidenceHighlight = evidenceIdForChip(chip);
    if (!keepAnswer) {
      setRevealed(false);
      setSynthesizing(false);
      setProgress(null);
      setActionProgress(null);
      setOperationalLink(null);
      setHighlightEvidenceId(null);
    } else if (agentInlineProgress) {
      setActionProgress(null);
      setOperationalLink(null);
      setHighlightEvidenceId(null);
    } else {
      setActionProgress(null);
      setOperationalLink(link);
      setHighlightEvidenceId(evidenceHighlight);
    }
    try {
      const next = await followUpEcScenario(
        envelope.scenario_id,
        followUpId,
        envelope.ec_session_state.session_id ?? undefined,
        options?.agentPayload,
      );
      if (epoch !== epochRef.current) return;
      if (executiveSummaryOnly) {
        setEnvelope(next);
        setRevealed(true);
        scrollAgentSection('[data-ec-section="executive-summary"]', 'start');
        return;
      }
      await playThenReveal(next, epoch, { keepAnswer, agentInlineProgress });
    } catch (err) {
      if (epoch !== epochRef.current) return;
      setError(err instanceof Error ? err.message : 'Follow-up failed');
    } finally {
      if (epoch === epochRef.current) setBusy(false);
    }
  };

  const replaceAction = (updated: EcActionRecord) => {
    setEnvelope((current) => {
      if (!current) return current;
      const exists = current.ec_actions.some((item) => item.action_id === updated.action_id);
      return {
        ...current,
        ec_actions: exists
          ? current.ec_actions.map((item) => (item.action_id === updated.action_id ? updated : item))
          : [...current.ec_actions, updated],
      };
    });
  };

  const clearWorkspace = () => {
    epochRef.current += 1;
    skipRef.current = true;
    setEnvelope(null);
    setProgress(null);
    setActionProgress(null);
    setRevealed(false);
    setSynthesizing(false);
    setAnswerRevealKey(0);
    setOperationalLink(null);
    setHighlightEvidenceId(null);
    setBusy(false);
    setError(null);
    setSelectedId('');
    setStream([]);
  };

  const showAnswer = revealed && envelope && !synthesizing;
  const agentMode = envelope?.scenario_id === 's4_zero_day_no_playbook' && Boolean(envelope?.ec_agent_workflow);
  const showWelcomeIdle =
    !busy && !showAnswer && !progress && !synthesizing && stream.length === 0;
  const activeSkill = envelope?.selected_skill;

  return (
    <div
      className={cn(
        'ec-cockpit-shell flex h-full min-h-0 flex-col soc-chat-canvas',
        showWelcomeIdle && 'ec-cockpit-shell--idle',
      )}
    >
      <ScrollArea className="min-h-0 flex-1 scrollbar-thin">
        <div className="ec-cockpit-stream soc-stream space-y-5 py-5">
          {stream.map((message) => (
            <EcChatBubble key={message.id} role={message.role}>
              <p className="ec-prose-wrap">{message.text}</p>
            </EcChatBubble>
          ))}

          {error ? (
            <EcChatBubble role="assistant">
              <p className="text-rose-300">{error}</p>
            </EcChatBubble>
          ) : null}

          {progress && !(envelope?.scenario_id === 's4_zero_day_no_playbook' && envelope.ec_agent_workflow) ? (
            <EcChatBubble role="assistant">
              <div ref={progressAnchorRef} className="space-y-3">
                <div className="flex items-center gap-2 text-sm text-cyan-200">
                  <Activity className="h-4 w-4 animate-pulse" />
                  Running governed investigation pipeline…
                </div>
                <ExperienceExecutionProgressPanel state={progress} />
                {!revealed && !synthesizing ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      skipRef.current = true;
                    }}
                  >
                    Skip to answer
                  </Button>
                ) : null}
              </div>
            </EcChatBubble>
          ) : null}

          {synthesizing ? (
            <EcChatBubble role="assistant">
              <div className="flex items-center gap-2 text-sm text-slate-200">
                <Sparkles className="h-4 w-4 animate-pulse text-cyan-400" />
                <span className="animate-pulse">Synthesizing governed analyst summary…</span>
              </div>
            </EcChatBubble>
          ) : null}

          {showAnswer ? (
            <div
              ref={answerAnchorRef}
              className={cn(
                'ec-answer-stream-item flex gap-3',
                answerMaximized &&
                  'fixed inset-0 z-50 flex-col bg-slate-950/98 p-4 shadow-2xl backdrop-blur-sm sm:p-6',
              )}
              data-ec-chat-role="assistant"
            >
              {answerMaximized ? (
                <div className="flex shrink-0 items-center justify-between border-b border-slate-800 pb-3">
                  <span className="text-sm font-medium text-cyan-100">Investigation answer — expanded</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="border-slate-600"
                    onClick={() => setAnswerMaximized(false)}
                  >
                    <Minimize2 className="mr-2 h-4 w-4" />
                    Exit full screen
                  </Button>
                </div>
              ) : null}
              <div className={cn('flex min-h-0 flex-1 gap-3', answerMaximized && 'overflow-y-auto pt-2')}>
              {!agentMode ? (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-800 text-cyan-200 ring-1 ring-cyan-400/25">
                  <Bot className="h-4 w-4" />
                </div>
              ) : null}
              <div className={cn('min-w-0 flex-1 space-y-6', agentMode && 'w-full max-w-none')}>
                {!answerMaximized ? (
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="text-slate-400 hover:text-cyan-100"
                      onClick={() => setAnswerMaximized(true)}
                    >
                      <Maximize2 className="mr-2 h-4 w-4" />
                      Expand answer
                    </Button>
                  </div>
                ) : null}
                <EcInvestigationAnswer
                  envelope={envelope}
                  embedded
                  revealActive={true}
                  revealKey={answerRevealKey}
                  highlightEvidenceId={highlightEvidenceId}
                  onEvidenceLinkClick={focusEvidence}
                  stepActionBusy={busy}
                  onStepAction={(followUpId) => {
                    const chip = envelope.ec_followups.find((item) => item.follow_up_id === followUpId)
                      ?? { follow_up_id: followUpId, label: followUpId, advances_state: true, group: 'action' as const };
                    void followUp(followUpId, chip, { keepAnswer: true });
                  }}
                  onAgentRunInvestigation={(selectedStepIds) => {
                    void followUp(
                      'run_investigation',
                      { follow_up_id: 'run_investigation', label: 'Run investigation', advances_state: true, group: 'action' },
                      { keepAnswer: true, agentPayload: { selected_step_ids: selectedStepIds } },
                    );
                  }}
                  onAgentRunRemediation={(selectedStepIds) => {
                    void followUp(
                      'run_remediation',
                      { follow_up_id: 'run_remediation', label: 'Approve remediation', advances_state: true, group: 'action' },
                      { keepAnswer: true, agentPayload: { selected_step_ids: selectedStepIds } },
                    );
                  }}
                  onAgentHilApprove={() => {
                    void followUp(
                      'approve_investigation_vuln_scan',
                      {
                        follow_up_id: 'approve_investigation_vuln_scan',
                        label: 'Connect Agilus MCP',
                        advances_state: true,
                        group: 'action',
                      },
                      { keepAnswer: true },
                    );
                  }}
                  onAgentHilSkip={() => {
                    void followUp(
                      'skip_investigation_vuln_scan',
                      {
                        follow_up_id: 'skip_investigation_vuln_scan',
                        label: 'Continue without Agilus',
                        advances_state: true,
                        group: 'continue',
                      },
                      { keepAnswer: true },
                    );
                  }}
                  agentExecutionProgress={
                    agentMode && progress ? progress : null
                  }
                  onCreateRemediationPlan={() => {
                    void followUp(
                      'create_remediation_plan',
                      {
                        follow_up_id: 'create_remediation_plan',
                        label: 'Continue to remediation plan',
                        advances_state: true,
                        group: 'action',
                      },
                      { keepAnswer: true },
                    );
                  }}
                  onDeclineRemediationPlan={() => {
                    void followUp(
                      'decline_remediation_plan',
                      {
                        follow_up_id: 'decline_remediation_plan',
                        label: 'Not now',
                        advances_state: true,
                        group: 'continue',
                      },
                      { keepAnswer: true },
                    );
                  }}
                  onViewEvidence={() => {
                    const panel = document.querySelector('[data-ec-section="source-evidence"]');
                    scrollIntoScrollParent(panel instanceof HTMLElement ? panel : null, {
                      block: 'start',
                      behavior: 'smooth',
                    });
                  }}
                  onEcActionUpdate={replaceAction}
                  onRevealStart={agentMode ? undefined : scrollToAnswerStart}
                  onRevealComplete={agentMode ? undefined : scrollToAnswerStart}
                />
                <EcFollowUpBar
                  chips={envelope.ec_followups}
                  disabled={busy}
                  onSelect={(id, chip) => void followUp(id, chip)}
                />
                {!agentMode && envelope.ec_action_readiness?.length ? (
                  <div
                    ref={operationalChainRef}
                    className={
                      operationalLink
                        ? 'space-y-3 rounded-xl border border-cyan-500/25 bg-cyan-950/10 p-4'
                        : 'space-y-3'
                    }
                    data-ec-operational-chain={operationalLink ? 'true' : undefined}
                  >
                    <EcActionReadinessPanel
                      rows={envelope.ec_action_readiness}
                      highlightAction={operationalLink}
                    />
                    {operationalLink ? (
                      <div className="flex items-center gap-2 px-1 text-xs text-cyan-400/85">
                        <span className="inline-block h-4 w-4 border-l-2 border-b-2 border-cyan-400/50" aria-hidden="true" />
                        <span>Selected action continues below</span>
                      </div>
                    ) : null}
                    {actionProgress ? <ExperienceExecutionProgressPanel state={actionProgress} /> : null}
                    {envelope.ec_actions.length ? (
                      <div ref={actionJourneyRef}>
                        <EcActionFlow
                          actions={envelope.ec_actions}
                          onUpdate={replaceAction}
                          highlightAction={operationalLink}
                        />
                      </div>
                    ) : null}
                  </div>
                ) : !agentMode ? (
                  <>
                    {actionProgress ? <ExperienceExecutionProgressPanel state={actionProgress} /> : null}
                    {envelope.ec_actions.length ? (
                      <div ref={actionJourneyRef}>
                        <EcActionFlow actions={envelope.ec_actions} onUpdate={replaceAction} />
                      </div>
                    ) : null}
                  </>
                ) : null}
                <EcTransparencyDrawer envelope={envelope} />
                <EcCoordinationPanels envelope={envelope} />
              </div>
              </div>
            </div>
          ) : null}

          {showWelcomeIdle ? <EcWelcomeHero /> : null}

          <div ref={streamEndRef} />
        </div>
      </ScrollArea>

      <EcCockpitComposer
        disabled={false}
        busy={busy}
        selectedId={selectedId}
        activeSkill={activeSkill ?? null}
        onSelect={setSelectedId}
        onRun={(scenario, queryText) => void load(scenario, queryText)}
        onClear={clearWorkspace}
      />
    </div>
  );
}
