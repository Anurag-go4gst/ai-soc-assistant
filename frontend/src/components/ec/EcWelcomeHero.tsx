import { Activity, Bot, Sparkles } from 'lucide-react';

const STARTER_HINTS = [
  'Suspicious IP or beaconing traffic',
  'Firewall-team coordination',
  'Zero-day exposure with no playbook',
  'Conflicting OT evidence',
];

export function EcWelcomeHero() {
  return (
    <div
      className="ec-welcome-hero mx-auto flex w-full max-w-3xl flex-col items-center px-2 py-8 sm:py-12"
      data-ec-welcome="true"
    >
      <div className="w-full rounded-2xl border border-cyan-500/25 bg-gradient-to-br from-cyan-500/10 via-slate-950/40 to-fuchsia-500/10 p-6 shadow-[0_0_48px_-12px_rgba(34,211,238,0.25)] sm:p-8">
        <div className="min-w-0 space-y-3">
          <p className="soc-eyebrow text-cyan-300">Experience Center</p>
          <h2 className="flex items-center gap-3 text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-fuchsia-500 text-slate-950 shadow-lg shadow-cyan-500/20">
              <Bot className="h-5 w-5" />
            </span>
            AI Investigation Cockpit
          </h2>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          {STARTER_HINTS.map((hint) => (
            <div
              key={hint}
              className="flex items-center gap-2 rounded-lg border border-slate-700/60 bg-slate-950/50 px-3 py-2.5 text-sm text-slate-200"
            >
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-cyan-400/90" />
              <span>{hint}</span>
            </div>
          ))}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <Activity className="h-3.5 w-3.5 text-cyan-400" />
          <span>Type a question below and press Enter to start.</span>
        </div>
      </div>
    </div>
  );
}
