import { Clock3, Mail, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { RequestedConditionalAction } from '@/types/api';

interface ConditionalRequestedActionsCardProps {
  actions?: RequestedConditionalAction[] | null;
}

export function ConditionalRequestedActionsCard({ actions }: ConditionalRequestedActionsCardProps) {
  const pending = (Array.isArray(actions) ? actions : []).filter(
    (action) => action.lifecycle_state === 'PENDING_CONDITION',
  );
  if (!pending.length) return null;

  return (
    <section
      aria-label="Requested conditional actions"
      className="w-full min-w-0 max-w-[72ch] rounded-xl border border-amber-400/30 bg-amber-500/[0.07] p-4 text-sm text-slate-100 shadow-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Clock3 className="h-4 w-4 text-amber-300" />
        <h3 className="font-semibold text-amber-100">Requested conditional actions</h3>
        <Badge variant="warning">Pending condition</Badge>
      </div>
      <p className="mt-2 leading-6 text-slate-300">
        These requests are preserved, but are not eligible, approved, sent, or executed.
      </p>
      <ul className="mt-3 space-y-2">
        {pending.map((action, index) => (
          <li
            key={`${action.action_kind}-${action.predicate_id ?? 'unconditional'}-${index}`}
            className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2"
          >
            <div className="flex items-center gap-2 font-medium text-slate-100">
              {action.action_kind === 'email_draft'
                ? <Mail className="h-4 w-4 text-cyan-300" />
                : <ShieldCheck className="h-4 w-4 text-cyan-300" />}
              <span>{actionLabel(action.action_kind)}</span>
            </div>
            {action.predicate_id ? (
              <p className="mt-1 text-xs text-amber-100">
                Required governed condition (not yet satisfied):{' '}
                <span className="font-mono">{action.predicate_id}</span>
              </p>
            ) : null}
            {action.recipient_roles?.length ? (
              <p className="mt-1 text-xs text-slate-300">
                Recipient roles: {action.recipient_roles.map(humanize).join(', ')}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function actionLabel(kind: RequestedConditionalAction['action_kind']): string {
  return kind === 'email_draft' ? 'Email draft requested' : 'Remediation plan requested';
}

function humanize(value: string): string {
  return value.replace(/_/g, ' ').trim();
}
