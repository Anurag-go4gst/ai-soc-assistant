import { PlayCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { getDemoScenarios } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import type { DemoScenarioSummary } from '@/types/api';

// Plan category order (Track C). Backend supplies these exact display strings.
const CATEGORY_ORDER = [
  'Coordinated Firewall Incident',
  'Alert Triage',
  'Threat Hunt',
  'SPL',
  'MITRE',
  'Knowledge & Compliance',
  'OT/ICS',
  'Guided (out-of-catalog)',
];

interface DemoScenarioPickerProps {
  disabled?: boolean;
  onRun: (scenario: DemoScenarioSummary) => void;
}

// Backend labels are prefixed with a sequence tag ("Q1 · ", "Q2 · "). Strip it so
// the dropdown reads as a plain, understandable summary of the scenario.
function scenarioSummary(label: string): string {
  return (label || '').replace(/^Q\d+\s*[·.:\-)]\s*/i, '').trim() || label;
}

export function DemoScenarioPicker({ disabled, onRun }: DemoScenarioPickerProps) {
  const [scenarios, setScenarios] = useState<DemoScenarioSummary[]>([]);
  const [selected, setSelected] = useState('');
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDemoScenarios()
      .then((payload) => {
        if (!cancelled) {
          setScenarios(payload.scenarios);
          setLoadError(null);
        }
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : 'Demo scenarios unavailable');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const grouped = useMemo(() => {
    const map = new Map<string, DemoScenarioSummary[]>();
    scenarios.forEach((scenario) => {
      const list = map.get(scenario.category) ?? [];
      list.push(scenario);
      map.set(scenario.category, list);
    });
    return CATEGORY_ORDER.filter((category) => map.has(category)).map((category) => ({
      category,
      scenarios: map.get(category) ?? [],
    }));
  }, [scenarios]);

  const selectedScenario = scenarios.find((scenario) => scenario.scenario_id === selected) ?? null;

  return (
    <div className="mt-3 min-w-0 w-full max-w-full overflow-hidden rounded-lg border border-cyan-500/20 bg-cyan-500/[0.03] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          <PlayCircle className="h-3.5 w-3.5 text-cyan-400" />
          Quick start
        </span>
        <Badge variant="outline">Experience Center</Badge>
      </div>
      <div className="mt-2 flex min-w-0 flex-col gap-2 sm:flex-row">
        <select
          value={selected}
          disabled={disabled || !scenarios.length}
          onChange={(event) => setSelected(event.target.value)}
          className="min-h-11 min-w-0 w-full max-w-full flex-1 truncate rounded-md border border-slate-700 bg-slate-950/80 px-3 py-2.5 text-sm leading-relaxed text-slate-100 outline-none transition focus:border-cyan-400 disabled:cursor-not-allowed disabled:opacity-60 sm:text-base"
        >
          <option value="">{loadError ? 'Scenarios unavailable' : 'Select a scenario'}</option>
          {grouped.map((group) => (
            <optgroup key={group.category} label={group.category}>
              {group.scenarios.map((scenario) => (
                <option key={scenario.scenario_id} value={scenario.scenario_id} title={scenario.query}>
                  {scenarioSummary(scenario.label)}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <button
          type="button"
          disabled={disabled || !selectedScenario}
          onClick={() => selectedScenario && onRun(selectedScenario)}
          className="inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded-md border border-cyan-400/40 bg-cyan-400/10 px-4 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-900 disabled:text-slate-500 sm:w-auto"
        >
          <PlayCircle className="h-3.5 w-3.5" />
          Run
        </button>
      </div>
      {selectedScenario ? (
        <p className="mt-2 break-words rounded-md border border-slate-800/80 bg-slate-950/50 px-3 py-2.5 text-sm leading-6 text-slate-200 sm:text-base sm:leading-7">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-cyan-300/90">
            {scenarioSummary(selectedScenario.label)}
          </span>
          {selectedScenario.query}
        </p>
      ) : null}
      {selectedScenario ? <ScenarioCapabilityChips category={selectedScenario.category} /> : null}
      {loadError ? <p className="mt-2 text-xs text-amber-100">{loadError}</p> : null}
    </div>
  );
}

const CATEGORY_CAPABILITY_CHIPS: Record<string, string[]> = {
  'Coordinated Firewall Incident': ['Investigation', 'SPL', 'MITRE'],
  'Alert Triage': ['Investigation', 'MITRE', 'Knowledge'],
  'Threat Hunt': ['SPL', 'Investigation'],
  SPL: ['SPL', 'Knowledge'],
  MITRE: ['MITRE', 'Investigation'],
  'Knowledge & Compliance': ['Knowledge'],
  'OT/ICS': ['SPL', 'Investigation'],
  'Guided (out-of-catalog)': ['Investigation', 'Knowledge'],
};

function ScenarioCapabilityChips({ category }: { category: DemoScenarioSummary['category'] }) {
  const labels = CATEGORY_CAPABILITY_CHIPS[category] ?? ['Investigation', 'Knowledge', 'MITRE'];

  return (
    <div className="mt-2 flex flex-wrap gap-1.5 text-[0.65rem] text-slate-400">
      {labels.map((label) => (
        <Badge key={label} variant="secondary">{label}</Badge>
      ))}
    </div>
  );
}
