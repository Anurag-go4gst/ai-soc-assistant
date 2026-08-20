import { useCallback, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Info,
  Loader2,
  MinusCircle,
} from 'lucide-react';
import type { EcActionRecord, EcAgentPlanStep, EcAgentStepFinding, EcAgentWorkflowPayload } from '@/components/ec/types';
import {
  EcEmailArtifactButton,
  EcTicketArtifactButton,
  readTicketDetail,
  resolveEmailDraft,
  stepHasEmailArtifact,
  stepHasTicketArtifact,
} from '@/components/ec/EcRemediationArtifactDialog';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { EcSplCodeBlock } from '@/components/ec/EcSplCodeBlock';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

type AttentionState = 'NORMAL' | 'ATTENTION' | 'RISK' | 'NO_MATCH' | 'INFORMATIONAL';

function displayStatus(step: EcAgentPlanStep): string {
  return step.status && step.status !== 'QUEUED' ? step.status : 'QUEUED';
}

function attentionFromFinding(finding?: EcAgentStepFinding | null): AttentionState {
  const raw = (finding as EcAgentStepFinding & { attention_state?: string })?.attention_state;
  if (raw && ['NORMAL', 'ATTENTION', 'RISK', 'NO_MATCH', 'INFORMATIONAL'].includes(raw)) {
    return raw as AttentionState;
  }
  return 'NORMAL';
}

function executionBadgeClass(status: string): string {
  const token = status.toUpperCase();
  if (
    ['COMPLETE', 'VERIFIED', 'VALIDATED', 'CREATED', 'SENT', 'DEPLOYED', 'EXECUTED', 'ACTIVE', 'APPLIED'].includes(token)
  ) {
    return 'border-emerald-500/50 bg-emerald-950/30 text-emerald-100';
  }
  if (token === 'RUNNING') return 'border-cyan-500/50 bg-cyan-950/25 text-cyan-100';
  if (token === 'SKIPPED' || token === 'NOT_REQUIRED') return 'border-slate-700 bg-slate-950/20 text-slate-400';
  if (token === 'FAILED' || token === 'BLOCKED') return 'border-rose-500/50 bg-rose-950/25 text-rose-100';
  if (token === 'QUEUED') return 'border-amber-500/45 bg-amber-950/25 text-amber-100';
  return 'border-slate-700 text-slate-400';
}

function findingColumnClass(status: string, attention: AttentionState): string {
  const token = status.toUpperCase();
  if (token === 'QUEUED') return 'text-amber-100/95';
  if (token === 'RUNNING') return 'text-cyan-100';
  if (token === 'COMPLETE' || token === 'VALIDATED' || token === 'ACTIVE' || token === 'CREATED' || token === 'SENT' || token === 'DEPLOYED' || token === 'EXECUTED' || token === 'APPLIED' || token === 'VERIFIED') return 'text-emerald-100/95';
  if (attention === 'ATTENTION') return 'text-amber-100';
  if (attention === 'RISK') return 'text-rose-100';
  if (attention === 'INFORMATIONAL') return 'text-sky-100/90';
  return 'text-slate-100';
}

function resolveHeadline(step: EcAgentPlanStep, status: string): string {
  const finding = step.finding;
  const token = status.toUpperCase();
  const byStatus = finding?.headlines_by_status?.[token];
  if (byStatus) return byStatus;
  if (finding?.headline_finding) return finding.headline_finding;
  if (step.result) return step.result;
  if (status === 'SKIPPED') return 'Skipped';
  if (status === 'RUNNING') return 'Searching…';
  return '—';
}

function attentionTone(state: AttentionState): { className: string; icon: React.ReactNode } {
  switch (state) {
    case 'ATTENTION':
      return {
        className: 'text-amber-100',
        icon: <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden="true" />,
      };
    case 'RISK':
      return {
        className: 'text-rose-100',
        icon: <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-rose-400" aria-hidden="true" />,
      };
    case 'NO_MATCH':
      return {
        className: 'text-slate-100',
        icon: <MinusCircle className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />,
      };
    case 'INFORMATIONAL':
      return {
        className: 'text-slate-200',
        icon: <Info className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />,
      };
    default:
      return {
        className: 'text-slate-100',
        icon: <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400/90" aria-hidden="true" />,
      };
  }
}

function formatMetricLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function compactMetrics(finding: EcAgentStepFinding): Array<{ label: string; value: string }> {
  const quantitative = finding.quantitative_summary ?? {};
  const preferredOrder = [
    'internet_facing_total',
    'in_advisory_scope',
    'version_probes',
    'affected_firmware',
    'not_affected',
    'ioc_hits',
    'known_ioc_matches',
    'anomalous_gateways',
    'privileged_auth_events',
    'search_window_days',
    'advisory_specific_detections',
    'reusable_analytics',
    'vpn_zero_day_playbooks',
    'related_emergency_runbooks',
    'ir_procedures',
    'temporary_controls',
    'vendor_assets_checked',
    'outdated_builds',
  ];
  const entries: Array<{ label: string; value: string }> = [];
  for (const key of preferredOrder) {
    const value = quantitative[key];
    if (value !== undefined && value !== '') {
      entries.push({ label: formatMetricLabel(key), value: String(value) });
    }
  }
  for (const [key, value] of Object.entries(quantitative)) {
    if (preferredOrder.includes(key) || value === undefined || value === '') continue;
    entries.push({ label: formatMetricLabel(key), value: String(value) });
  }
  return entries.slice(0, 6);
}

function provenanceLabel(finding: EcAgentStepFinding): string | null {
  const src = finding.evidence_sources?.[0];
  if (!src) return null;
  const provenance = src.provenance?.replace(/_/g, ' ').toUpperCase() ?? 'SIMULATED';
  return `${src.source} · ${provenance}`;
}

function EntityChips({
  entities,
  anomalousIds = [],
}: {
  entities: string[];
  anomalousIds?: string[];
}) {
  if (!entities.length) return null;
  const anomalous = new Set(anomalousIds);
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {entities.map((entity) => (
        <span
          key={entity}
          className={cn(
            'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs',
            anomalous.has(entity)
              ? 'border-amber-500/35 bg-amber-950/25 text-amber-50'
              : 'border-slate-700/80 bg-slate-900/50 text-slate-200',
          )}
        >
          {anomalous.has(entity) ? (
            <AlertTriangle className="h-3 w-3 text-amber-400" aria-hidden="true" />
          ) : null}
          {entity}
        </span>
      ))}
    </div>
  );
}

