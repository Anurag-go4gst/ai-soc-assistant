import { Shield } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  collectTraceAuthorityRows,
  hasTraceAuthorityData,
  summarizeTraceAuthorityTiers,
  type AuthorityTier,
  type TraceAuthoritySectionRow,
} from '@/lib/traceAuthority';

interface TraceAuthorityPanelProps {
  controlPlaneTrace?: Record<string, unknown> | null;
  compact?: boolean;
  className?: string;
}

export function TraceAuthorityPanel({
  controlPlaneTrace,
  compact = false,
  className,
}: TraceAuthorityPanelProps) {
  const rows = collectTraceAuthorityRows(controlPlaneTrace);
  if (!hasTraceAuthorityData(controlPlaneTrace) || !rows.length) {
    if (controlPlaneTrace && Object.keys(controlPlaneTrace).length > 0) {
      return (
        <p className={cn('text-[11px] text-slate-500', className)}>
          No authority-tier trace available for this response.
        </p>
      );
    }
    return null;
  }

  const indexRows = rows.filter((row) => row.source === 'index');
  const sectionRows = rows.filter((row) => row.source === 'section');

  return (
    <div className={cn('space-y-2', className)}>
      <div className="rounded border border-slate-800 bg-slate-950/80 p-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <Shield className="h-3.5 w-3.5 text-slate-400" />
          <span className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-slate-400">
            Trace authority tier (diagnostic)
          </span>
          <Badge variant="outline">{summarizeTraceAuthorityTiers(rows)}</Badge>
        </div>
        <p className="mt-2 text-[11px] leading-5 text-slate-500">
          Diagnostic authority source for debug trace sections only. Render and evidence authority remain
          {' '}
          <span className="font-mono text-slate-400">RunContract</span>
          {' / '}
          <span className="font-mono text-slate-400">FinalEvidenceGate</span>
          . Trace tiers do not authorize MCP execution or SPL execution.
        </p>
      </div>

      {indexRows.length ? (
        <AuthorityTierTable
          title="Trace authority index"
          caption="Indexed diagnostic authority holders for this turn."
          rows={indexRows}
          compact={compact}
        />
      ) : null}

      {sectionRows.length ? (
        <AuthorityTierTable
          title="Per-section authority tier"
          caption="Authority tier stamped on control-plane trace payloads when present."
          rows={sectionRows}
          compact={compact}
        />
      ) : null}
    </div>
  );
}

function AuthorityTierTable({
  title,
  caption,
  rows,
  compact,
}: {
  title: string;
  caption: string;
  rows: TraceAuthoritySectionRow[];
  compact: boolean;
}) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950/60">
      <div className="border-b border-slate-800 px-2.5 py-2">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-slate-400">{title}</p>
        {!compact ? <p className="mt-1 text-[11px] text-slate-500">{caption}</p> : null}
      </div>
      <div className="divide-y divide-slate-800/80">
        {rows.map((row) => (
          <div key={`${row.source}-${row.key}`} className="px-2.5 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 text-slate-200">{row.label}</span>
              <AuthorityTierBadge tier={row.tier} />
            </div>
            {row.note ? (
              <p className="mt-1 text-[11px] leading-5 text-slate-500">{row.note}</p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

export function AuthorityTierBadge({ tier }: { tier: AuthorityTier }) {
  return (
    <Badge variant={authorityTierVariant(tier)} className="font-mono text-[0.62rem] uppercase tracking-wide">
      {tier}
    </Badge>
  );
}

function authorityTierVariant(
  tier: AuthorityTier,
): 'success' | 'secondary' | 'warning' | 'outline' {
  switch (tier) {
    case 'AUTHORITATIVE':
      return 'success';
    case 'PLANNING':
      return 'secondary';
    case 'ADVISORY':
      return 'warning';
    case 'DIAGNOSTIC':
    default:
      return 'outline';
  }
}
