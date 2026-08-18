import { useEffect, useState } from 'react';
import { Mail, Ticket } from 'lucide-react';
import { approveEcAction, executeEcAction, prepareEcAction } from '@/api/ecClient';
import type { EcActionRecord } from '@/components/ec/types';
import { EC_DEMO_EMAIL_FROM_LABEL, EC_DEMO_EMAIL_TO } from '@/lib/ecDemoEmail';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

type EmailDraftShape = {
  to?: string;
  subject?: string;
  body?: string;
  body_preview?: string;
  send_note?: string;
  status?: string;
};

type TicketDetailShape = {
  ticket_id?: string;
  ticket_type?: string;
  priority?: string;
  title?: string;
  status?: string;
  assignee_group?: string;
  linked_advisory?: string;
  linked_incident?: string;
};

function readEmailDraft(details: Record<string, unknown> | undefined): EmailDraftShape | null {
  const raw = details?.email_draft;
  if (!raw || typeof raw !== 'object') return null;
  return raw as EmailDraftShape;
}

export function readTicketDetail(details: Record<string, unknown> | undefined): TicketDetailShape | null {
  const raw = details?.ticket_detail;
  if (!raw || typeof raw !== 'object') return null;
  return raw as TicketDetailShape;
}

export function resolveEmailDraft(
  emailDraft?: EmailDraftShape | null,
  emailExtra?: Record<string, unknown>,
): EmailDraftShape {
  if (emailDraft?.subject || emailDraft?.body || emailDraft?.body_preview) {
    return emailDraft;
  }
  const envelopeEmail =
    emailExtra && typeof emailExtra.email === 'object'
      ? (emailExtra.email as Record<string, unknown>)
      : undefined;
  if (envelopeEmail) {
    return {
      subject: String(envelopeEmail.subject ?? ''),
      body: String(envelopeEmail.body ?? ''),
      send_note: emailDraft?.send_note,
    };
  }
  return { subject: '', body: '' };
}

export function stepHasEmailArtifact(step: { finding?: { details?: Record<string, unknown> } | null }): boolean {
  const details = step.finding?.details;
  if (!details) return false;
  return Boolean(readEmailDraft(details) || details.email_extra);
}

export function stepHasTicketArtifact(step: { finding?: { details?: Record<string, unknown> } | null }): boolean {
  return Boolean(readTicketDetail(step.finding?.details));
}

async function sendEcEmail({
  scenarioId,
  sessionId,
  label,
  extra,
  to,
  subject,
  body,
  existingAction,
}: {
  scenarioId: string;
  sessionId?: string | null;
  label: string;
  extra?: Record<string, unknown>;
  to: string;
  subject: string;
  body: string;
  existingAction?: EcActionRecord | null;
}): Promise<EcActionRecord> {
  let current =
    existingAction ??
    (await prepareEcAction({
      kind: 'email_send',
      label,
      scenario_id: scenarioId,
      session_id: sessionId ?? null,
      extra: {
        ...(extra ?? {}),
        email: { to, subject, body },
      },
    }));
  if (current.state === 'APPROVAL_REQUIRED' || current.state === 'PREPARED') {
    current = await approveEcAction(current.action_id, current);
  }
  return executeEcAction(current.action_id, { to, subject, body }, current);
}

async function confirmEcTicket({
  scenarioId,
  sessionId,
  label,
  ticket,
  existingAction,
}: {
  scenarioId: string;
  sessionId?: string | null;
  label: string;
  ticket: TicketDetailShape;
  existingAction?: EcActionRecord | null;
}): Promise<EcActionRecord> {
  const extra = {
    ticket: {
      id: ticket.ticket_id,
      ticket_id: ticket.ticket_id,
      type: ticket.ticket_type,
      priority: ticket.priority,
      title: ticket.title,
    },
  };
  let current =
    existingAction ??
    (await prepareEcAction({
      kind: 'ticket_create',
      label,
      scenario_id: scenarioId,
      session_id: sessionId ?? null,
      extra,
    }));
  if (current.state === 'APPROVAL_REQUIRED' || current.state === 'PREPARED') {
    current = await approveEcAction(current.action_id, current);
  }
  return executeEcAction(current.action_id, undefined, current);
}

