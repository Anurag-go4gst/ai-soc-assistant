import type { EcAffectedSystem } from '@/components/ec/types';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcRevealBlock } from '@/components/ec/EcAnswerReveal';

export function EcAffectedSystemsTable({ systems }: { systems: EcAffectedSystem[] }) {
  return (
    <EcRevealBlock data-ec-section="affected-systems">
      <EcSectionHeading>Affected systems</EcSectionHeading>
      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-700/80 bg-slate-950/50">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="border-b border-cyan-500/25 bg-gradient-to-r from-cyan-950/70 to-slate-900/50">
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-cyan-100">System</th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-cyan-100">Activity</th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-cyan-100 whitespace-nowrap">First Seen</th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-cyan-100 whitespace-nowrap">Last Seen</th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-cyan-100">Allowed/Denied</th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-cyan-100">Identity / auth context</th>
              <th className="px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-cyan-100">Risk Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/90">
            {systems.map((row) => (
              <tr key={row.system} className="align-top hover:bg-slate-900/35">
                <td className="px-4 py-3">
                  <div className="font-semibold text-slate-50">{row.system}</div>
                  {row.role ? <div className="mt-0.5 text-xs text-slate-400">{row.role}</div> : null}
                </td>
                <td className="px-4 py-3 text-slate-200">{row.activity}</td>
                <td className="px-4 py-3 whitespace-nowrap text-slate-300">{row.first_seen}</td>
                <td className="px-4 py-3 whitespace-nowrap text-slate-300">{row.last_seen}</td>
                <td className="px-4 py-3 text-slate-200">{row.allowed_denied}</td>
                <td className="ec-prose-wrap px-4 py-3 text-slate-200">{row.identity_auth_context ?? row.auth_correlation}</td>
                <td className="px-4 py-3 text-slate-100">{row.risk_note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EcRevealBlock>
  );
}
