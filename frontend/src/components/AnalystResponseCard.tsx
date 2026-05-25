import { Badge } from '@/components/ui/badge';
import type React from 'react';
import type { AnalystResponseEnvelope } from '@/types/api';
import { cn } from '@/lib/utils';

export function AnalystResponseCard({ response }: { response: AnalystResponseEnvelope }) {
  const playbookTitle = formatPlaybook(response.retrieved_playbook);
  const triageSteps = stringList(response.sop_guidance?.triage_steps);
  const validationNotes = stringList(response.sop_guidance?.validation_notes);
  const hasInvestigationTable = Boolean(response.splunk_results_table?.length);
  const hasSopSections = Boolean(response.escalation_criteria?.length || response.closure_conditions?.length);
  const title = stripSeverityPrefix(response.finding_title);

  return (
    <div className="max-w-[1120px] rounded-xl border border-cyan-500/20 bg-slate-950/70 px-6 py-5 text-[15px] text-slate-100 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        {response.severity_label ? <SeverityBadge label={response.severity_label} /> : null}
        {response.review_notice ? <Badge variant="warning">Review required</Badge> : null}
      </div>

      {title ? <h3 className="mt-3 text-xl font-semibold text-slate-50">{title}</h3> : null}
      {response.one_sentence_finding ? <p className="mt-2 leading-6 text-slate-200">{response.one_sentence_finding}</p> : null}

      {response.splunk_status_line ? <p className="mt-4 font-mono text-xs text-cyan-100">{response.splunk_status_line}</p> : null}
      {hasInvestigationTable ? <DataTable rows={response.splunk_results_table ?? []} /> : null}

      {response.spl_code ? (
        <section className="mt-4">
          <SectionTitle>What the SPL detects</SectionTitle>
          <p className="mt-1 leading-6 text-slate-200">{response.one_sentence_finding}</p>
          <pre className="mt-3 max-h-80 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs leading-5 text-cyan-100">
            <code>{response.spl_code}</code>
          </pre>
        </section>
      ) : null}

      {response.key_fields?.length ? (
        <section className="mt-4">
          <SectionTitle>Key returned fields</SectionTitle>
          <BulletList items={response.key_fields} />
        </section>
      ) : null}

      {response.spl_code && response.recommended_actions?.length ? (
        <section className="mt-4">
          <SectionTitle>{hasPriorityActions(response.recommended_actions) ? 'Recommended actions' : 'What to look for'}</SectionTitle>
          {hasPriorityActions(response.recommended_actions) ? <RecommendationList items={response.recommended_actions} /> : <BulletList items={response.recommended_actions} />}
        </section>
      ) : null}

      {response.mitre_mappings?.length ? (
        <section className="mt-4">
          <SectionTitle>MITRE ATT&amp;CK</SectionTitle>
          <DataTable rows={response.mitre_mappings} />
        </section>
      ) : null}

      {playbookTitle ? (
        <section className="mt-4">
          <SectionTitle>{hasSopSections ? 'Playbook' : 'Retrieved playbook'}</SectionTitle>
          <p className="mt-1 font-medium text-cyan-100">{playbookTitle}</p>
          {typeof response.retrieved_playbook?.purpose === 'string' ? (
            <div className="mt-3">
              <SectionTitle>Purpose</SectionTitle>
              <p className="mt-1 leading-6 text-slate-200">{response.retrieved_playbook.purpose}</p>
            </div>
          ) : null}
        </section>
      ) : null}

      {triageSteps.length ? (
        <section className="mt-4">
          <SectionTitle>{hasSopSections ? 'Triage steps' : `Per ${playbookId(response.retrieved_playbook) ?? 'retrieved playbook'}`}</SectionTitle>
          {hasSopSections ? <NumberedList items={triageSteps} /> : <BulletList items={validationNotes.length ? validationNotes : triageSteps} />}
        </section>
      ) : null}

      {response.foundation_sec_analysis ? (
        <section className="mt-4">
          <SectionTitle>Foundation-sec analysis</SectionTitle>
          <div className="mt-1 space-y-3 leading-6 text-slate-200">
            {splitParagraphs(response.foundation_sec_analysis).map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>
      ) : null}

      {!response.spl_code && response.recommended_actions?.length && !hasSopSections ? (
        <section className="mt-4">
          <SectionTitle>Recommended actions</SectionTitle>
          <RecommendationList items={response.recommended_actions} />
        </section>
      ) : null}

      {response.escalation_criteria?.length ? (
        <section className="mt-4">
          <SectionTitle>Escalation criteria</SectionTitle>
          <BulletList items={response.escalation_criteria} />
        </section>
      ) : null}

      {response.closure_conditions?.length ? (
        <section className="mt-4">
          <SectionTitle>Closure conditions</SectionTitle>
          <BulletList items={response.closure_conditions} />
        </section>
      ) : null}

      {response.review_notice ? <p className="mt-4 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">{response.review_notice}</p> : null}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h4 className="text-xs font-medium uppercase tracking-[0.05em] text-slate-400">{children}</h4>;
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return null;
  const columns = Object.keys(rows[0]);
  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-slate-800">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-800 text-left text-[13px]">
          <thead className="bg-slate-900/80 text-slate-400">
            <tr>
              {columns.map((column) => (
                <th key={column} className={cn('whitespace-nowrap px-3 py-2 font-medium', isNumericColumn(column) && 'text-right')}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-950/70">
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column} className={cn('whitespace-nowrap px-3 py-2 text-slate-100', isNumericValue(row[column]) && 'text-right font-medium')}>{String(row[column] ?? '')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="mt-2 space-y-1.5 text-slate-200">
      {items.map((item) => <li key={item}>- {item}</li>)}
    </ul>
  );
}

function RecommendationList({ items }: { items: string[] }) {
  return (
    <div className="mt-3 space-y-2">
      {items.map((item) => {
        const priority = item.match(/^(P[1-4])\s*[—-]\s*/)?.[1] ?? 'P3';
        const text = item.replace(/^(P[1-4])\s*[—-]\s*/, '');
        return (
          <div key={item} className={cn('rounded-lg border py-3 pl-4 pr-3 leading-6', recommendationTone(priority))}>
            <span className="mr-2 text-xs font-bold uppercase tracking-[0.05em]">{priority}</span>
            <span className="text-slate-100">{text}</span>
          </div>
        );
      })}
    </div>
  );
}

function SeverityBadge({ label }: { label: string }) {
  const className = label.startsWith('P1')
    ? 'border-red-400/40 bg-red-500/15 text-red-100'
    : label.startsWith('P2')
      ? 'border-amber-400/40 bg-amber-500/15 text-amber-100'
      : label.startsWith('P3')
        ? 'border-blue-400/40 bg-blue-500/15 text-blue-100'
        : 'border-slate-500/40 bg-slate-500/15 text-slate-200';
  return <span className={cn('inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold', className)}>{label}</span>;
}

function recommendationTone(priority: string) {
  if (priority === 'P1') return 'border-l-4 border-red-400/70 bg-red-500/10 text-red-100';
  if (priority === 'P2') return 'border-l-4 border-amber-400/70 bg-amber-500/10 text-amber-100';
  if (priority === 'P4') return 'border-l-4 border-slate-500/70 bg-slate-500/10 text-slate-200';
  return 'border-l-4 border-blue-400/70 bg-blue-500/10 text-blue-100';
}

function splitParagraphs(value: string) {
  return value.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
}

function stripSeverityPrefix(value?: string | null) {
  return value?.replace(/^P[1-4]\s+(Critical|High|Medium|Low)\s*[-—]\s*/i, '') ?? null;
}

function isNumericColumn(column: string) {
  return /count|logins|users|failures|success|total/i.test(column);
}

function isNumericValue(value: unknown) {
  return typeof value === 'number';
}

function hasPriorityActions(items: string[]) {
  return items.some((item) => /^P[1-4]\s*[—-]\s*/.test(item));
}

function NumberedList({ items }: { items: string[] }) {
  return (
    <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-slate-200">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ol>
  );
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function formatPlaybook(playbook?: Record<string, unknown> | null): string | null {
  if (!playbook) return null;
  const title = typeof playbook.title === 'string' ? playbook.title : null;
  const id = typeof playbook.id === 'string' ? playbook.id : null;
  const version = typeof playbook.version === 'string' ? playbook.version : null;
  return [title, id, version].filter(Boolean).join(' - ') || null;
}

function playbookId(playbook?: Record<string, unknown> | null): string | null {
  return typeof playbook?.id === 'string' ? playbook.id : null;
}