function CompactFindingDetails({
  step,
  finding,
  anomalousAssetIds,
}: {
  step: EcAgentPlanStep;
  finding: EcAgentStepFinding;
  anomalousAssetIds: string[];
}) {
  const metrics = compactMetrics(finding);
  const provenance = provenanceLabel(finding);
  const details = finding.details ?? {};
  const [traceOpen, setTraceOpen] = useState(false);
  const [splOpen, setSplOpen] = useState(false);
  const [ioOpen, setIoOpen] = useState(false);
  const reasoning = details.reasoning && typeof details.reasoning === 'object'
    ? (details.reasoning as Record<string, unknown>)
    : null;
  const keyEvidence = (finding.key_evidence ?? []).filter((item) => item.trim());
  const normalizedSpl = typeof details.normalized_spl === 'string' ? details.normalized_spl.trim() : '';
  const relatedSpl =
    details.related_spl && typeof details.related_spl === 'object'
      ? (details.related_spl as Record<string, unknown>)
      : null;
  const requestText = typeof details.request === 'string' ? details.request.trim() : '';
  const responseText = typeof details.response === 'string' ? details.response.trim() : '';
  const nextSteps = typeof details.next_steps === 'string' ? details.next_steps.trim() : '';
  const executionLine = typeof details.execution === 'string' ? details.execution.trim() : '';
  const connector = typeof details.connector === 'string' ? details.connector : null;
  const emailDraft = details.email_draft && typeof details.email_draft === 'object'
    ? (details.email_draft as Record<string, unknown>)
    : null;
  const notification = details.notification && typeof details.notification === 'object'
    ? (details.notification as Record<string, unknown>)
    : null;
  const emailSent = String(emailDraft?.status ?? '') === 'sent';

  return (
    <div className="mt-3 space-y-3 border-t border-slate-800/70 pt-3 text-sm text-slate-300">
      {keyEvidence.length ? (
        <div>
          <p className="text-xs font-medium text-slate-400">Evidence</p>
          <ul className="mt-1.5 space-y-1">
            {keyEvidence.map((item) => (
              <li key={item} className="flex gap-2 leading-relaxed">
                <span className="text-slate-500">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {executionLine ? (
        <p className="text-xs text-slate-400">
          Execution <span className="text-slate-200">{executionLine}</span>
          {connector ? <span className="text-slate-500"> · {connector}</span> : null}
        </p>
      ) : null}

      {normalizedSpl || relatedSpl ? (
        <div>
          <button
            type="button"
            className="text-xs text-cyan-400/90 hover:text-cyan-300"
            onClick={(event) => {
              event.stopPropagation();
              setSplOpen((current) => !current);
            }}
          >
            {splOpen ? 'Hide SPL' : 'View SPL ›'}
          </button>
          {splOpen ? (
            <div className="mt-2 space-y-3">
              {normalizedSpl ? <EcSplCodeBlock spl={normalizedSpl} label="Normalized SPL" maxHeightClass="max-h-48" /> : null}
              {relatedSpl
                ? Object.entries(relatedSpl).map(([label, spl]) =>
                    typeof spl === 'string' && spl.trim() ? (
                      <EcSplCodeBlock key={label} spl={spl} label={label.replace(/_/g, ' ')} maxHeightClass="max-h-40" />
                    ) : null,
                  )
                : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {requestText || responseText ? (
        <div>
          <button
            type="button"
            className="text-xs text-cyan-400/90 hover:text-cyan-300"
            onClick={(event) => {
              event.stopPropagation();
              setIoOpen((current) => !current);
            }}
          >
            {ioOpen ? 'Hide request / response' : 'View request / response ›'}
          </button>
          {ioOpen ? (
            <div className="mt-2 grid gap-3 rounded-md border border-slate-800/80 bg-slate-950/50 p-3 text-xs sm:grid-cols-2">
              {requestText ? (
                <div>
                  <p className="font-medium uppercase tracking-wide text-slate-500">Request</p>
                  <pre className="mt-1 whitespace-pre-wrap font-mono text-slate-200">{requestText}</pre>
                </div>
              ) : null}
              {responseText ? (
                <div>
                  <p className="font-medium uppercase tracking-wide text-slate-500">Response</p>
                  <pre className="mt-1 whitespace-pre-wrap font-mono text-slate-200">{responseText}</pre>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {nextSteps ? (
        <p className="text-xs leading-relaxed text-cyan-100/90">{nextSteps}</p>
      ) : null}

      {Array.isArray(details.sessions) && details.sessions.length ? (
        <div className="overflow-x-auto rounded-md border border-slate-800/80">
          <table className="min-w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/60 text-slate-500">
              <tr>
                {['dest', 'dest_port', 'service', 'action', 'count', 'first_seen', 'last_seen'].map((col) => (
                  <th key={col} className="px-2 py-1.5 font-medium">
                    {col.replace('_', ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(details.sessions as Array<Record<string, unknown>>).map((row, index) => (
                <tr key={`${String(row.dest)}-${String(row.dest_port)}-${index}`} className="border-t border-slate-800/70">
                  <td className="px-2 py-1.5">{String(row.dest ?? '')}</td>
                  <td className="px-2 py-1.5">{String(row.dest_port ?? '')}</td>
                  <td className="px-2 py-1.5">{String(row.service ?? '')}</td>
                  <td className="px-2 py-1.5">{String(row.action ?? '')}</td>
                  <td className="px-2 py-1.5">{String(row.count ?? '')}</td>
                  <td className="px-2 py-1.5">{String(row.first_seen ?? '')}</td>
                  <td className="px-2 py-1.5">{String(row.last_seen ?? '')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {finding.affected_entities?.length ? (
        <EntityChips entities={finding.affected_entities} anomalousIds={anomalousAssetIds} />
      ) : null}

      {metrics.length ? (
        <div className="flex flex-wrap gap-2">
          {metrics.map((metric) => (
            <span
              key={metric.label}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-800/80 bg-slate-950/40 px-2 py-1 text-xs text-slate-200"
            >
              <span className="font-medium text-slate-50">{metric.value}</span>
              <span className="text-slate-400">{metric.label}</span>
            </span>
          ))}
        </div>
      ) : null}

      {typeof details.investigation_window === 'string' ? (
        <p className="text-xs text-slate-400">Window: {details.investigation_window}</p>
      ) : null}

      {finding.caveat ? (
        <p className="text-xs leading-relaxed text-amber-100/85">{finding.caveat}</p>
      ) : null}

      {Array.isArray(details.iam_notes) && (details.iam_notes as string[]).filter((item) => item.trim()).length ? (
        <div>
          <p className="text-xs font-medium text-slate-400">IAM implementation notes</p>
          <ul className="mt-1.5 space-y-1">
            {(details.iam_notes as string[]).filter((item) => item.trim()).map((item) => (
              <li key={item} className="flex gap-2 leading-relaxed">
                <span className="text-slate-500">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {typeof details.execution_channel === 'string' ? (
        <p className="text-xs text-slate-500">
          Execution channel: <span className="text-slate-300">{details.execution_channel.replace(/_/g, ' ')}</span>
        </p>
      ) : null}

      {emailDraft && emailSent ? (
        <div className="rounded-md border border-slate-800/80 bg-slate-950/50 p-3 text-xs">
          <p className="font-medium text-slate-300">SOC notification</p>
          <p className="mt-1 text-slate-400">To: {String(notification?.recipient ?? emailDraft.to ?? '—')}</p>
          {notification?.sent_at ? <p className="text-slate-400">Sent: {String(notification.sent_at)}</p> : null}
          <p className="text-slate-400">
            Result: {String(notification?.delivery_result ?? emailDraft.delivery_result ?? 'DELIVERED')}
          </p>
        </div>
      ) : null}

      {provenance || reasoning ? (
        <div className="space-y-2 text-xs text-slate-500">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {provenance ? <span>{provenance}</span> : <span />}
            <button
              type="button"
              className="text-cyan-400/90 hover:text-cyan-300"
              onClick={(event) => {
                event.stopPropagation();
                setTraceOpen((current) => !current);
              }}
            >
              {traceOpen ? 'Hide trace' : 'View trace ›'}
            </button>
          </div>
          {traceOpen && reasoning ? (
            <div className="rounded-md border border-slate-800/80 bg-slate-950/50 p-3 text-slate-400">
              <p className="font-medium text-slate-300">
                {String(reasoning.trace_label ?? reasoning.label ?? 'Reasoning')}
              </p>
              {typeof reasoning.summary === 'string' && reasoning.summary.trim() ? (
                <p className="mt-1 leading-relaxed">{reasoning.summary}</p>
              ) : null}
              {Array.isArray(reasoning.chain) && reasoning.chain.length ? (
                <p className="mt-2 font-mono text-[11px] text-slate-500">
                  {(reasoning.chain as unknown[]).map((item) => String(item)).join(' → ')}
                </p>
              ) : null}
              {reasoning.not_evidence ? (
                <p className="mt-2 text-[11px] uppercase tracking-wide text-slate-500">
                  LLM output is reasoning, not evidence
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function findEcActionForStep(stepId: string, actions: EcActionRecord[]): EcActionRecord | undefined {
  const matchers: Record<string, RegExp> = {
    restrict_wan: /wan|network ops|restriction/i,
    enforce_mfa: /mfa|identity|iam/i,
    notify_stakeholders: /network|soc|stakeholder|notify/i,
    notify_firewall: /firewall|security team/i,
    notify_appsec: /appsec|app security|ai platform/i,
    create_incident: /incident/i,
    create_change: /change/i,
    update_ticket: /update incident|incident ticket/i,
  };
  const pattern = matchers[stepId];
  if (!pattern) return undefined;
  return actions.find((action) => {
    if (stepId.startsWith('create_') || stepId === 'update_ticket') {
      return action.kind.startsWith('ticket') && pattern.test(action.label);
    }
    return action.kind === 'email_send' && pattern.test(action.label);
  });
}

function InvestigationResultRow({
  step,
  anomalousAssetIds,
  defaultExpanded,
  selectable = false,
  selected = true,
  onToggle,
  statusOverride,
  variant = 'investigation',
  scenarioId,
  sessionId,
  ecActions = [],
  onActionUpdate,
}: {
  step: EcAgentPlanStep;
  anomalousAssetIds: string[];
  defaultExpanded: boolean;
  selectable?: boolean;
  selected?: boolean;
  onToggle?: (checked: boolean) => void;
  statusOverride?: string;
  variant?: 'investigation' | 'remediation';
  scenarioId?: string;
  sessionId?: string | null;
  ecActions?: EcActionRecord[];
  onActionUpdate?: (action: EcActionRecord) => void;
}) {
  const status = statusOverride ?? displayStatus(step);
  const finding = step.finding;
  const attention = attentionFromFinding(finding);
  const attentionUi = attentionTone(attention);
  const hasEmailDraft = Boolean(finding?.details?.email_draft);
  const canExpand = Boolean(
    finding &&
      (status !== 'RUNNING' && (status !== 'QUEUED' || variant === 'remediation' || hasEmailDraft)),
  );
  const [open, setOpen] = useState(defaultExpanded);

  const headline = resolveHeadline(step, status);

  const resource = step.tools?.join(' · ');
  const details = (finding?.details ?? {}) as Record<string, unknown>;
  const emailDraft = details.email_draft as Record<string, unknown> | undefined;
  const emailExtra = details.email_extra as Record<string, unknown> | undefined;
  const ticketDetail = readTicketDetail(details);
  const showEmail = stepHasEmailArtifact(step);
  const showTicket = stepHasTicketArtifact(step);
  const linkedAction = findEcActionForStep(step.id, ecActions);
  const artifactsEnabled = Boolean(scenarioId);
  const resolvedEmailDraft = resolveEmailDraft(
    emailDraft as Parameters<typeof resolveEmailDraft>[0],
    emailExtra,
  );

  const findingClass = findingColumnClass(status, attention);

  const toggle = useCallback(() => {
    if (!canExpand) return;
    setOpen((current) => !current);
  }, [canExpand]);

  return (
    <div
      className={cn(
        'rounded-lg border border-slate-800/80 bg-slate-900/30',
        step.added_by_agent && 'ml-3 border-l-2 border-l-violet-500/50',
        attention === 'ATTENTION' && 'border-amber-500/20',
      )}
      data-ec-result-row={step.id}
    >
      {step.added_by_agent ? (
        <div className="space-y-1 px-3 pt-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-violet-300/90">
            ↳ ADDED BY AGENT
          </p>
          {step.reason ? (
            <p className="text-xs leading-relaxed text-violet-200/90">{step.reason}</p>
          ) : null}
        </div>
      ) : null}

      <div
        role={canExpand ? 'button' : undefined}
        tabIndex={canExpand ? 0 : undefined}
        onClick={toggle}
        onKeyDown={(event) => {
          if (!canExpand) return;
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggle();
          }
        }}
        className={cn(
          'grid gap-3 px-3 py-3 md:grid-cols-[minmax(0,42%)_minmax(0,11%)_minmax(0,1fr)] md:items-start',
          canExpand && 'cursor-pointer hover:bg-slate-900/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/40',
        )}
      >
        <div className="min-w-0">
          <div className="flex items-start gap-2">
            {selectable ? (
              <input
                type="checkbox"
                checked={selected}
                onChange={(event) => {
                  event.stopPropagation();
                  onToggle?.(event.target.checked);
                }}
                onClick={(event) => event.stopPropagation()}
                className="mt-1 h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-cyan-500"
                aria-label={`Include ${step.title}`}
              />
            ) : null}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-100">{step.title}</p>
              {resource ? <p className="mt-0.5 text-xs text-slate-500">{resource}</p> : null}
            </div>
          </div>
          {!step.added_by_agent && step.summary ? (
            <p className="mt-1 hidden text-xs text-slate-500 md:block">{step.summary}</p>
          ) : null}
        </div>

        <div className="flex flex-col items-start gap-2 md:justify-start">
          <Badge variant="outline" className={cn('text-[10px] uppercase tracking-wide', executionBadgeClass(status))}>
            {status === 'RUNNING' ? (
              <span className="inline-flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                {status}
              </span>
            ) : (
              status
            )}
          </Badge>
          {variant === 'remediation' && artifactsEnabled ? (
            <div className="flex flex-wrap gap-1.5">
              {showEmail ? (
                <EcEmailArtifactButton
                  stepTitle={step.title}
                  emailDraft={resolvedEmailDraft}
                  emailExtra={emailExtra}
                  scenarioId={scenarioId!}
                  sessionId={sessionId}
                  existingAction={linkedAction?.kind === 'email_send' ? linkedAction : undefined}
                  onActionUpdate={onActionUpdate}
                />
              ) : null}
              {showTicket && ticketDetail ? (
                <EcTicketArtifactButton
                  stepTitle={step.title}
                  ticket={ticketDetail}
                  scenarioId={scenarioId!}
                  sessionId={sessionId}
                  existingAction={linkedAction?.kind.startsWith('ticket') ? linkedAction : undefined}
                  onActionUpdate={onActionUpdate}
                />
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="flex min-w-0 items-start gap-2">
          <div className="mt-0.5 hidden md:block">
            {canExpand ? (
              open ? (
                <ChevronDown className="h-4 w-4 text-slate-400" aria-hidden="true" />
              ) : (
                <ChevronRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
              )
            ) : (
              <span className="inline-block w-4" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className={cn('text-sm leading-relaxed', findingClass)}>
              <span className="mr-1.5 inline-flex align-middle">{attentionUi.icon}</span>
              {headline}
            </p>
            {typeof details.normalized_spl === 'string' && details.normalized_spl.trim() ? (
              <p className="mt-1 text-xs text-cyan-400/80">
                {String(details.connector ?? 'Splunk MCP')} · View SPL ›
              </p>
            ) : null}
          </div>
        </div>
      </div>
      {canExpand && open && finding ? (
        <div className="px-3 pb-3">
          <CompactFindingDetails step={step} finding={finding} anomalousAssetIds={anomalousAssetIds} />
        </div>
      ) : null}
    </div>
  );
}

export function EcInvestigationSummaryStrip({
  summary,
}: {
  summary: NonNullable<EcAgentWorkflowPayload['investigation_summary']>;
}) {
  const metrics = (summary.metrics ?? []).filter(
    (metric) => metric.label?.trim() && String(metric.value ?? '').trim() && String(metric.value).trim() !== '—',
  );
  return (
    <div className="space-y-3" data-ec-section="investigation-summary">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">
          {summary.title ?? 'Investigation complete'}
        </p>
        <p className="text-sm text-slate-400">
          {summary.steps_completed ?? 0} / {summary.steps_total ?? 0} steps
        </p>
      </div>
      {metrics.length ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className="rounded-md border border-slate-800/80 bg-slate-950/35 px-3 py-2 text-center"
            >
              <p className="text-xl font-semibold tabular-nums text-slate-50">{metric.value}</p>
              <p className="mt-0.5 text-[11px] uppercase tracking-wide text-slate-400">{metric.label}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function EcInvestigationResultList({
  header = 'Investigation results',
  steps,
  anomalousAssetIds = [],
  selectable = false,
  selectedIds,
  onToggleStep,
  statusOverrides,
  variant = 'investigation',
  expandDetails = false,
  scenarioId,
  sessionId,
  ecActions,
  onActionUpdate,
}: {
  header?: string;
  steps: EcAgentPlanStep[];
  anomalousAssetIds?: string[];
  selectable?: boolean;
  selectedIds?: Set<string>;
  onToggleStep?: (id: string, checked: boolean) => void;
  statusOverrides?: Record<string, string>;
  variant?: 'investigation' | 'remediation';
  expandDetails?: boolean;
  scenarioId?: string;
  sessionId?: string | null;
  ecActions?: EcActionRecord[];
  onActionUpdate?: (action: EcActionRecord) => void;
}) {
  const active = useMemo(() => steps.filter((step) => step.selected !== false || selectable), [steps, selectable]);

  return (
    <section className="space-y-3" data-ec-section="investigation-results">
      <EcSectionHeading>{header}</EcSectionHeading>

      <div className="hidden rounded-t-lg border border-b border-slate-700/80 bg-slate-800/90 px-3 py-2.5 md:grid md:grid-cols-[minmax(0,42%)_minmax(0,11%)_minmax(0,1fr)] md:gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-100">Step</span>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-100">
          {variant === 'remediation' ? 'Status / actions' : 'Status'}
        </span>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-100">Finding</span>
      </div>

      <div className="space-y-2 md:rounded-b-lg md:border md:border-slate-800/80 md:p-2">
        {active.map((step) => {
          const attention = attentionFromFinding(step.finding);
          const defaultExpanded = expandDetails || attention === 'ATTENTION' || attention === 'RISK';
          const isSelected = selectedIds ? selectedIds.has(step.id) : step.selected !== false;
          return (
            <InvestigationResultRow
              key={step.id}
              step={step}
              anomalousAssetIds={anomalousAssetIds}
              defaultExpanded={defaultExpanded}
              selectable={selectable}
              selected={isSelected}
              onToggle={(checked) => onToggleStep?.(step.id, checked)}
              statusOverride={statusOverrides?.[step.id]}
              variant={variant}
              scenarioId={scenarioId}
              sessionId={sessionId}
              ecActions={ecActions}
              onActionUpdate={onActionUpdate}
            />
          );
        })}
      </div>
    </section>
  );
}
