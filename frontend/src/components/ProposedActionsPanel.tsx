import { useState } from 'react';
import { CheckCircle2, Ticket, XCircle } from 'lucide-react';
import { approveAction, denyAction } from '@/api/client';
import type { ActionProposalEnvelope } from '@/types/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

function toolLabel(toolId: string): string {
  const leaf = toolId.includes(':') ? toolId.split(':').pop() ?? toolId : toolId;
  return leaf.replace(/_/g, ' ');
}

export function ProposedActionsPanel({
  proposals,
  onUpdated,
  busy = false,
}: {
  proposals: ActionProposalEnvelope[];
  onUpdated?: (next: ActionProposalEnvelope[]) => void;
  busy?: boolean;
}) {
  const [local, setLocal] = useState(proposals);
  const [error, setError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);

  const updateLocal = (next: ActionProposalEnvelope[]) => {
    setLocal(next);
    onUpdated?.(next);
  };

  const handleApprove = async (actionId: string) => {
    setError(null);
    setActingId(actionId);
    try {
      const updated = await approveAction(actionId);
      updateLocal(local.map((row) => (row.action_id === actionId ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval failed');
    } finally {
      setActingId(null);
    }
  };

  const handleDeny = async (actionId: string) => {
    setError(null);
    setActingId(actionId);
    try {
      const updated = await denyAction(actionId);
      updateLocal(local.map((row) => (row.action_id === actionId ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Denial failed');
    } finally {
      setActingId(null);
    }
  };

  if (!local.length) return null;

  return (
    <div className="space-y-3">
      {local.map((proposal) => {
        const pending = proposal.status === 'pending_approval';
        const executed = proposal.status === 'executed';
        const denied = proposal.status === 'denied';
        return (
          <div
            key={proposal.action_id}
            className="rounded-xl border border-violet-400/35 bg-violet-500/[0.08] px-4 py-3.5 shadow-sm"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Ticket className="h-4 w-4 text-violet-300" />
              <span className="text-sm font-semibold text-slate-50">Proposed action</span>
              <Badge variant="secondary">{toolLabel(proposal.tool_id)}</Badge>
              <Badge variant={pending ? 'warning' : executed ? 'success' : 'outline'}>
                {String(proposal.status ?? 'unknown').replace(/_/g, ' ')}
              </Badge>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-100">
              {typeof proposal.payload?.summary === 'string' ? proposal.payload.summary : 'No summary provided.'}
            </p>
            <div className="mt-2 rounded-md border border-slate-700/80 bg-slate-950/50 p-3 text-xs text-slate-300">
              <p>
                <span className="text-slate-500">Severity:</span>{' '}
                <span className="font-medium text-slate-100">{String(proposal.payload?.severity_label ?? '—')}</span>
              </p>
              <p className="mt-1">
                <span className="text-slate-500">Source refs:</span>{' '}
                <span className="font-mono text-[0.7rem] text-slate-200">
                  {Array.isArray(proposal.payload?.source_refs)
                    ? proposal.payload.source_refs.join(', ')
                    : '—'}
                </span>
              </p>
              <p className="mt-1 text-[0.65rem] text-slate-500">
                Audit: <span className="font-mono">{proposal.action_id}</span>
                {proposal.trace_id ? (
                  <>
                    {' '}
                    · trace <span className="font-mono">{proposal.trace_id.slice(0, 8)}</span>
                  </>
                ) : null}
              </p>
            </div>
            {executed && proposal.outcome ? (
              <div className="mt-3 flex items-start gap-2 rounded-md border border-emerald-400/30 bg-emerald-500/[0.08] p-3 text-sm text-emerald-50">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                <div>
                  <p className="font-medium">Mock ticket created</p>
                  <p className="mt-1 font-mono text-xs text-emerald-100/90">
                    {String(proposal.outcome.ticket_id ?? '—')}
                  </p>
                </div>
              </div>
            ) : null}
            {denied ? (
              <div className="mt-3 flex items-start gap-2 rounded-md border border-slate-600/50 bg-slate-900/60 p-3 text-sm text-slate-200">
                <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                <p>Action denied. Audit record retained for {proposal.approver ?? 'analyst'}.</p>
              </div>
            ) : null}
            {pending ? (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  disabled={busy || actingId === proposal.action_id}
                  onClick={() => void handleApprove(proposal.action_id)}
                >
                  Approve
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy || actingId === proposal.action_id}
                  onClick={() => void handleDeny(proposal.action_id)}
                >
                  Deny
                </Button>
              </div>
            ) : null}
          </div>
        );
      })}
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
    </div>
  );
}
