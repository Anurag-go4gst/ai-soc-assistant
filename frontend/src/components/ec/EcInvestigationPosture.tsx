import type {
  EcAgilusPatchStatus,
  EcCapabilityPlanRow,
  EcInvestigationPhase,
  EcInvestigationPhaseStep,
  EcVpnGatewayPostureRow,
} from '@/components/ec/types';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

function capabilityBadgeClass(status: string): string {
  const token = status.toUpperCase();
  if (token === 'EXECUTED') return 'border-cyan-500/40 text-cyan-100';
  if (token === 'READY') return 'border-amber-500/40 text-amber-100';
  if (token === 'AWAITING_CALLBACK') return 'border-violet-500/40 text-violet-100';
  if (token === 'NOT_AVAILABLE') return 'border-slate-600 text-slate-400';
  return 'border-slate-600 text-slate-300';
}

function phaseStepBadgeClass(status: string): string {
  const token = status.toUpperCase();
  if (token === 'DONE') return 'border-cyan-500/40 text-cyan-100';
  if (token === 'NEXT' || token === 'READY') return 'border-amber-500/40 text-amber-100';
  if (token === 'OPTIONAL') return 'border-slate-600 text-slate-400';
  if (token === 'PLANNED') return 'border-slate-500/50 text-slate-300';
  if (token === 'AWAITING_CALLBACK') return 'border-violet-500/40 text-violet-100';
  return 'border-slate-600 text-slate-300';
}

function connectorLabel(step: EcInvestigationPhaseStep): string {
  if (step.connector_available === false) {
    return step.fallback_label || 'Open ticket / email';
  }
  if (step.connector_mode === 'RAG') return 'RAG · SOC-KB';
  if (step.connector_mode === 'MCP') return 'MCP connected';
  return step.connector_mode || 'Manual';
}

