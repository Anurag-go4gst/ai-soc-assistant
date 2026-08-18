import type { EcAnalystPayload } from '@/components/ec/types';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcRevealBlock } from '@/components/ec/EcAnswerReveal';
import { EcSplCodeBlock } from '@/components/ec/EcSplCodeBlock';
import { Badge } from '@/components/ui/badge';

export function EcSplArtifactPanel({ analyst }: { analyst: EcAnalystPayload }) {
  const spl = analyst.spl_code?.trim();
  if (!spl) return null;

  const detail = analyst.spl_status_detail as Record<string, string> | undefined;
  const keyFields = analyst.key_fields ?? [];
  const checklist = analyst.analyst_checklist ?? [];

  return (
    <EcRevealBlock>
      <EcSectionHeading>Candidate SPL artifact</EcSectionHeading>
      <div className="mt-3 min-w-0 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {analyst.spl_status ? <Badge variant="outline">{analyst.spl_status}</Badge> : null}
          {detail?.generation_status ? (
            <Badge variant="secondary" className="text-xs">{detail.generation_status}</Badge>
          ) : null}
          {detail?.template_status ? (
            <Badge variant="outline" className="text-xs">Template {detail.template_status}</Badge>
          ) : null}
        </div>
        {detail?.message ? <p className="ec-prose-wrap text-sm text-slate-200">{detail.message}</p> : null}
        <EcSplCodeBlock spl={spl} />
        {detail?.environment_fields_used && Array.isArray(detail.environment_fields_used) ? (
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-300">Environment fields</p>
            <ul className="mt-2 space-y-1 text-sm text-slate-200">
              {detail.environment_fields_used.map((item) => (
                <li key={String(item)} className="ec-prose-wrap font-mono text-xs">{String(item)}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {keyFields.length ? (
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-300">Key output fields</p>
            <ul className="mt-2 space-y-1.5 text-sm text-slate-200">
              {keyFields.map((item) => (
                <li key={item} className="ec-prose-wrap rounded border border-slate-800/80 bg-slate-900/50 px-3 py-2">{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {checklist.length ? (
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-300">Analyst checklist</p>
            <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-slate-200">
              {checklist.map((item) => (
                <li key={item} className="ec-prose-wrap">{item}</li>
              ))}
            </ol>
          </div>
        ) : null}
        {analyst.review_notice ? (
          <p className="ec-prose-wrap rounded-md border border-amber-500/25 bg-amber-950/25 px-3 py-2 text-sm text-amber-100/95">
            {analyst.review_notice}
          </p>
        ) : null}
      </div>
    </EcRevealBlock>
  );
}
