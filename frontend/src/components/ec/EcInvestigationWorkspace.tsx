import { useEffect, useRef, useState } from 'react';
import { Activity, Bot, Sparkles } from 'lucide-react';
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
import { readinessLabelForActionChip } from '@/lib/ecOperationalLink';
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

export function EcInvestigationWorkspace() {
  const [selectedId, setSelectedId] = useState('');
  const [envelope, setEnvelope] = useState<ExperienceCenterResponse | null>(null);
  const [progress, setProgress] = useState<ExperienceExecutionProgressView | null>(null);
  const [actionProgress, setActionProgress] = useState<ExperienceExecutionProgressView | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [answerRevealKey, setAnswerRevealKey] = useState(0);
  const [operationalLink, setOperationalLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stream, setStream] = useState<EcStreamMessage[]>([]);
  const epochRef = useRef(0);
  const skipRef = useRef(false);
  const actionJourneyRef = useRef<HTMLDivElement | null>(null);
  const answerAnchorRef = useRef<HTMLDivElement | null>(null);
  const progressAnchorRef = useRef<HTMLDivElement | null>(null);
  const streamEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToAnswerStart = () => {
    window.requestAnimationFrame(() => {
      scrollIntoScrollParent(answerAnchorRef.current, { block: 'start', behavior: 'smooth' });
    });
  };

  useEffect(() => {
    if (!progress) return;
    window.requestAnimationFrame(() => {
      scrollIntoScrollParent(progressAnchorRef.current, { block: 'start', behavior: 'smooth' });
    });
  }, [progress?.activeStepIndex, progress?.completedStepIds?.length, progress?.header]);

  const scrollToEnd = () => {
    window.requestAnimationFrame(() => {
      const el = streamEndRef.current;
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
    });
  };

  const pushUserMessage = (text: string) => {
    setStream((current) => [...current, { id: `user-${Date.now()}`, role: 'user', text }]);
    scrollToEnd();
  };

  const playThenReveal = async (
    next: ExperienceCenterResponse,
    epoch: number,
    options?: { keepAnswer?: boolean },
  ) => {
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
      setAnswerRevealKey((key) => key + 1);
    } else if (options?.keepAnswer) {
      setView(null);
      setRevealed(true);
      setAnswerRevealKey((key) => key + 1);
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
        const el = actionJourneyRef.current;
        if (el && typeof el.scrollIntoView === 'function') {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
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

  const followUp = async (followUpId: string, chip?: EcFollowUpChip) => {
    if (!envelope) return;
    const epoch = epochRef.current + 1;
    epochRef.current = epoch;
    const keepAnswer = isActionChip(chip);
    setBusy(true);
    setError(null);
    pushUserMessage(chip?.label ?? followUpId);
    const link = isActionChip(chip) ? readinessLabelForActionChip(chip) : null;
    if (!keepAnswer) {
      setRevealed(false);
      setSynthesizing(false);
      setProgress(null);
      setActionProgress(null);
      setOperationalLink(null);
    } else {
      setActionProgress(null);
      setOperationalLink(link);
    }
    try {
      const next = await followUpEcScenario(
        envelope.scenario_id,
        followUpId,
        envelope.ec_session_state.session_id ?? undefined,
      );
      if (epoch !== epochRef.current) return;
      await playThenReveal(next, epoch, { keepAnswer });
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
      return {
        ...current,
        ec_actions: current.ec_actions.map((item) => (item.action_id === updated.action_id ? updated : item)),
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
    setBusy(false);
    setError(null);
    setSelectedId('');
    setStream([]);
  };

  const showAnswer = revealed && envelope && !synthesizing;
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

          {progress ? (
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
              className="ec-answer-stream-item flex gap-3"
              data-ec-chat-role="assistant"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-800 text-cyan-200 ring-1 ring-cyan-400/25">
                <Bot className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-6">
                <EcInvestigationAnswer
                  envelope={envelope}
                  embedded
                  revealActive={true}
                  revealKey={answerRevealKey}
                  onRevealStart={scrollToAnswerStart}
                  onRevealComplete={scrollToAnswerStart}
                />
                <EcFollowUpBar
                  chips={envelope.ec_followups}
                  disabled={busy}
                  onSelect={(id, chip) => void followUp(id, chip)}
                />
                {envelope.ec_action_readiness?.length ? (
                  <div
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
                ) : (
                  <>
                    {actionProgress ? <ExperienceExecutionProgressPanel state={actionProgress} /> : null}
                    {envelope.ec_actions.length ? (
                      <div ref={actionJourneyRef}>
                        <EcActionFlow actions={envelope.ec_actions} onUpdate={replaceAction} />
                      </div>
                    ) : null}
                  </>
                )}
                <EcTransparencyDrawer envelope={envelope} />
                <EcCoordinationPanels envelope={envelope} />
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
