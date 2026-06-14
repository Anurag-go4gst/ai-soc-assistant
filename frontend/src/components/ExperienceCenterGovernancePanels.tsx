import { ChevronRight } from 'lucide-react';
import type React from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ExperienceCenterGovernance } from '@/types/api';

interface ExperienceCenterGovernancePanelsProps {
  governance: ExperienceCenterGovernance;
  demoMode?: boolean;
  /** When set, render only these panel groups (default: all except mcp, for post-evidence placement). */
  sections?: Array<'mcp' | 'severity' | 'skills' | 'completion'>;
}

export function ExperienceCenterGovernancePanels({
  governance,
  demoMode = false,
  sections,
}: ExperienceCenterGovernancePanelsProps) {
  const show = (key: 'mcp' | 'severity' | 'skills' | 'completion') =>
    !sections || sections.includes(key);

  return (
    <div className={cn(sections?.includes('mcp') ? 'mt-3 space-y-2' : 'mt-3 space-y-2 border-t border-slate-800/80 pt-3')}>
      {!sections?.includes('mcp') ? (
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-slate-500">Governance panels</p>
      ) : null}
      {!sections && governance.resource_planner ? (
        <GovernanceDetails title="Resource Planner" testId="ec-resource-planner-panel">
          <ObjectPanel panel={governance.resource_planner} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.spl_validation_panel ? (
        <GovernanceDetails title="SPL validation" testId="ec-spl-validation-panel">
          <ObjectPanel panel={governance.spl_validation_panel} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.mcp_tool_selection ? (
        <GovernanceDetails title="MCP fixture tool selection" testId="ec-mcp-tool-selection-panel">
          <ObjectPanel panel={governance.mcp_tool_selection} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.mcp_fixture_result ? (
        <GovernanceDetails title="MCP fixture search result" testId="ec-mcp-fixture-result-panel">
          <ObjectPanel panel={governance.mcp_fixture_result} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.source_evidence_panel ? (
        <GovernanceDetails title="SourceEvidence package" testId="ec-source-evidence-panel">
          <ObjectPanel panel={governance.source_evidence_panel} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.soc_kb_panel ? (
        <GovernanceDetails title="Governed SOC-KB" testId="ec-soc-kb-panel">
          <ObjectPanel panel={governance.soc_kb_panel} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.mitre_panel ? (
        <GovernanceDetails title="MITRE treatment" testId="ec-mitre-panel">
          <ObjectPanel panel={governance.mitre_panel} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.answer_contract_panel ? (
        <GovernanceDetails title="Answer contract" testId="ec-answer-contract-panel">
          <ObjectPanel panel={governance.answer_contract_panel} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.model_signal_panel ? (
        <GovernanceDetails title="Model signal" testId="ec-model-signal-panel">
          <ObjectPanel panel={governance.model_signal_panel} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.llm_sidecar_panel ? (
        <GovernanceDetails title="LLM sidecars (advisory)" testId="ec-llm-sidecar-panel">
          <ObjectPanel panel={governance.llm_sidecar_panel} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.answer_scorecard_panel ? (
        <GovernanceDetails title="Answer scorecard" testId="ec-answer-scorecard-panel">
          <ObjectPanel panel={governance.answer_scorecard_panel} />
        </GovernanceDetails>
      ) : null}
      {!sections && governance.narration_visibility_panel ? (
        <GovernanceDetails title="Narration visibility" testId="ec-narration-visibility-panel">
          <ObjectPanel panel={governance.narration_visibility_panel} />
        </GovernanceDetails>
      ) : null}
      {show('mcp') && governance.mcp_envelope?.available ? (
        <GovernanceDetails title="MCP response / envelope" testId="ec-mcp-envelope-panel">
          <EnvelopeGrid panel={governance.mcp_envelope} />
        </GovernanceDetails>
      ) : null}
      {show('severity') && governance.severity ? (
        <GovernanceDetails title={governance.severity.why_severity_title} testId="ec-severity-panel">
          <SeverityPanelContent panel={governance.severity} />
        </GovernanceDetails>
      ) : null}
      {show('skills') ? (
        <GovernanceDetails title="Skills / operations status" testId="ec-skills-panel">
          <SkillsPanelContent panel={governance.skills_operations} />
        </GovernanceDetails>
      ) : null}
      {show('completion') ? (
        <GovernanceDetails title="Skills completion status" testId="ec-completion-panel">
          <CompletionPanelContent panel={governance.completion_status} />
        </GovernanceDetails>
      ) : null}
    </div>
  );
}

function GovernanceDetails({
  title,
  testId,
  children,
}: {
  title: string;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <details className="group rounded-md border border-slate-800 bg-slate-950/50" data-testid={testId}>
      <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-300 transition hover:text-cyan-200">
        <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
        {title}
      </summary>
      <div className="border-t border-slate-800/80 px-3 py-2.5 text-xs text-slate-300">{children}</div>
    </details>
  );
}

function EnvelopeGrid({ panel }: { panel: NonNullable<ExperienceCenterGovernance['mcp_envelope']> }) {
  const rows: Array<{ label: string; value: string }> = [
    { label: 'origin', value: panel.origin ?? '—' },
    { label: 'schema_confirmed', value: String(panel.schema_confirmed) },
    { label: 'schema_confirmed_reason', value: panel.schema_confirmed_reason ?? '—' },
    { label: 'status', value: panel.status ?? '—' },
    { label: 'row_count', value: String(panel.row_count ?? '—') },
    { label: 'total_row_count', value: panel.total_row_count == null ? '—' : String(panel.total_row_count) },
    { label: 'truncated', value: String(panel.truncated) },
    { label: 'truncation_reason', value: panel.truncation_reason ?? '—' },
    { label: 'preview_rows count', value: String(panel.preview_rows_count ?? '—') },
    { label: 'provenance', value: panel.provenance ?? '—' },
    { label: 'executed_spl', value: panel.executed_spl ?? 'null' },
  ];
  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2">
        {rows.map((row) => (
          <KeyRow key={row.label} label={row.label} value={row.value} mono />
        ))}
      </div>
      {panel.fields?.length ? (
        <div>
          <p className="mb-1 font-mono text-[0.62rem] uppercase text-slate-500">fields</p>
          <div className="flex flex-wrap gap-1">
            {panel.fields.map((field) => (
              <Badge key={field} variant="outline">{field}</Badge>
            ))}
          </div>
        </div>
      ) : null}
      {panel.warnings?.length ? (
        <div>
          <p className="mb-1 font-mono text-[0.62rem] uppercase text-slate-500">warnings</p>
          <div className="flex flex-wrap gap-1">
            {panel.warnings.map((warning) => (
              <Badge key={warning} variant="warning">{warning}</Badge>
            ))}
          </div>
        </div>
      ) : null}
      <p className="text-[0.65rem] text-slate-500">
        COE synthetic rows normalized through the fixture adapter; no live MCP execution claim beyond the status line above.
      </p>
    </div>
  );
}

function SeverityPanelContent({ panel }: { panel: NonNullable<ExperienceCenterGovernance['severity']> }) {
  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1 font-medium text-slate-100">{panel.why_severity_title}</p>
        <BulletList items={panel.why_severity} />
      </div>
      <div data-testid="ec-severity-why-not-higher">
        <p className="mb-1 font-medium text-slate-100">{panel.why_not_higher_title}</p>
        <BulletList items={panel.why_not_higher} />
      </div>
      {panel.priority_note ? <p className="leading-5 text-slate-400">{panel.priority_note}</p> : null}
    </div>
  );
}

function SkillsPanelContent({ panel }: { panel: ExperienceCenterGovernance['skills_operations'] }) {
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <KeyRow label="Intent skill" value={panel.intent_skill} />
        <KeyRow label="Legacy router skill" value={panel.legacy_router_skill} />
      </div>
      <div>
        <p className="mb-1 font-mono text-[0.62rem] uppercase text-slate-500">Runtime operation</p>
        {panel.runtime_operation ? (
          <Badge variant="secondary">{panel.runtime_operation}</Badge>
        ) : (
          <p className="text-slate-400">{panel.runtime_operation_note}</p>
        )}
      </div>
      <div>
        <p className="mb-2 font-mono text-[0.62rem] uppercase text-slate-500">Pipeline stages</p>
        <div className="space-y-1">
          {panel.pipeline_stages.map((stage) => (
            <div key={stage.stage_id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-800 bg-slate-950 px-2 py-1.5">
              <span className="text-slate-200">{stage.label}</span>
              <Badge variant={stageStatusVariant(stage.status)}>{stage.status}</Badge>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CompletionPanelContent({ panel }: { panel: ExperienceCenterGovernance['completion_status'] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div>
        <p className="mb-1.5 font-medium text-emerald-200/90">Completed</p>
        <BulletList items={panel.completed} tone="success" />
      </div>
      <div>
        <p className="mb-1.5 font-medium text-amber-200/90">Gated / WIP</p>
        <BulletList items={panel.gated_wip} tone="warning" />
      </div>
    </div>
  );
}

function KeyRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950 px-2 py-1.5">
      <p className="font-mono text-[0.62rem] uppercase text-slate-500">{label}</p>
      <p className={cn('mt-0.5 break-all text-slate-100', mono && 'font-mono text-[0.7rem]')}>{value}</p>
    </div>
  );
}

function ObjectPanel({ panel }: { panel: Record<string, unknown> }) {
  return (
    <div className="space-y-2">
      {Object.entries(panel).map(([key, value]) => (
        <ValueBlock key={key} label={key} value={value} />
      ))}
    </div>
  );
}

function ValueBlock({ label, value }: { label: string; value: unknown }) {
  if (Array.isArray(value)) {
    if (value.every((item) => typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean')) {
      return (
        <div>
          <p className="mb-1 font-mono text-[0.62rem] uppercase text-slate-500">{label}</p>
          <BulletList items={value.map((item) => String(item))} />
        </div>
      );
    }
    return (
      <div>
        <p className="mb-1 font-mono text-[0.62rem] uppercase text-slate-500">{label}</p>
        <div className="space-y-1.5">
          {value.map((item, index) => (
            <pre key={`${label}-${index}`} className="overflow-x-auto rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[0.68rem] leading-5 text-slate-200">
              {JSON.stringify(item, null, 2)}
            </pre>
          ))}
        </div>
      </div>
    );
  }
  if (value && typeof value === 'object') {
    return (
      <div>
        <p className="mb-1 font-mono text-[0.62rem] uppercase text-slate-500">{label}</p>
        <pre className="overflow-x-auto rounded border border-slate-800 bg-slate-950 p-2 font-mono text-[0.68rem] leading-5 text-slate-200">
          {JSON.stringify(value, null, 2)}
        </pre>
      </div>
    );
  }
  return <KeyRow label={label} value={value == null ? '—' : String(value)} mono={typeof value === 'string' && value.length > 80} />;
}

function BulletList({ items, tone = 'default' }: { items: string[]; tone?: 'default' | 'success' | 'warning' }) {
  const dot =
    tone === 'success' ? 'bg-emerald-400' : tone === 'warning' ? 'bg-amber-400' : 'bg-cyan-400/80';
  return (
    <ul className="space-y-1">
      {items.map((item) => (
        <li key={item} className="flex gap-2 leading-5">
          <span className={cn('mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full', dot)} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function stageStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'warning' | 'success' | 'outline' {
  if (status === 'complete') return 'success';
  if (status === 'planned' || status === 'disabled') return 'secondary';
  if (status === 'blocked' || status === 'failed') return 'destructive';
  if (status === 'skipped' || status === 'partial') return 'warning';
  return 'outline';
}
