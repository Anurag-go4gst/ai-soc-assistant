import { useEffect, useState } from 'react';
import { getHealth } from '../api/client';
import { AlertList } from '../components/AlertList';
import { ApprovalPanel } from '../components/ApprovalPanel';
import { ChatPanel } from '../components/ChatPanel';
import { EvidencePanel } from '../components/EvidencePanel';
import { GraphContextPanel } from '../components/GraphContextPanel';
import { SopReferencePanel } from '../components/SopReferencePanel';
import { SplTracePanel } from '../components/SplTracePanel';
import { CompareResultPanel } from '../components/debug/CompareResultPanel';
import { DeterministicRouterPanel } from '../components/debug/DeterministicRouterPanel';
import { NodeTimeline } from '../components/debug/NodeTimeline';
import { PlannerDecisionPanel } from '../components/debug/PlannerDecisionPanel';
import type { HealthResponse } from '../types/api';

interface SocCockpitProps {
  username: string;
  onLogout: () => Promise<void>;
}

export function SocCockpit({ username, onLogout }: SocCockpitProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Internal development scaffold</p>
          <h1>AI SOC Assistant</h1>
        </div>
        <div className={`status ${health?.status === 'ok' ? 'ok' : 'warn'}`}>
          Backend: {health?.status ?? (error ? 'unavailable' : 'checking')}
        </div>
        <div className="userControls">
          <span>{username}</span>
          <button type="button" className="secondaryButton" onClick={() => void onLogout()}>
            Logout
          </button>
        </div>
      </header>

      <section className="grid">
        <AlertList />
        <ChatPanel />
        <EvidencePanel />
        <SplTracePanel />
        <GraphContextPanel />
        <SopReferencePanel />
        <ApprovalPanel />
      </section>

      <section className="debugGrid" aria-label="Debug panels">
        <PlannerDecisionPanel />
        <DeterministicRouterPanel />
        <CompareResultPanel />
        <NodeTimeline />
      </section>
    </main>
  );
}
