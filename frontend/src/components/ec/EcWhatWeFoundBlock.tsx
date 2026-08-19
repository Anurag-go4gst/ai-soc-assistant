import type { EcAnalystTextSegment } from '@/components/ec/types';

export function EcWhatWeFoundBlock({
  segments,
  fallbackText,
  onEvidenceLinkClick,
}: {
  segments?: EcAnalystTextSegment[] | null;
  fallbackText: string;
  onEvidenceLinkClick?: (evidenceId: string) => void;
}) {
  if (!segments?.length) {
    return <p className="ec-prose-wrap mt-3 text-sm leading-relaxed text-slate-200">{fallbackText}</p>;
  }

  return (
    <p className="ec-prose-wrap mt-3 text-sm leading-relaxed text-slate-200">
      {segments.map((segment, index) => {
        if (segment.type === 'evidence_link' && segment.evidence_id && onEvidenceLinkClick) {
          return (
            <button
              key={`${segment.evidence_id}-${index}`}
              type="button"
              title={segment.title ?? 'View Splunk MCP evidence receipt'}
              className="font-medium text-cyan-300 underline decoration-cyan-500/50 underline-offset-2 hover:text-cyan-200"
              onClick={() => onEvidenceLinkClick(segment.evidence_id!)}
            >
              {segment.text}
            </button>
          );
        }
        if (segment.type === 'evidence_link' && segment.evidence_id) {
          return (
            <span key={`${segment.evidence_id}-${index}`} className="font-medium text-cyan-200">
              {segment.text}
            </span>
          );
        }
        return <span key={`text-${index}`}>{segment.text}</span>;
      })}
    </p>
  );
}
