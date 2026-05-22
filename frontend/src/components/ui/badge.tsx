import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold', {
  variants: {
    variant: {
      default: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100',
      secondary: 'border-slate-700 bg-slate-800 text-slate-200',
      destructive: 'border-red-400/40 bg-red-500/15 text-red-100',
      warning: 'border-amber-400/40 bg-amber-500/15 text-amber-100',
      success: 'border-emerald-400/40 bg-emerald-500/15 text-emerald-100',
      outline: 'border-slate-700 text-slate-300',
    },
  },
  defaultVariants: { variant: 'default' },
});

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
