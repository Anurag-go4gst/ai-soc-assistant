import type { EcAffectedSystem, ExperienceCenterResponse } from '@/components/ec/types';
import { Badge } from '@/components/ui/badge';

function systemsFrom(envelope: ExperienceCenterResponse): EcAffectedSystem[] {
  const analyst = envelope.analyst ?? envelope.analyst_response ?? {};
  if (envelope.ec_affected_systems?.length) return envelope.ec_affected_systems;
  if (analyst.affected_systems?.length) return analyst.affected_systems;
  return [];
}

export function EcInvestigationAnswer({ envelope }: { envelope: ExperienceCenterResponse }) {
  const analyst = envelope.analyst ?? envelope.analyst_response ?? {};
  const title = analyst.finding_title || envelope.message;
  const assessment = analyst.assessment || analyst.direct_answer_summary || envelope.analyst_summary;
  const found = analyst.what_we_found || analyst.one_sentence_finding || envelope.analyst_summary;
  const systems = systemsFrom(envelope);
  const important = analyst.important_evidence ?? [];
  const unconfirmed = analyst.unconfirmed_findings?.length
    ? analyst.unconfirmed_findings
    : envelope.ec_investigation_outcome?.unconfirmed ?? [];
  const nextSteps = analyst.recommended_actions ?? [];
  const tableRows = systems.length
    ? []
    : (analyst.splunk_results_table ?? []);

  return (
    <section className="soc-panel space-y-5 rounded-xl p-5" data-ec-layer="soc-answer">
      <header className="space-y-2">
        <p className="soc-eyebrow text-cyan-400">SOC Answer</p>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h3 className="text-lg font-semibold tracking-tight text-slate-50">{title}</h3>
          {analyst.severity_label ? <Badge>{analyst.severity_label}</Badge> : <Badge variant="outline">Severity not assigned</Badge>}
        </div>
      </header>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Assessment</h4>
        <p className="mt-1 text-sm leading-relaxed text-slate-200">{assessment}</p>
      </div>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">What we found</h4>
        <p className="mt-1 text-sm text-slate-300">{found}</p>
      </div>

      {systems.length ? (
        <div className="overflow-x-auto" data-ec-section="affected-systems">
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Affected systems</h4>
          <table className="mt-2 min-w-full text-left text-xs text-slate-300">
            <thead className="text-slate-500">
              <tr>
                <th className="pr-4 font-medium">System</th>
                <th className="pr-4 font-medium">Activity</th>
                <th className="pr-4 font-medium">First Seen</th>
                <th className="pr-4 font-medium">Last Seen</th>
                <th className="pr-4 font-medium">Allowed/Denied</th>
                <th className="pr-4 font-medium">Auth Correlation</th>
                <th className="font-medium">Risk Note</th>
              </tr>
            </thead>
            <tbody>
              {systems.map((row) => (
                <tr key={row.system} className="border-t border-slate-800 align-top">
                  <td className="py-2 pr-4">
                    <div className="font-medium text-slate-100">{row.system}</div>
                    {row.role ? <div className="text-slate-500">{row.role}</div> : null}
                  </td>
                  <td className="py-2 pr-4">{row.activity}</td>
                  <td className="py-2 pr-4 whitespace-nowrap">{row.first_seen}</td>
                  <td className="py-2 pr-4 whitespace-nowrap">{row.last_seen}</td>
                  <td className="py-2 pr-4">{row.allowed_denied}</td>
                  <td className="py-2 pr-4">{row.auth_correlation}</td>
                  <td className="py-2">{row.risk_note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : tableRows.length ? (
        <div className="overflow-x-auto">
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Affected systems</h4>
          <table className="mt-2 min-w-full text-left text-xs text-slate-300">
            <thead className="text-slate-500">
              <tr>
                {Object.keys(tableRows[0] ?? {}).slice(0, 7).map((column) => (
                  <th key={column} className="pr-4 font-medium">{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(0, 8).map((row, index) => (
                <tr key={index} className="border-t border-slate-800">
                  {Object.keys(tableRows[0] ?? {}).slice(0, 7).map((column) => (
                    <td key={column} className="py-1.5 pr-4">{String(row[column] ?? '')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {important.length ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Important evidence</h4>
          <ul className="mt-2 space-y-1 text-sm text-slate-300">
            {important.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div data-ec-section="unconfirmed">
        <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-400/80">What remains unconfirmed</h4>
        <ul className="mt-2 space-y-1 text-sm text-amber-100/90">
          {unconfirmed.length ? unconfirmed.map((item) => <li key={item}>{item}</li>) : (
            <li>No additional unconfirmed claims beyond the governed fixture evidence.</li>
          )}
        </ul>
      </div>

      {nextSteps.length ? (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Recommended next steps</h4>
          <ol className="mt-2 list-decimal space-y-1 pl-4 text-sm text-slate-300">
            {nextSteps.slice(0, 8).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
