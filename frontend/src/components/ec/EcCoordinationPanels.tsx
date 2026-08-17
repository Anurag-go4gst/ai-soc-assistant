import type { EcActionRecord, ExperienceCenterResponse } from '@/components/ec/types';
import { Badge } from '@/components/ui/badge';

function fields(value: Record<string, unknown> | undefined) {
  if (!value) return [];
  return Object.entries(value).map(([key, item]) => (
    <div key={key} className="grid grid-cols-[10rem_1fr] gap-2 text-xs">
      <dt className="text-slate-500">{key.replace(/_/g, ' ')}</dt>
      <dd className="text-slate-300">{Array.isArray(item) ? item.join(', ') : String(item ?? '')}</dd>
    </div>
  ));
}

export function EcCoordinationPanels({ envelope }: { envelope: ExperienceCenterResponse }) {
  const email = envelope.ec_email;
  const tickets = envelope.ec_actions.filter((item) => item.kind.startsWith('ticket_'));
  const tools = envelope.ec_actions.filter((item) =>
    item.kind.startsWith('cisco_') || item.kind.startsWith('firewall_') || item.kind === 'iam_disable',
  );
  if (!email && !tickets.length && !tools.length && !envelope.ec_ticket_id) return null;
  return (
    <div className="grid gap-4 md:grid-cols-2" data-ec-section="coordination">
      {email ? (
        <article className="soc-panel rounded-xl p-4" data-ec-panel="email">
          <p className="soc-eyebrow text-cyan-400">Email</p>
          <h4 className="mt-1 text-sm font-semibold text-slate-100">{email.subject}</h4>
          <p className="mt-1 text-xs text-slate-400">To {email.to}</p>
          <Badge className="mt-2" variant="outline">{email.status ?? 'prepared'}</Badge>
          <dl className="mt-3 space-y-1">{fields(email.mandatory_fields)}</dl>
          {email.inbound ? <p className="mt-3 text-sm text-slate-200">Inbound: {email.inbound}</p> : null}
        </article>
      ) : null}
      {tickets.length || envelope.ec_ticket_id ? (
        <article className="soc-panel rounded-xl p-4" data-ec-panel="ticket">
          <p className="soc-eyebrow text-cyan-400">Ticket</p>
          <p className="mt-1 text-sm text-slate-200">{envelope.ec_ticket_id ?? tickets[0]?.label}</p>
          <ul className="mt-2 space-y-2 text-xs text-slate-400">
            {tickets.map((item) => (
              <li key={item.action_id}>
                {item.label} · {item.state}
                {item.receipt ? <span className="block text-emerald-300">{String(item.receipt.summary ?? '')}</span> : null}
              </li>
            ))}
          </ul>
        </article>
      ) : null}
      {tools.length ? (
        <article className="soc-panel rounded-xl p-4 md:col-span-2" data-ec-panel="tool">
          <p className="soc-eyebrow text-cyan-400">Tool / MCP</p>
          <ul className="mt-2 space-y-2 text-sm text-slate-300">
            {tools.map((item) => (
              <ToolRow key={item.action_id} action={item} />
            ))}
          </ul>
        </article>
      ) : null}
    </div>
  );
}

function ToolRow({ action }: { action: EcActionRecord }) {
  const write = action.kind.includes('upgrade') || action.kind.includes('block') || action.kind.includes('disable') || action.kind.includes('remove');
  return (
    <li className="rounded-lg border border-slate-800 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span>{action.label}</span>
        <Badge variant="outline">{write ? 'write' : 'read'} · {action.state}</Badge>
      </div>
      <p className="mt-1 text-xs text-slate-500">{action.kind} · approval required for write operations</p>
      {action.receipt ? <p className="mt-1 text-xs text-emerald-300">{String(action.receipt.summary ?? 'Receipt recorded')}</p> : null}
      {action.verify_result ? <p className="mt-1 text-xs text-cyan-300">Verified: {JSON.stringify(action.verify_result)}</p> : null}
    </li>
  );
}
