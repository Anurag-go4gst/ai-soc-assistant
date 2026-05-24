import { Search, BookOpen, Code2, Crosshair } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface PromptGroup {
  label: string;
  icon: typeof Search;
  prompts: string[];
}

const GROUPS: PromptGroup[] = [
  {
    label: 'Investigate',
    icon: Search,
    prompts: ['Investigate failed login spike on APP-01', 'Show successful logins from new source IPs in the last hour'],
  },
  {
    label: 'Knowledge / SOP',
    icon: BookOpen,
    prompts: ['Show SOP for brute-force investigation', 'What is the playbook for failed login investigation?'],
  },
  {
    label: 'Generate SPL',
    icon: Code2,
    prompts: ['Generate SPL for successful login after failures', 'Generate SPL for account lockouts over time'],
  },
  {
    label: 'MITRE Mapping',
    icon: Crosshair,
    prompts: ['Map this alert to MITRE'],
  },
];

interface StarterPromptsProps {
  disabled?: boolean;
  onPick: (prompt: string) => void;
}

export function StarterPrompts({ disabled, onPick }: StarterPromptsProps) {
  return (
    <div className="mt-2 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
      {GROUPS.map((group) => {
        const Icon = group.icon;
        return (
          <div key={group.label} className="space-y-1.5">
            <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              <Icon className="h-3 w-3 text-cyan-400/80" />
              {group.label}
            </p>
            <div className="flex flex-col gap-1.5">
              {group.prompts.map((prompt) => (
                <button key={prompt} type="button" disabled={disabled} onClick={() => onPick(prompt)} className="text-left">
                  <Badge
                    variant="outline"
                    className="w-full cursor-pointer justify-start whitespace-normal py-1 text-left font-normal leading-tight hover:border-cyan-400/60 hover:text-cyan-100"
                  >
                    {prompt}
                  </Badge>
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
