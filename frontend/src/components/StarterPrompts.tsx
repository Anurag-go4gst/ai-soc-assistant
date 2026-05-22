import { Badge } from '@/components/ui/badge';

const prompts = [
  'Investigate failed login spike on APP-01',
  'Show SOP for brute-force investigation',
  'Generate SPL for successful login after failures',
  'Map this alert to MITRE',
  'Prepare investigation note',
];

interface StarterPromptsProps {
  disabled?: boolean;
  onPick: (prompt: string) => void;
}

export function StarterPrompts({ disabled, onPick }: StarterPromptsProps) {
  return (
    <div className="space-y-2">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Starter prompts</p>
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt) => (
          <button key={prompt} type="button" disabled={disabled} onClick={() => onPick(prompt)}>
            <Badge variant="outline" className="cursor-pointer hover:border-cyan-400/60 hover:text-cyan-100">
              {prompt}
            </Badge>
          </button>
        ))}
      </div>
    </div>
  );
}
