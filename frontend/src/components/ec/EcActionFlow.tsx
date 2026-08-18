import { useEffect, useState, type ReactNode } from 'react';
import { approveEcAction, executeEcAction, verifyEcAction } from '@/api/ecClient';
import type { EcActionRecord } from '@/components/ec/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

function textValue(draft: Record<string, unknown> | null | undefined, key: string): string {
  const value = draft?.[key];
  return typeof value === 'string' ? value : value == null ? '' : String(value);
}

function actionMatchesHighlight(action: EcActionRecord, highlight: string): boolean {
  const needle = highlight.trim().toLowerCase();
  if (!needle) return false;
  const label = action.label.toLowerCase();
  const kind = action.kind.toLowerCase();
  return label.includes(needle) || needle.includes(label.slice(0, 14)) || needle.includes(kind.replace(/_/g, ' '));
}

export function EcActionFlow({
  actions,
  onUpdate,
  highlightAction = null,
}: {
  actions: EcActionRecord[];
  onUpdate: (action: EcActionRecord) => void;
  highlightAction?: string | null;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!actions.length) return null;

  const run = async (
    action: EcActionRecord,
    fn: () => Promise<EcActionRecord>,
  ) => {
    setBusyId(action.action_id);
    setError(null);
    try {
      onUpdate(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section
      className={
        highlightAction
          ? 'soc-panel space-y-4 rounded-xl border border-cyan-400/35 bg-cyan-950/15 p-5 ring-1 ring-cyan-400/20'
          : 'soc-panel space-y-4 rounded-xl p-5'
      }
      data-ec-layer="action-journey"
      data-ec-action-highlight={highlightAction ? 'true' : undefined}
    >
      {highlightAction ? (
        <p className="text-xs font-medium text-cyan-300/90">↓ Action journey for selected readiness step</p>
      ) : null}
      <header>
        <p className="soc-eyebrow text-cyan-400">Action Journey</p>
        <p className="mt-1 text-sm text-slate-400">
          Review the draft, then confirm. Email can send now. Firewall blocks go through SOAR / firewall MCP when configured.
        </p>
      </header>
      {actions.map((action) => (
        <ActionCard
          key={action.action_id}
          action={action}
          busy={busyId === action.action_id}
          highlighted={highlightAction ? actionMatchesHighlight(action, highlightAction) : false}
          onRun={(fn) => void run(action, fn)}
        />
      ))}
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
    </section>
  );
}

function ActionCard({
  action,
  busy,
  highlighted = false,
  onRun,
}: {
  action: EcActionRecord;
  busy: boolean;
  highlighted?: boolean;
  onRun: (fn: () => Promise<EcActionRecord>) => void;
}) {
  let inner: ReactNode;
  if (action.kind === 'email_send' || action.kind === 'email_reply') {
    inner = <EmailDraftCard action={action} busy={busy} onRun={onRun} />;
  } else if (action.kind.startsWith('firewall_')) {
    inner = <SoarDraftCard action={action} busy={busy} onRun={onRun} />;
  } else if (action.kind.startsWith('ticket_')) {
    inner = <TicketDraftCard action={action} busy={busy} onRun={onRun} />;
  } else {
    inner = <GenericActionCard action={action} busy={busy} onRun={onRun} />;
  }
  if (!highlighted) return inner;
  return (
    <div className="rounded-lg ring-2 ring-cyan-400/35 ring-offset-2 ring-offset-slate-950" data-ec-action-card-highlight="true">
      {inner}
    </div>
  );
}

function EmailDraftCard({
  action,
  busy,
  onRun,
}: {
  action: EcActionRecord;
  busy: boolean;
  onRun: (fn: () => Promise<EcActionRecord>) => void;
}) {
  const [to, setTo] = useState(textValue(action.draft, 'to'));
  const [subject, setSubject] = useState(textValue(action.draft, 'subject'));
  const [body, setBody] = useState(textValue(action.draft, 'body'));
  useEffect(() => {
    setTo(textValue(action.draft, 'to'));
    setSubject(textValue(action.draft, 'subject'));
    setBody(textValue(action.draft, 'body'));
  }, [action.action_id, action.draft]);
  const sent = action.state === 'EXECUTED';
  const failed = action.state === 'FAILED';
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-100">{action.label}</h4>
        <Badge variant={sent ? 'success' : 'outline'}>{action.state}</Badge>
      </div>
      <p className="mt-1 text-xs text-slate-500">Editable draft · Send uses the allowlisted EC SMTP adapter</p>
      <div className="mt-3 space-y-3">
        <Field label="To">
          <Input value={to} onChange={(event) => setTo(event.target.value)} disabled={sent || busy} />
        </Field>
        <Field label="Subject">
          <Input value={subject} onChange={(event) => setSubject(event.target.value)} disabled={sent || busy} />
        </Field>
        <Field label="Email body">
          <Textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            disabled={sent || busy}
            className="min-h-[220px] whitespace-pre-wrap"
          />
        </Field>
      </div>
      {!sent ? (
        <Button
          className="mt-4"
          size="sm"
          disabled={busy || !to.trim() || !subject.trim() || !body.trim()}
          onClick={() =>
            onRun(async () => {
              let current = action;
              if (current.state === 'APPROVAL_REQUIRED' || current.state === 'PREPARED') {
                current = await approveEcAction(current.action_id, current);
              }
              return executeEcAction(current.action_id, { to, subject, body }, current);
            })
          }
        >
          Send email
        </Button>
      ) : null}
      {action.receipt ? (
        <p className={`mt-2 text-xs ${failed ? 'text-rose-300' : 'text-emerald-300'}`}>
          {String(action.receipt.summary ?? action.receipt.status ?? 'Receipt recorded')}
        </p>
      ) : null}
    </article>
  );
}

function SoarDraftCard({
  action,
  busy,
  onRun,
}: {
  action: EcActionRecord;
  busy: boolean;
  onRun: (fn: () => Promise<EcActionRecord>) => void;
}) {
  const done = action.state === 'EXECUTED' || action.state === 'VERIFIED' || action.state === 'FAILED';
  const canVerify = action.state === 'EXECUTED';
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-100">{action.label}</h4>
        <Badge variant={action.state === 'VERIFIED' ? 'success' : 'outline'}>{action.state}</Badge>
      </div>
      <p className="mt-1 text-xs text-slate-500">SOAR / firewall MCP request · no direct production firewall change from this console</p>
      <dl className="mt-3 space-y-1 text-xs">
        <DraftLine label="Playbook" value={textValue(action.draft, 'playbook')} />
        <DraftLine label="Indicator" value={textValue(action.draft, 'indicator')} />
        <DraftLine label="Action" value={textValue(action.draft, 'action')} />
        <DraftLine label="Reason" value={textValue(action.draft, 'reason')} />
      </dl>
      <div className="mt-3 flex flex-wrap gap-2">
        {!done ? (
          <Button
            size="sm"
            disabled={busy}
            onClick={() =>
              onRun(async () => {
                let current = action;
                if (current.state === 'APPROVAL_REQUIRED' || current.state === 'PREPARED') {
                  current = await approveEcAction(current.action_id, current);
                }
                return executeEcAction(current.action_id, action.draft ?? undefined, current);
              })
            }
          >
            Call SOAR to block
          </Button>
        ) : null}
        <Button size="sm" variant="outline" disabled={busy || !canVerify} onClick={() => onRun(() => verifyEcAction(action.action_id, action))}>
          Verify
        </Button>
      </div>
      {action.receipt ? (
        <p className={`mt-2 text-xs ${action.state === 'FAILED' ? 'text-rose-300' : 'text-emerald-300'}`}>
          {String(action.receipt.summary ?? action.receipt.status ?? 'Receipt recorded')}
        </p>
      ) : null}
      {action.verify_result ? (
        <p className="mt-2 text-xs text-cyan-300">{String(action.verify_result.summary ?? 'Verification recorded')}</p>
      ) : null}
    </article>
  );
}

