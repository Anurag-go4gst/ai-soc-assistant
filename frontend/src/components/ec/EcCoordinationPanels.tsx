import type { ExperienceCenterResponse } from '@/components/ec/types';

export function EcCoordinationPanels({ envelope }: { envelope: ExperienceCenterResponse }) {
  const email = envelope.ec_email;
  if (!email?.inbound) return null;
  return (
    <article className="soc-panel rounded-xl p-4" data-ec-section="coordination-inbound">
      <p className="soc-eyebrow text-cyan-400">Inbound team reply</p>
      <h4 className="mt-1 text-sm font-semibold text-slate-100">{email.subject ?? 'Team response'}</h4>
      <p className="mt-3 text-sm leading-relaxed text-slate-200">{email.inbound}</p>
      <p className="mt-2 text-xs text-slate-400">Inbound fixture-backed evidence — full action journey is above.</p>
    </article>
  );
}
