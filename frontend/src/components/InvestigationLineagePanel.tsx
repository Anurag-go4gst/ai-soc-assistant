import { ArrowRight, CheckCircle2, CircleDashed, FileSearch, GitBranch, ShieldCheck, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { InvestigationLineage, LineageStage } from '@/types/api';

interface InvestigationLineagePanelProps {
  lineage: InvestigationLineage;
}

export function InvestigationLineagePanel({ lineage }: InvestigationLineagePanelProps) {
  const stages = lineage.stages ?? [];
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/70 text-xs text-slate-300">
      <div className="border-b border-slate-800/80 px-3 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">lineage</Badge>
          <Badge variant="outline">{lineage.lineage_id}</Badge>
        </div>
        <p className="mt-2 text-slate-400">{lineage.summary}</p>
      </div>
      <div className="divide-y divide-slate-800/80">
        {stages.map((stage, index) => (
          <LineageRow key={`${stage.stage_id}-${index}`} stage={stage} isLast={index === stages.length - 1} />
        ))}
      </div>
    </div>
  );
}

function LineageRow({ stage, isLast }: { stage: LineageStage; isLast: boolean }) {
  const Icon = iconForStatus(stage.status);
  return (
    <div className="px-3 py-3">
      <div className="flex gap-3">
        <div className="flex flex-col items-center">
          <Icon className={iconClass(stage.status)} />
          {!isLast ? <div className="mt-1 h-full min-h-6 w-px bg-slate-800" /> : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-slate-100">{stage.visible_label}</span>
            <Badge variant={statusVariant(stage.status)}>{stage.status}</Badge>
            <ModeSourceBadge source={stage.current_mode_source} />
            <DemoShadowBadges stage={stage} />
          </div>
          <p className="mt-1 text-slate-400">{stage.explanation}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
            <span className="inline-flex items-center gap-1">
              <GitBranch className="h-3 w-3" />
              production equivalent
            </span>
            <ArrowRight className="h-3 w-3" />
            <span className="text-slate-300">{stage.production_equivalent}</span>
          </div>
          {stage.produced_answer_sections.length ? (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {stage.produced_answer_sections.map((section) => (
                <Badge key={section} variant="outline">{section}</Badge>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function DemoShadowBadges({ stage }: { stage: LineageStage }) {
  if (stage.stage_id !== 'demo_foundation_sec_shadow') {
    return null;
  }
  const output = stage.technical_output ?? {};
  const provider = typeof output.provider === 'string' ? output.provider : 'disabled';
  const deterministicWins = output.deterministic_wins !== false;
  return (
    <>
      <Badge variant="warning">scenario-backed</Badge>
      <Badge variant={deterministicWins ? 'success' : 'warning'}>
        deterministic wins: {deterministicWins ? 'true' : 'false'}
      </Badge>
      <Badge variant="outline">provider: {provider}</Badge>
      <Badge variant="secondary">not live model output</Badge>
    </>
  );
}

function ModeSourceBadge({ source }: { source: string }) {
  if (source === 'scenario') return <Badge variant="warning">scenario-backed</Badge>;
  if (source === 'live') return <Badge variant="success">live</Badge>;
  if (source === 'derived') return <Badge variant="default">derived</Badge>;
  if (source === 'planned') return <Badge variant="secondary">planned</Badge>;
  if (source === 'config') return <Badge variant="outline">config</Badge>;
  return <Badge variant="outline">{source}</Badge>;
}

function iconForStatus(status: string) {
  if (status === 'complete') return CheckCircle2;
  if (status === 'blocked' || status === 'failed') return XCircle;
  if (status === 'planned' || status === 'disabled') return CircleDashed;
  if (status === 'skipped' || status === 'partial') return FileSearch;
  return ShieldCheck;
}

function iconClass(status: string): string {
  if (status === 'complete') return 'mt-0.5 h-4 w-4 shrink-0 text-emerald-300';
  if (status === 'blocked' || status === 'failed') return 'mt-0.5 h-4 w-4 shrink-0 text-red-300';
  if (status === 'planned' || status === 'disabled') return 'mt-0.5 h-4 w-4 shrink-0 text-slate-400';
  if (status === 'skipped' || status === 'partial') return 'mt-0.5 h-4 w-4 shrink-0 text-amber-300';
  return 'mt-0.5 h-4 w-4 shrink-0 text-cyan-300';
}

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'warning' | 'success' | 'outline' {
  if (status === 'complete') return 'success';
  if (status === 'blocked' || status === 'failed') return 'destructive';
  if (status === 'planned' || status === 'disabled') return 'secondary';
  if (status === 'skipped' || status === 'partial') return 'warning';
  return 'outline';
}