function TicketDraftCard({
  action,
  busy,
  onRun,
}: {
  action: EcActionRecord;
  busy: boolean;
  onRun: (fn: () => Promise<EcActionRecord>) => void;
}) {
  const done = action.state === 'EXECUTED' || action.state === 'VERIFIED';
  const draft = action.draft ?? {};
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-100">{action.label}</h4>
        <Badge variant={done ? 'success' : 'outline'}>{action.state}</Badge>
      </div>
      <p className="mt-1 text-xs text-slate-500">Simulated ITSM draft · no live ServiceNow change</p>
      <dl className="mt-3 space-y-1 text-xs">
        {Object.entries(draft).map(([key, value]) => (
          <DraftLine key={key} label={key.replace(/_/g, ' ')} value={Array.isArray(value) ? value.join(', ') : String(value ?? '')} />
        ))}
      </dl>
      {!done ? (
        <Button
          className="mt-3"
          size="sm"
          disabled={busy}
          onClick={() =>
            onRun(async () => {
              let current = action;
              if (current.state === 'APPROVAL_REQUIRED' || current.state === 'PREPARED') {
                current = await approveEcAction(current.action_id, current);
              }
              return executeEcAction(current.action_id, undefined, current);
            })
          }
        >
          Confirm ticket
        </Button>
      ) : null}
      {action.receipt ? (
        <p className="mt-2 text-xs text-emerald-300">{String(action.receipt.summary ?? 'Ticket recorded')}</p>
      ) : null}
    </article>
  );
}

function GenericActionCard({
  action,
  busy,
  onRun,
}: {
  action: EcActionRecord;
  busy: boolean;
  onRun: (fn: () => Promise<EcActionRecord>) => void;
}) {
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-100">{action.label}</h4>
        <Badge variant={action.state === 'VERIFIED' ? 'success' : 'outline'}>{action.state}</Badge>
      </div>
      <p className="mt-1 text-xs text-slate-500">{action.kind} · no production change</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="secondary"
          disabled={busy || !['APPROVAL_REQUIRED', 'PREPARED'].includes(action.state)}
          onClick={() => onRun(() => approveEcAction(action.action_id, action))}
        >
          Approve
        </Button>
        <Button
          size="sm"
          disabled={busy || action.state !== 'APPROVED'}
          onClick={() => onRun(() => executeEcAction(action.action_id, undefined, action))}
        >
          Execute
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={busy || action.state !== 'EXECUTED'}
          onClick={() => onRun(() => verifyEcAction(action.action_id, action))}
        >
          Verify
        </Button>
      </div>
      {action.receipt ? (
        <p className="mt-2 text-xs text-emerald-300">{String(action.receipt.summary ?? 'Receipt recorded')}</p>
      ) : null}
      {action.verify_result ? (
        <p className="mt-2 text-xs text-cyan-300">{String(action.verify_result.summary ?? 'Verification recorded')}</p>
      ) : null}
    </article>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Label className="text-xs text-slate-400">{label}</Label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function DraftLine({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="whitespace-pre-wrap text-slate-200">{value}</dd>
    </div>
  );
}
