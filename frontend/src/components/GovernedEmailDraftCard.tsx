import { Mail, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { GovernedEmailDraft } from '@/types/api';

export function GovernedEmailDraftCard({ draft }: { draft: GovernedEmailDraft }) {
  return (
    <section
      aria-label="Governed email draft"
      className="w-full min-w-0 max-w-[72ch] rounded-xl border border-cyan-400/30 bg-cyan-500/[0.07] p-4 text-sm text-slate-100 shadow-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Mail className="h-4 w-4 text-cyan-300" />
        <h3 className="font-semibold text-cyan-100">Email draft</h3>
        <Badge variant="secondary">Draft only</Badge>
      </div>
      <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-500/[0.07] px-3 py-2 text-xs text-amber-100">
        <div className="flex items-center gap-2 font-semibold">
          <ShieldCheck className="h-3.5 w-3.5" />
          Recipients unresolved · not approved or sent
        </div>
        <p className="mt-1">
          Recipient roles: {draft.recipient_roles.length
            ? draft.recipient_roles.map(humanize).join(', ')
            : 'needs analyst clarification'}
        </p>
      </div>
      <dl className="mt-3 space-y-3">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">Subject</dt>
          <dd className="mt-1 text-slate-100">{draft.subject}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">Body</dt>
          <dd className="mt-1 whitespace-pre-wrap rounded-lg border border-slate-800 bg-slate-950/60 p-3 leading-6 text-slate-200">
            {draft.body}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-slate-400">
        Evidence-bound deterministic draft · no live model call · no send authority
      </p>
    </section>
  );
}

function humanize(value: string): string {
  return value.replace(/_/g, ' ').trim();
}
