/** Pretty-print SPL for analyst UI — wraps at pipes; does not alter executable SPL. */
export function formatSplForDisplay(spl: string): string {
  const normalized = spl.replace(/\\n/g, '\n').trim();
  if (!normalized) return '';
  if (normalized.includes('\n')) return normalized;

  const parts = normalized.split(/\s*\|\s*/);
  if (parts.length <= 1) return normalized;

  return parts.map((part, index) => (index === 0 ? part.trim() : `| ${part.trim()}`)).join('\n');
}
