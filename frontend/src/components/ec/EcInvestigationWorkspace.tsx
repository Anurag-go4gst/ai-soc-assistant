import { useRef, useState } from 'react';
import { followUpEcScenario, runEcScenario } from '@/api/ecClient';
import { EcActionFlow } from '@/components/ec/EcActionFlow';
import { EcCoordinationPanels } from '@/components/ec/EcCoordinationPanels';
import { EcFollowUpBar } from '@/components/ec/EcFollowUpBar';
import { EcInvestigationAnswer } from '@/components/ec/EcInvestigationAnswer';
import { EcScenarioPicker } from '@/components/ec/EcScenarioPicker';
import { EcTransparencyDrawer } from '@/components/ec/EcTransparencyDrawer';
import { playEcExecutionJourney, resolveJourney } from '@/components/ec/ecExecutionJourneyPlayer';
import type { EcActionRecord, EcScenarioSummary, ExperienceCenterResponse } from '@/components/ec/types';
import { ExperienceExecutionProgressPanel } from '@/components/experience-center/ExperienceExecutionProgressPanel';
import type { ExperienceExecutionProgressView } from '@/lib/experienceCenterExecution';
import { ScrollArea } from '@/components/ui/scroll-area';

export function EcInvestigationWorkspace() {
  const [selectedId, setSelectedId] = useState('');
  const [envelope, setEnvelope] = useState<ExperienceCenterResponse | null>(null);
  const [progress, setProgress] = useState<ExperienceExecutionProgressView | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const epochRef = useRef(0);

  const playThenReveal = async (next: ExperienceCenterResponse, epoch: number) => {
    const ok = await playEcExecutionJourney(resolveJourney(next.ec_execution_journey), setProgress, {
      isStale: () => epoch !== epochRef.current,
    });
    if (!ok || epoch !== epochRef.current) return;
    setEnvelope(next);
    setRevealed(true);
  };

  const load = async (scenario: EcScenarioSummary) => {
    const epoch = epochRef.current + 1;
    epochRef.current = epoch;
    setBusy(true);
    setError(null);
    setRevealed(false);
    setEnvelope(null);
    setProgress(null);
    setSelectedId(scenario.scenario_id);
    try {
      const next = await runEcScenario(scenario.scenario_id);
      if (epoch !== epochRef.current) return;
      await playThenReveal(next, epoch);
    } catch (err) {
      if (epoch !== epochRef.current) return;
      setError(err instanceof Error ? err.message : 'Investigation failed');
    } finally {
      if (epoch === epochRef.current) setBusy(false);
    }
  };

  const followUp = async (followUpId: string) => {
    if (!envelope) return;
    const epoch = epochRef.current + 1;
    epochRef.current = epoch;
    setBusy(true);
    setError(null);
    setRevealed(false);
    try {
      const next = await followUpEcScenario(
        envelope.scenario_id,
        followUpId,
        envelope.ec_session_state.session_id ?? undefined,
      );
      if (epoch !== epochRef.current) return;
      await playThenReveal(next, epoch);
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

  const showAnswer = revealed && envelope;

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-5xl space-y-5 p-4 lg:p-6">
        <header>
          <p className="soc-eyebrow text-cyan-400">Experience Center</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight">Investigation workspace</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Seven flagship investigations plus a lab of additional scenarios. Production chat on /chat is unchanged.
          </p>
        </header>

        <section className="soc-panel rounded-xl p-5">
          <EcScenarioPicker
            selectedId={selectedId}
            onSelect={setSelectedId}
            onRun={load}
          />
          {envelope && revealed ? (
            <p className="mt-3 text-xs text-slate-500">Investigation active</p>
          ) : null}
        </section>

        {error ? <p className="text-sm text-rose-300">{error}</p> : null}

        {progress ? <ExperienceExecutionProgressPanel state={progress} /> : null}

        {showAnswer ? (
          <>
            <EcInvestigationAnswer envelope={envelope} />
            <EcFollowUpBar chips={envelope.ec_followups} disabled={busy} onSelect={(id) => void followUp(id)} />
            <EcTransparencyDrawer envelope={envelope} />
            <EcCoordinationPanels envelope={envelope} />
            {envelope.ec_actions.length ? (
              <EcActionFlow actions={envelope.ec_actions} onUpdate={replaceAction} />
            ) : null}
          </>
        ) : progress ? null : (
          <p className="text-sm text-slate-500">Select a scenario and run an investigation to see the SOC answer.</p>
        )}
      </div>
    </ScrollArea>
  );
}
