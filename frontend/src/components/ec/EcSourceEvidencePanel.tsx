import type { EcSourceEvidenceItem } from '@/components/ec/types';
import { EcSectionHeading } from '@/components/ec/EcSectionHeading';
import { Badge } from '@/components/ui/badge';

function provenanceLabel(provenance: string | null | undefined): string {
  switch (provenance) {
    case 'experience_center_fixture':
      return 'Experience Center fixture';
    case 'simulated_mcp':
      return 'Simulated MCP';
    case 'ec_scenario_policy':
      return 'EC scenario policy';
    default:
      return provenance ?? 'Unknown provenance';
  }
}

function sourceTypeLabel(sourceType: string): string {
  switch (sourceType) {
    case 'splunk_mcp_fixture':
      return 'Splunk MCP · ad-hoc SPL';
    case 'splunk_saved_search':
      return 'Splunk MCP · saved search';
    case 'cisco_mcp_fixture':
      return 'Cisco MCP fixture';
    case 'kb_fixture':
      return 'Knowledge base fixture';
    case 'itsm_fixture':
      return 'ITSM fixture';
    default:
      return sourceType;
  }
}

function collectionMethodLabel(item: EcSourceEvidenceItem): string | null {
  if (item.tool_name === 'splunk_run_saved_search' && item.query_or_request_summary) {
    return `Collected via Splunk MCP saved search · ${item.query_or_request_summary}`;
  }
  if (item.tool_name === 'splunk_run_query' && item.executed_spl) {
    return 'Collected via Splunk MCP ad-hoc SPL (`splunk_run_query`)';
  }
  if (item.tool_name) {
    return `Collected via ${item.tool_name}`;
  }
  return null;
}

function formatPreviewValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

export function EcSourceEvidencePanel({
  items,
  highlightEvidenceId = null,
}: {
  items: EcSourceEvidenceItem[];
  highlightEvidenceId?: string | null;
}) {
  if (!items.length) return null;

  return (
    <section data-ec-section="source-evidence">
      <EcSectionHeading>Source evidence</EcSectionHeading>
      <p className="mt-2 text-sm text-slate-400">
        How each evidence item was collected — saved search, ad-hoc SPL, or connector path.
      </p>
      <ul className="mt-4 space-y-3">
        {items.map((item) => {
          const highlighted = highlightEvidenceId != null && item.evidence_id === highlightEvidenceId;
          return (
            <li
              key={item.evidence_id}
              data-evidence-id={item.evidence_id}
              data-ec-evidence-highlight={highlighted ? 'true' : undefined}
              className={
                highlighted
                  ? 'rounded-lg border border-cyan-400/50 bg-cyan-950/35 p-4 ring-1 ring-cyan-400/25'
                  : 'rounded-lg border border-slate-800/80 bg-slate-900/40 p-4'
              }
            >
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-medium text-slate-100">{item.source_name}</h4>
                <Badge variant="outline" className="border-slate-600 text-slate-300">
                  {sourceTypeLabel(item.source_type)}
                </Badge>
                {item.provenance ? (
                  <Badge variant="outline" className="border-cyan-500/40 text-cyan-100">
                    {provenanceLabel(item.provenance)}
                  </Badge>
                ) : null}
                {item.tool_name ? (
                  <Badge variant="outline" className="border-slate-600 font-mono text-xs text-slate-300">
                    {item.tool_name}
                  </Badge>
                ) : null}
              </div>
              {collectionMethodLabel(item) ? (
                <p className="mt-2 text-xs text-slate-400">{collectionMethodLabel(item)}</p>
              ) : null}
              {(item.preview_rows ?? []).map((row, rowIndex) => (
                <dl key={`${item.evidence_id}-row-${rowIndex}`} className="mt-3 space-y-1.5 text-sm">
                  {Object.entries(row).map(([key, value]) => (
                    <div key={key} className="grid gap-1 sm:grid-cols-[minmax(8rem,30%)_1fr]">
                      <dt className="font-medium text-slate-400">{key.replace(/_/g, ' ')}</dt>
                      <dd className="ec-prose-wrap text-slate-100">{formatPreviewValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              ))}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
