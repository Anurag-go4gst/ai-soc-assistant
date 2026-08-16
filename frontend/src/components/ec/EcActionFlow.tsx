import { useState } from 'react';
import { approveEcAction, executeEcAction, verifyEcAction } from '@/api/ecClient';
import type { EcActionRecord } from '@/components/ec/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export function EcActionFlow({
  actions,
  onUpdate,
}: {
  actions: EcActionRecord[];
  onUpdate: (action: EcActionRecord) => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!actions.length) return null;

  const run = async (actionId: string, fn: (id: string) => Promise<EcActionRecord>) => {
    setBusyId(actionId);
    setError(null);
    try {
      onUpdate(await fn(actionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="soc-panel space-y-4 rounded-xl p-5" data-ec-layer="action-journey">
      <header>
        <p className="soc-eyebrow text-cyan-400">Action Journey</p>
        <p className="mt-1 text-sm text-slate-400">Recommended → HIL → execute → receipt → verify. No production side effects.</p>
      </header>
      {actions.map((action) => (
        <article key={action.action_id} className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-slate-100">{action.label}</h4>
            <Badge variant={action.state === 'VERIFIED' ? 'success' : 'outline'}>{action.state}</Badge>
          </div>
          <p className="mt-1 text-xs text-slate-500">{action.kind} · no production change</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" disabled={busyId === action.action_id} onClick={() => void run(action.action_id, approveEcAction)}>
              Approve
            </Button>
            <Button size="sm" disabled={busyId === action.action_id} onClick={() => void run(action.action_id, executeEcAction)}>
              Execute
            </Button>
            <Button size="sm" variant="outline" disabled={busyId === action.action_id} onClick={() => void run(action.action_id, verifyEcAction)}>
              Verify
            </Button>
          </div>
          {action.receipt ? (
            <p className="mt-2 text-xs text-emerald-300">{String(action.receipt.summary ?? 'Receipt recorded')}</p>
          ) : null}
        </article>
      ))}
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
    </section>
  );
}
