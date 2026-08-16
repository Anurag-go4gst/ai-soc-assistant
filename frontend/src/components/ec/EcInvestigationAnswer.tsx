import type { ExperienceCenterResponse } from '@/components/ec/types';
import { Badge } from '@/components/ui/badge';

export function EcInvestigationAnswer({ envelope }: { envelope: ExperienceCenterResponse }) {
  const analyst = envelope.analyst ?? envelope.analyst_response ?? {};
  const title = analyst.finding_title || envelope.message;
  const summary = analyst.direct_answer_summary || analyst.one_sentence_finding || envelope.analyst_summary;
  const evidenceRows = analyst.splunk_results_table ?? [];
  const nextSteps = analyst.recommended_actions ?? [];
  const unconfirmed = (analyst.mitre_mappings ?? [])
    .map((row) => String(row.Status || row.status || ''))
    .filter((status) => /validation|unconfirmed|requires/i.test(status));

  return (
    <section className="soc-panel space-y-5 rounded-xl p-5" data-ec-layer="soc-answer">
      <header className="space-y-2">
        <p className="soc-eyebrow text-cyan-400">SOC Answer</p>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h3 className="text-lg font-semibold tracking-tight text-slate-50">{title}</h3>
          {analyst.severity_label ? <Badge>{analyst.severity_label}</Badge> : <Badge variant="outline">Severity not assigned</Badge>}
        </div>
        {summary ? <p className="text-sm leading-relaxed text-slate-300">{summary}</p> : null}
      </header>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">What we found</h4>
        <p className="mt-1 text-sm text-slate-300">{analyst.one_sentence_finding || envelope.analyst_summary || 'Fixture investigation packaged for review.'}</p>
      </div>

      {analyst.key_fields?.length ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Affected systems / fields</h4>
          <ul className="mt-2 space-y-1 text-sm text-slate-300">
            {analyst.key_fields.slice(0, 6).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {evidenceRows.length ? (
        <div className="overflow-x-auto">
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Evidence</h4>
          <table className="mt-2 min-w-full text-left text-xs text-slate-300">
            <thead className="text-slate-500">
              <tr>
                {Object.keys(evidenceRows[0] ?? {}).slice(0, 6).map((column) => (
                  <th key={column} className="pr-4 font-medium">{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {evidenceRows.slice(0, 5).map((row, index) => (
                <tr key={index} className="border-t border-slate-800">
                  {Object.keys(evidenceRows[0] ?? {}).slice(0, 6).map((column) => (
                    <td key={column} className="py-1.5 pr-4">{String(row[column] ?? '')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Unconfirmed</h4>
        <p className="mt-1 text-sm text-slate-400">
          {unconfirmed.length ? unconfirmed.join(' · ') : 'No additional unconfirmed claims beyond the governed fixture evidence.'}
        </p>
      </div>

      {nextSteps.length ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Recommended next steps</h4>
          <ol className="mt-2 list-decimal space-y-1 pl-4 text-sm text-slate-300">
            {nextSteps.slice(0, 6).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