function PhaseStepCard({
  step,
  onAction,
  actionBusy = false,
}: {
  step: EcInvestigationPhaseStep;
  onAction?: (followUpId: string) => void;
  actionBusy?: boolean;
}) {
  const canAct = Boolean(step.follow_up_id && step.action_label && !step.executed && step.status !== 'OPTIONAL');
  return (
    <li className="rounded-lg border border-slate-800/80 bg-slate-900/40 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-slate-100">{step.title}</span>
            <Badge variant="outline" className={phaseStepBadgeClass(step.status)}>
              {step.status}
            </Badge>
            {step.hil_action ? (
              <Badge variant="outline" className="border-rose-500/35 text-rose-100">
                HIL
              </Badge>
            ) : null}
            <Badge variant="outline" className="border-slate-600 text-slate-400">
              {connectorLabel(step)}
            </Badge>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{step.plan_summary}</p>
          {step.connector_available === false ? (
            <p className="mt-1 text-xs text-amber-200/80">Fallback: {step.fallback_label}</p>
          ) : null}
        </div>
        {canAct && onAction && step.follow_up_id ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="shrink-0 border-cyan-500/40 text-cyan-100 hover:bg-cyan-950/40"
            disabled={actionBusy}
            onClick={() => onAction(step.follow_up_id!)}
          >
            {step.action_label}
          </Button>
        ) : null}
      </div>
      {step.executed && step.detail ? (
        <p className="mt-3 text-sm leading-relaxed text-cyan-50/95">{step.detail}</p>
      ) : null}
      {step.executed && step.bullets?.length ? (
        <ul className="mt-2 space-y-1 text-sm text-slate-400">
          {step.bullets.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="text-cyan-500/80" aria-hidden="true">
                ·
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {step.executed && step.spl_preview ? (
        <pre className="mt-3 overflow-x-auto rounded-md border border-slate-700/80 bg-slate-950/80 p-3 font-mono text-xs leading-relaxed text-cyan-100/90">
          {step.spl_preview}
        </pre>
      ) : null}
    </li>
  );
}

export function EcInvestigationPhasesPanel({
  phases,
  onStepAction,
  actionBusy = false,
}: {
  phases: EcInvestigationPhase[];
  onStepAction?: (followUpId: string) => void;
  actionBusy?: boolean;
}) {
  if (!phases.length) return null;
  return (
    <section data-ec-section="investigation-phases" className="space-y-6">
      <div>
        <EcSectionHeading>Investigation plan</EcSectionHeading>
        <p className="mt-2 text-sm text-slate-400">
          Select a step and click Action — AI SOC executes via Splunk/MCP where connected, otherwise ITSM or email.
        </p>
      </div>
      {phases.map((phase) => (
        <div key={phase.phase} className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-cyan-100">
            {phase.phase}. {phase.title}
          </h3>
          <ul className="space-y-2">
            {phase.steps.map((step) => (
              <PhaseStepCard
                key={step.id}
                step={step}
                onAction={onStepAction}
                actionBusy={actionBusy}
              />
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

export function EcOpeningBriefingPanel({ text }: { text: string }) {
  if (!text.trim()) return null;
  return (
    <section data-ec-section="opening-briefing" className="rounded-lg border border-slate-700/80 bg-slate-900/35 p-4">
      <p className="text-base leading-relaxed text-slate-100">{text}</p>
    </section>
  );
}

export function EcExecutiveSummaryPanel({ bullets }: { bullets: string[] }) {
  if (!bullets.length) return null;
  return (
    <section data-ec-section="executive-summary" className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-4">
      <EcSectionHeading>Executive summary</EcSectionHeading>
      <p className="mt-2 text-xs text-slate-400">Generated after plan steps run — reflects confirmed connector outcomes.</p>
      <ul className="mt-3 space-y-2 text-sm leading-relaxed text-slate-100">
        {bullets.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" aria-hidden="true" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function EcVpnGatewayPosturePanel({ rows }: { rows: EcVpnGatewayPostureRow[] }) {
  if (!rows.length) return null;
  const totalSessions = rows.reduce((sum, row) => sum + (row.active_sessions ?? 0), 0);
  return (
    <section data-ec-section="vpn-gateway-posture">
      <EcSectionHeading>VPN gateway posture</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-400">
        Connected via CMDB and device MCP — {rows.length} internet-facing gateways · {totalSessions} active VPN sessions
        (fixture telemetry).
      </p>
      <div className="mt-3 overflow-x-auto rounded-lg border border-slate-700/80">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="border-b border-cyan-500/25 bg-gradient-to-r from-cyan-950/70 to-slate-900/50">
              <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-cyan-100">Gateway</th>
              <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-cyan-100">Site</th>
              <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-cyan-100">Version</th>
              <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-cyan-100">Health</th>
              <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-cyan-100">Sessions</th>
              <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-cyan-100">Exposure</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/90">
            {rows.map((row) => (
              <tr key={row.gateway} className="align-top hover:bg-slate-900/35">
                <td className="px-3 py-2 font-medium text-slate-50">{row.gateway}</td>
                <td className="px-3 py-2 text-slate-300">{row.site}</td>
                <td className="px-3 py-2 font-mono text-slate-200">{row.version}</td>
                <td className="px-3 py-2 text-slate-200">{row.health}</td>
                <td className="px-3 py-2 text-slate-200">{row.active_sessions ?? '—'}</td>
                <td className="px-3 py-2">
                  <Badge variant="outline" className={row.affected ? 'border-amber-500/40 text-amber-100' : 'border-emerald-500/35 text-emerald-100'}>
                    {row.affected ? 'Vulnerable' : 'Not affected'}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function EcCapabilityPlanPanel({ rows }: { rows: EcCapabilityPlanRow[] }) {
  if (!rows.length) return null;
  return (
    <section data-ec-section="capability-plan">
      <EcSectionHeading>Connected capabilities — what we can do</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-400">
        Governed connectors already used or ready on this investigation. Items marked READY run on your approval.
      </p>
      <ul className="mt-3 space-y-2">
        {rows.map((row) => (
          <li
            key={`${row.integration}-${row.status}-${row.detail.slice(0, 24)}`}
            className="rounded-lg border border-slate-800/80 bg-slate-900/40 px-3 py-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-slate-100">{row.integration}</span>
              <Badge variant="outline" className={capabilityBadgeClass(row.status)}>
                {row.status}
              </Badge>
            </div>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-300">{row.detail}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function agilusStatusLabel(status: EcAgilusPatchStatus['status']): string {
  if (status === 'ANALYZED') return 'Patch identified';
  if (status === 'READY_TO_SUBMIT') return 'Ready to submit';
  if (status === 'AWAITING_CALLBACK') return 'Awaiting Agilus';
  return 'Applied';
}

export function EcAgilusPatchPanel({ patch }: { patch: EcAgilusPatchStatus }) {
  return (
    <section data-ec-section="agilus-patch" className="rounded-lg border border-violet-500/25 bg-violet-950/20 p-4">
      <EcSectionHeading>Agilus patch orchestration</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-400">
        Standalone patch product connected via MCP — checks vendor assets against version history, identifies applicable
        patches, and applies them after approval.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="border-violet-500/40 text-violet-100">
          {agilusStatusLabel(patch.status)}
        </Badge>
        <span className="font-mono text-xs text-slate-300">{patch.patch_id}</span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-slate-200">{patch.detail}</p>
      <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Patch</dt>
          <dd className="text-slate-100">{patch.patch_title}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Targets</dt>
          <dd className="text-slate-100">{patch.targets.join(', ')}</dd>
        </div>
        {patch.job_id ? (
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Agilus job</dt>
            <dd className="font-mono text-slate-100">{patch.job_id}</dd>
          </div>
        ) : null}
        {patch.ticket_id ? (
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Change ticket</dt>
            <dd className="font-mono text-slate-100">{patch.ticket_id}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}
