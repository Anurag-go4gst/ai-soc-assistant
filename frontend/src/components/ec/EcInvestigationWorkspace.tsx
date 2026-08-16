import { useState } from 'react';
import { followUpEcScenario, runEcScenario } from '@/api/ecClient';
import { EcActionFlow } from '@/components/ec/EcActionFlow';
import { EcFollowUpBar } from '@/components/ec/EcFollowUpBar';
import { EcInvestigationAnswer } from '@/components/ec/EcInvestigationAnswer';
import { EcScenarioPicker } from '@/components/ec/EcScenarioPicker';
import { EcTransparencyDrawer } from '@/components/ec/EcTransparencyDrawer';
import type { EcActionRecord, EcScenarioSummary, ExperienceCenterResponse } from '@/components/ec/types';
import { ScrollArea } from '@/components/ui/scroll-area';

export function EcInvestigationWorkspace() {
  const [selectedId, setSelectedId] = useState('');
  const [envelope, setEnvelope] = useState<ExperienceCenterResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (scenario: EcScenarioSummary) => {
    setBusy(true);
    setError(null);
    try {
      const next = await runEcScenario(scenario.scenario_id, envelope?.ec_session_state.session_id ?? undefined);
      setSelectedId(scenario.scenario_id);
      setEnvelope(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Investigation failed');
    } finally {
      setBusy(false);
    }
  };

  const followUp = async (followUpId: string) => {
    if (!envelope) return;
    setBusy(true);
    setError(null);
    try {
      setEnvelope(
        await followUpEcScenario(
          envelope.scenario_id,
          followUpId,
          envelope.ec_session_state.session_id ?? undefined,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Follow-up failed');
    } finally {
      setBusy(false);
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

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-5xl space-y-5 p-4 lg:p-6">
        <header>
          <p className="soc-eyebrow text-cyan-400">Experience Center</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight">Investigation workspace</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Visitor showcase of governed SOC investigations. Production chat on /chat is unchanged.
          </p>
        </header>

        <section className="soc-panel rounded-xl p-5">
          <EcScenarioPicker
            disabled={busy}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onRun={load}
          />
          {envelope ? (
            <p className="mt-3 text-xs text-slate-500">
              Turn {envelope.ec_session_state.turn} · {envelope.route_source} · session {envelope.ec_session_state.session_id}
            </p>
          ) : null}
        </section>

        {error ? <p className="text-sm text-rose-300">{error}</p> : null}

        {envelope ? (
          <>
            <EcInvestigationAnswer envelope={envelope} />
            <EcFollowUpBar chips={envelope.ec_followups} disabled={busy} onSelect={(id) => void followUp(id)} />
            <EcTransparencyDrawer envelope={envelope} />
            {envelope.ec_actions.length ? (
              <EcActionFlow actions={envelope.ec_actions} onUpdate={replaceAction} />
            ) : null}
          </>
        ) : (
          <p className="text-sm text-slate-500">Select a scenario and run an investigation to see the SOC answer.</p>
        )}
      </div>
    </ScrollArea>
  );
}
