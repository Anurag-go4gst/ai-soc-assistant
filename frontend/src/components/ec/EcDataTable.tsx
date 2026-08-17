import { cn } from '@/lib/utils';

export function EcDataTable({
  columns,
  rows,
  className,
}: {
  columns: { key: string; label: string; className?: string }[];
  rows: Record<string, string>[];
  className?: string;
}) {
  return (
    <div className={cn('overflow-x-auto rounded-lg border border-slate-700/80 bg-slate-950/50', className)}>
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-cyan-500/20 bg-cyan-950/50">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-cyan-100',
                  col.className,
                )}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/90">
          {rows.map((row, index) => (
            <tr key={index} className="align-top transition-colors hover:bg-slate-900/40">
              {columns.map((col) => (
                <td key={col.key} className={cn('ec-prose-wrap max-w-[28rem] px-4 py-3 text-slate-200', col.className)}>
                  {row[col.key] ?? ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