export function EcEmailArtifactButton({
  stepTitle,
  emailDraft: emailDraftInput,
  emailExtra,
  scenarioId,
  sessionId,
  existingAction,
  onActionUpdate,
  disabled = false,
}: {
  stepTitle: string;
  emailDraft?: EmailDraftShape | null;
  emailExtra?: Record<string, unknown>;
  scenarioId: string;
  sessionId?: string | null;
  existingAction?: EcActionRecord | null;
  onActionUpdate?: (action: EcActionRecord) => void;
  disabled?: boolean;
}) {
  const emailDraft = resolveEmailDraft(emailDraftInput, emailExtra);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [subject, setSubject] = useState(emailDraft.subject ?? '');
  const [body, setBody] = useState(emailDraft.body ?? emailDraft.body_preview ?? '');
  const sent = existingAction?.state === 'EXECUTED';

  useEffect(() => {
    if (!open) return;
    setSubject(emailDraft.subject ?? '');
    setBody(emailDraft.body ?? emailDraft.body_preview ?? '');
    setError(null);
  }, [open, emailDraft.body, emailDraft.body_preview, emailDraft.subject]);

  return (
    <>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-8 shrink-0 border-sky-500/40 bg-sky-950/30 text-sky-100 hover:bg-sky-900/50"
        aria-label={`Open email for ${stepTitle}`}
        disabled={disabled}
        onClick={(event) => {
          event.stopPropagation();
          setOpen(true);
        }}
      >
        <Mail className="mr-1.5 h-4 w-4" aria-hidden="true" />
        Email
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="w-[min(94vw,720px)] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Remediation email</DialogTitle>
            <DialogDescription>{stepTitle}</DialogDescription>
          </DialogHeader>

          <div className="space-y-3 text-sm">
            <div className="space-y-1.5">
              <Label htmlFor={`ec-email-from-${stepTitle}`}>From</Label>
              <Input id={`ec-email-from-${stepTitle}`} value={EC_DEMO_EMAIL_FROM_LABEL} readOnly disabled />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`ec-email-to-${stepTitle}`}>To</Label>
              <Input id={`ec-email-to-${stepTitle}`} value={EC_DEMO_EMAIL_TO} readOnly disabled />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`ec-email-subject-${stepTitle}`}>Subject</Label>
              <Input
                id={`ec-email-subject-${stepTitle}`}
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                disabled={sent || busy}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`ec-email-body-${stepTitle}`}>Email body</Label>
              <Textarea
                id={`ec-email-body-${stepTitle}`}
                value={body}
                onChange={(event) => setBody(event.target.value)}
                disabled={sent || busy}
                className="min-h-[280px] whitespace-pre-wrap font-sans text-sm"
              />
            </div>
            {emailDraft.send_note ? <p className="text-xs text-slate-400">{emailDraft.send_note}</p> : null}
          </div>

          {error ? <p className="text-xs text-rose-300">{error}</p> : null}
          {existingAction?.receipt ? (
            <p className="text-xs text-emerald-300">
              {String((existingAction.receipt as Record<string, unknown>).summary ?? 'Email sent')}
            </p>
          ) : null}

          {!sent && onActionUpdate ? (
            <Button
              className="mt-2"
              disabled={busy || !subject.trim() || !body.trim()}
              onClick={() => {
                void (async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const updated = await sendEcEmail({
                      scenarioId,
                      sessionId,
                      label: stepTitle,
                      extra: emailExtra,
                      to: EC_DEMO_EMAIL_TO,
                      subject: subject.trim(),
                      body: body.trim(),
                      existingAction,
                    });
                    onActionUpdate?.(updated);
                    setOpen(false);
                  } catch (err) {
                    setError(err instanceof Error ? err.message : 'Send failed');
                  } finally {
                    setBusy(false);
                  }
                })();
              }}
            >
              {busy ? 'Sending…' : 'Send email'}
            </Button>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

export function EcTicketArtifactButton({
  stepTitle,
  ticket,
  scenarioId,
  sessionId,
  existingAction,
  onActionUpdate,
  disabled = false,
}: {
  stepTitle: string;
  ticket: TicketDetailShape;
  scenarioId: string;
  sessionId?: string | null;
  existingAction?: EcActionRecord | null;
  onActionUpdate?: (action: EcActionRecord) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const done = existingAction?.state === 'EXECUTED' || existingAction?.state === 'VERIFIED';

  return (
    <>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-8 shrink-0 border-violet-500/40 bg-violet-950/30 text-violet-100 hover:bg-violet-900/50"
        aria-label={`Open ticket for ${stepTitle}`}
        disabled={disabled}
        onClick={(event) => {
          event.stopPropagation();
          setOpen(true);
        }}
      >
        <Ticket className="mr-1.5 h-4 w-4" aria-hidden="true" />
        Ticket
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="w-[min(94vw,560px)]">
          <DialogHeader>
            <DialogTitle>ITSM ticket</DialogTitle>
            <DialogDescription>{stepTitle}</DialogDescription>
          </DialogHeader>

          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Ticket number</dt>
              <dd className="mt-0.5 font-mono text-base text-slate-50">{ticket.ticket_id ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Type</dt>
              <dd className="mt-0.5 text-slate-200">{ticket.ticket_type ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Priority</dt>
              <dd className="mt-0.5 text-slate-200">{ticket.priority ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Title</dt>
              <dd className="mt-0.5 text-slate-200">{ticket.title ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Status</dt>
              <dd className="mt-0.5 text-slate-200">{ticket.status ?? 'Draft'}</dd>
            </div>
            {ticket.assignee_group ? (
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Assignment group</dt>
                <dd className="mt-0.5 text-slate-200">{ticket.assignee_group}</dd>
              </div>
            ) : null}
            {ticket.linked_advisory ? (
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Linked advisory</dt>
                <dd className="mt-0.5 font-mono text-slate-200">{ticket.linked_advisory}</dd>
              </div>
            ) : null}
            {ticket.linked_incident ? (
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Linked incident</dt>
                <dd className="mt-0.5 font-mono text-slate-200">{ticket.linked_incident}</dd>
              </div>
            ) : null}
          </dl>

          {error ? <p className="text-xs text-rose-300">{error}</p> : null}
          {existingAction?.receipt ? (
            <p className="text-xs text-emerald-300">
              {String((existingAction.receipt as Record<string, unknown>).summary ?? 'Ticket created')}
            </p>
          ) : null}

          {!done && onActionUpdate ? (
            <Button
              className="mt-2"
              disabled={busy || !ticket.ticket_id}
              onClick={() => {
                void (async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const updated = await confirmEcTicket({
                      scenarioId,
                      sessionId,
                      label: stepTitle,
                      ticket,
                      existingAction,
                    });
                    onActionUpdate?.(updated);
                    setOpen(false);
                  } catch (err) {
                    setError(err instanceof Error ? err.message : 'Ticket creation failed');
                  } finally {
                    setBusy(false);
                  }
                })();
              }}
            >
              {busy ? 'Creating…' : 'Confirm ticket'}
            </Button>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
