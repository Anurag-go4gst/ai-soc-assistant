import { useState } from 'react';
import type { EcEmailDelivery, EcPriorityControl, EcTicketRecord } from '@/components/ec/types';
import { cn } from '@/lib/utils';

/** Incident priority before approval: policy value by default; any change needs a reason. */
export function EcPriorityPicker({
  control,
  priority,
  reason,
  onChange,
}: {
  control: EcPriorityControl;
  priority: string;
  reason: string;
  onChange: (priority: string, reason: string) => void;
}) {
  const overridden = priority !== control.policy_priority;
  return (
    <div className="mt-2 space-y-2 rounded-md border border-slate-700/80 bg-slate-950/50 p-2.5 text-xs" data-ec-priority-picker>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="ec-incident-priority" className="text-slate-400">
          Priority
        </label>
        <select
          id="ec-incident-priority"
          className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-100"
          value={priority}
          onChange={(event) => onChange(event.target.value, reason)}
        >
          {control.options.map((option) => (
            <option key={option} value={option}>
              {option}
              {option === control.policy_priority ? ' (policy)' : ''}
            </option>
          ))}
        </select>
        <span className="text-slate-500">
          Policy: {control.policy_priority} · {control.policy_rule} ({control.policy_basis})
        </span>
      </div>
      {overridden ? (
        <div className="space-y-1">
          <label htmlFor="ec-incident-priority-reason" className="text-amber-200">
            Reason for changing from {control.policy_priority} to {priority} (recorded on the ticket)
          </label>
          <input
            id="ec-incident-priority-reason"
            type="text"
            maxLength={300}
            className="w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-slate-100"
            value={reason}
            onChange={(event) => onChange(priority, event.target.value)}
            placeholder="e.g. Jump host is in scope of an active audit"
          />
        </div>
      ) : null}
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="whitespace-pre-wrap text-slate-200">{value}</dd>
    </div>
  );
}

/** The ticket as ITSM holds it after creation — the evidence that it exists. */
export function EcTicketCard({ ticket }: { ticket: EcTicketRecord }) {
  return (
    <dl className="mt-2 space-y-1.5 rounded-md border border-slate-700/80 bg-slate-950/60 p-3 text-xs" data-ec-ticket={ticket.number}>
      <Field label="Number" value={ticket.number} />
      <Field label="Type" value={ticket.type} />
      <Field label="State" value={ticket.state} />
      <Field label="Priority" value={ticket.priority} />
      <Field label="Threat assessment" value={ticket.threat_assessment} />
      <Field label="Category" value={ticket.category} />
      <Field label="Configuration item" value={ticket.configuration_item} />
      <Field label="Assignment group" value={ticket.assignment_group} />
      <Field label="Short description" value={ticket.short_description} />
      <Field label="Description" value={ticket.description} />
      <Field label="Work note" value={ticket.work_note} />
      <Field label="Parent incident" value={ticket.parent ?? undefined} />
      <Field label="Related" value={ticket.related?.join(', ')} />
      <Field label="Opened" value={ticket.opened ?? ticket.updated} />
      <Field label="Opened by" value={ticket.opened_by ?? ticket.updated_by} />
      {ticket.attachment ? (
        <div className="grid grid-cols-[9rem_1fr] gap-2">
          <dt className="text-slate-500">Attachment</dt>
          <dd>
            <pre className="overflow-x-auto rounded bg-slate-900/80 p-2 font-mono text-[11px] text-slate-300">{ticket.attachment}</pre>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

/** The email as sent, with what the mail transport actually reported. */
export function EcEmailCard({
  email,
  delivery,
}: {
  email: { to: string; subject: string; body: string };
  delivery?: EcEmailDelivery | null;
}) {
  const recipients = delivery?.sent
    ? [delivery.to_address, ...(delivery.cc_addresses ?? []).map((address) => `cc ${address}`)].filter(Boolean).join(' · ')
    : email.to;
  return (
    <div className="mt-2 rounded-md border border-slate-700/80 bg-slate-950/60 p-3 text-xs" data-ec-email-sent>
      {delivery ? (
        <p className={cn('mb-2 font-medium', delivery.sent ? 'text-emerald-300' : 'text-rose-300')}>{delivery.line}</p>
      ) : null}
      <p className="text-slate-400">
        To: <span className="text-slate-200">{recipients}</span>
      </p>
      {delivery?.cc_not_copied?.length ? (
        <p className="text-slate-500">Not copied (no address configured): {delivery.cc_not_copied.join(', ')}</p>
      ) : null}
      {delivery?.message_id ? <p className="text-slate-500">Message ID: {delivery.message_id}</p> : null}
      <p className="mt-1 font-medium text-slate-100">{email.subject}</p>
      <pre className="mt-2 max-h-64 overflow-y-auto whitespace-pre-wrap font-sans leading-relaxed text-slate-300">{email.body}</pre>
    </div>
  );
}

/** "View ticket" / "View email" toggle for one completed action. */
export function EcActionRecordToggle({
  ticket,
  email,
  delivery,
}: {
  ticket?: EcTicketRecord | null;
  email?: { to: string; subject: string; body: string } | null;
  delivery?: EcEmailDelivery | null;
}) {
  const [open, setOpen] = useState(false);
  if (!ticket && !email) return null;
  const label = ticket ? (open ? 'Hide ticket' : 'View ticket') : open ? 'Hide email' : 'View email';
  return (
    <div className="w-full">
      <button type="button" className="text-xs text-cyan-400 hover:text-cyan-300" onClick={() => setOpen((value) => !value)}>
        {label}
      </button>
      {open && ticket ? <EcTicketCard ticket={ticket} /> : null}
      {open && !ticket && email ? <EcEmailCard email={email} delivery={delivery} /> : null}
    </div>
  );
}
