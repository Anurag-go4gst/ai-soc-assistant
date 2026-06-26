import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Code2,
  Compass,
  Crosshair,
  Factory,
  Search,
  Sparkles,
} from 'lucide-react';
import { getDemoScenarios } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import type { DemoScenarioSummary } from '@/types/api';

/**
 * Starter prompts are derived from the SAME curated demo-scenario list the picker
 * uses (single source of truth — no hardcoded, auth-skewed array). We show one
 * category-diverse highlight per category, in the plan's category order, so the
 * surface advertises platform breadth (auth, threat hunt, SPL, MITRE, regulatory,
 * OT/ICS, guided) rather than five flavours of "failed login". The full set lives
 * in the DemoScenarioPicker; this is the curated highlight strip.
 */
const CATEGORY_ICON: Record<string, typeof Search> = {
  'Alert Triage': AlertTriangle,
  'Threat Hunt': Search,
  SPL: Code2,
  MITRE: Crosshair,
  'Knowledge & Compliance': BookOpen,
  'OT/ICS': Factory,
  'Guided (out-of-catalog)': Compass,
};

// Plan category order; surfaces breadth and keeps auth from dominating.
const CATEGORY_ORDER = [
  'Alert Triage',
  'Threat Hunt',
  'SPL',
  'MITRE',
  'Knowledge & Compliance',
  'OT/ICS',
  'Guided (out-of-catalog)',
];

interface HighlightPrompt {
  category: string;
  icon: typeof Search;
  prompt: string;
}

function buildHighlights(scenarios: DemoScenarioSummary[]): HighlightPrompt[] {
  const firstByCategory = new Map<string, DemoScenarioSummary>();
  scenarios.forEach((scenario) => {
    if (!firstByCategory.has(scenario.category)) {
      firstByCategory.set(scenario.category, scenario);
    }
  });

  const ordered = [
    ...CATEGORY_ORDER.filter((category) => firstByCategory.has(category)),
    // Tolerate any backend category not in the known order rather than dropping it.
    ...Array.from(firstByCategory.keys()).filter((category) => !CATEGORY_ORDER.includes(category)),
  ];

  return ordered.map((category) => {
    const scenario = firstByCategory.get(category)!;
    return {
      category,
      icon: CATEGORY_ICON[category] ?? Sparkles,
      prompt: scenario.query,
    };
  });
}

interface StarterPromptsProps {
  disabled?: boolean;
  onPick: (prompt: string) => void;
}

export function StarterPrompts({ disabled, onPick }: StarterPromptsProps) {
  const [highlights, setHighlights] = useState<HighlightPrompt[]>([]);

  useEffect(() => {
    let cancelled = false;
    getDemoScenarios()
      .then((payload) => {
        if (!cancelled) setHighlights(buildHighlights(payload.scenarios));
      })
      .catch(() => {
        // Non-fatal: the DemoScenarioPicker surfaces its own load error; the
        // highlight strip simply stays empty rather than showing a stale fallback.
        if (!cancelled) setHighlights([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (highlights.length === 0) {
    return null;
  }

  return (
    <div className="mt-2 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {highlights.map((highlight) => {
        const Icon = highlight.icon;
        return (
          <div key={highlight.category} className="space-y-1.5">
            <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              <Icon className="h-3 w-3 text-cyan-400/80" />
              {highlight.category}
            </p>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onPick(highlight.prompt)}
              className="block w-full text-left"
            >
              <Badge
                variant="outline"
                className="w-full cursor-pointer justify-start whitespace-normal py-1 text-left font-normal leading-tight hover:border-cyan-400/60 hover:text-cyan-100"
              >
                {highlight.prompt}
              </Badge>
            </button>
          </div>
        );
      })}
    </div>
  );
}
