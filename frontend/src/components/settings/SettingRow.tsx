import { ReactNode } from 'react';
import { Check, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface SettingRowProps {
  label: string;
  value: ReactNode;
  mono?: boolean;
  className?: string;
}

export function SettingRow({ label, value, mono, className }: SettingRowProps) {
  return (
    <div className={cn('flex items-center justify-between gap-3 border-b border-slate-800/60 py-2 last:border-b-0', className)}>
      <span className="text-xs text-slate-400">{label}</span>
      <span className={cn('text-right text-xs text-slate-100', mono && 'font-mono')}>{value}</span>
    </div>
  );
}

export function BoolPill({ value, trueLabel, falseLabel }: { value: boolean; trueLabel?: string; falseLabel?: string }) {
  return value ? (
    <Badge variant="success" className="gap-1">
      <Check className="h-3 w-3" />
      {trueLabel ?? 'yes'}
    </Badge>
  ) : (
    <Badge variant="secondary" className="gap-1">
      <X className="h-3 w-3" />
      {falseLabel ?? 'no'}
    </Badge>
  );
}

export function ModeBadge({ mode }: { mode: string }) {
  const variant = mode === 'live' ? 'success' : 'warning';
  return <Badge variant={variant}>{mode}</Badge>;
}

export function PanelMockBanner() {
  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-500/8 px-3 py-2 text-xs text-amber-100">
      Mock configuration — live connector not enabled yet.
    </div>
  );
}
