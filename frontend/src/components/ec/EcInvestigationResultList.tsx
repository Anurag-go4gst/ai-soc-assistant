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
  if (token === 'COMPLETE' || token === 'VERIFIED' || token === 'VALIDATED') {
    return 'border-emerald-500/50 bg-emerald-950/30 text-emerald-100';
  }
  if (token === 'RUNNING') return 'border-cyan-500/50 bg-cyan-950/25 text-cyan-100';
  if (token === 'SKIPPED') return 'border-slate-700 bg-slate-950/20 text-slate-500';
  if (token === 'FAILED' || token === 'BLOCKED') return 'border-rose-500/50 bg-rose-950/25 text-rose-100';
  if (token === 'QUEUED') return 'border-amber-500/45 bg-amber-950/25 text-amber-100';
  return 'border-slate-700 text-slate-400';
}

function findingColumnClass(status: string, attention: AttentionState): string {
  const token = status.toUpperCase();
  if (token === 'QUEUED') return 'text-amber-100/95';
  if (token === 'RUNNING') return 'text-cyan-100';
  if (token === 'COMPLETE' || token === 'VALIDATED') return 'text-emerald-100/95';
  if (attention === 'ATTENTION') return 'text-amber-100';
  if (attention === 'RISK') return 'text-rose-100';
  if (attention === 'INFORMATIONAL') return 'text-sky-100/90';
  return 'text-slate-100';
}

function resolveHeadline(step: EcAgentPlanStep, status: string): string {
  const finding = step.finding;
  const token = status.toUpperCase();
  const byStatus =
    token === 'VALIDATED'
      ? finding?.headlines_by_status?.COMPLETE
      : finding?.headlines_by_status?.[token as keyof NonNullable<typeof finding>['headlines_by_status']];
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

  return (
    <div className="mt-3 space-y-3 border-t border-slate-800/70 pt-3 text-sm text-slate-300">
      {finding.key_evidence?.length ? (
        <div>
          <p className="text-xs font-medium text-slate-400">Evidence</p>
          <ul className="mt-1.5 space-y-1">
            {finding.key_evidence.map((item) => (
              <li key={item} className="flex gap-2 leading-relaxed">
                <span className="text-slate-500">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
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

      {Array.isArray(details.iam_notes) && details.iam_notes.length ? (
        <div>
          <p className="text-xs font-medium text-slate-400">IAM implementation notes</p>
          <ul className="mt-1.5 space-y-1">
            {(details.iam_notes as string[]).map((item) => (
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

      {details.email_draft && typeof details.email_draft === 'object' ? (
        <div className="rounded-md border border-slate-800/80 bg-slate-950/50 p-3 text-xs">
          <p className="font-medium text-slate-300">Email draft</p>
          <p className="mt-1 text-slate-400">
            To: {String((details.email_draft as Record<string, unknown>).to ?? '—')}
          </p>
          <p className="text-slate-400">
            Subject: {String((details.email_draft as Record<string, unknown>).subject ?? '—')}
          </p>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-sans leading-relaxed text-slate-300">
            {String((details.email_draft as Record<string, unknown>).body_preview ?? '')}
          </pre>
          <p className="mt-2 text-slate-500">
            {String(
              (details.email_draft as Record<string, unknown>).send_note ??
                'Draft only — not sent until analyst approves Send.',
            )}
          </p>
        </div>
      ) : null}

      {provenance ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
          <span>{provenance}</span>
          <button type="button" className="text-cyan-400/90 hover:text-cyan-300">
            View trace ›
          </button>
        </div>
      ) : null}

      {step.added_by_agent && step.reason ? (
        <p className="text-xs text-violet-200/90">{step.reason}</p>
      ) : null}
    </div>
  );
}

function findEcActionForStep(stepId: string, actions: EcActionRecord[]): EcActionRecord | undefined {
  const matchers: Record<string, RegExp> = {
    restrict_wan: /wan|network ops|restriction/i,
    enforce_mfa: /mfa|identity|iam/i,
    notify_stakeholders: /network|soc|stakeholder|notify/i,
    create_incident: /incident/i,
    create_change: /change/i,
  };
  const pattern = matchers[stepId];
  if (!pattern) return undefined;
  return actions.find((action) => {
    if (stepId.startsWith('create_')) {
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
        <p className="px-3 pt-2 text-[11px] font-medium uppercase tracking-wide text-violet-300/90">
          ↳ Added by agent
        </p>
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
            {status === 'RUNNING' && step.summary ? (
              <p className="mt-1 text-xs text-slate-400">{step.summary}</p>
            ) : null}
            {canExpand && open && finding ? (
              <CompactFindingDetails step={step} finding={finding} anomalousAssetIds={anomalousAssetIds} />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

export function EcInvestigationSummaryStrip({
  summary,
}: {
  summary: NonNullable<EcAgentWorkflowPayload['investigation_summary']>;
}) {
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
      {summary.metrics?.length ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {summary.metrics.map((metric) => (
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
          const defaultExpanded = attention === 'ATTENTION' || attention === 'RISK';
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
