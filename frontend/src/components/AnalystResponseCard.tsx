import { Badge } from '@/components/ui/badge';
import type React from 'react';
import type { AnalystResponseEnvelope } from '@/types/api';

export function AnalystResponseCard({ response }: { response: AnalystResponseEnvelope }) {
  const playbookTitle = formatPlaybook(response.retrieved_playbook);
  const triageSteps = stringList(response.sop_guidance?.triage_steps);
  const validationNotes = stringList(response.sop_guidance?.validation_notes);
  const hasInvestigationTable = Boolean(response.splunk_results_table?.length);
  const hasSopSections = Boolean(response.escalation_criteria?.length || response.closure_conditions?.length);

  return (
    <div className="rounded-xl border border-cyan-500/20 bg-slate-950/70 p-4 text-sm text-slate-100 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        {response.status_badge ? <Badge variant="outline">{response.status_badge}</Badge> : null}
        {response.severity_label ? <Badge variant="warning">{response.severity_label}</Badge> : null}
        {response.review_notice ? <Badge variant="warning">Review required</Badge> : null}
      </div>

      {response.finding_title ? <h3 className="mt-3 text-base font-semibold text-slate-50">{response.finding_title}</h3> : null}
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
          <SectionTitle>What to look for</SectionTitle>
          <BulletList items={response.recommended_actions} />
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
          <SectionTitle>{hasSopSections ? 'Triage steps' : 'Per SOC-SOP-AUTH-001'}</SectionTitle>
          {hasSopSections ? <NumberedList items={triageSteps} /> : <BulletList items={validationNotes.length ? validationNotes : triageSteps} />}
        </section>
      ) : null}

      {response.foundation_sec_analysis ? (
        <section className="mt-4">
          <SectionTitle>Foundation-sec analysis</SectionTitle>
          <p className="mt-1 leading-6 text-slate-200">{response.foundation_sec_analysis}</p>
        </section>
      ) : null}

      {!response.spl_code && response.recommended_actions?.length && !hasSopSections ? (
        <section className="mt-4">
          <SectionTitle>Recommended actions</SectionTitle>
          <BulletList items={response.recommended_actions} />
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
  return <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">{children}</h4>;
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return null;
  const columns = Object.keys(rows[0]);
  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-slate-800">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-800 text-left text-xs">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              {columns.map((column) => (
                <th key={column} className="whitespace-nowrap px-3 py-2 font-semibold">{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 bg-slate-950/70">
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column} className="whitespace-nowrap px-3 py-2 text-slate-100">{String(row[column] ?? '')}</td>
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
