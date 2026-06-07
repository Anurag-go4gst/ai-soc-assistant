import { PlayCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { getDemoScenarios } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import type { DemoScenarioSummary } from '@/types/api';

const CATEGORY_ORDER = ['Investigate', 'Knowledge / SOP', 'Generate SPL', 'Generate + Run', 'MITRE Mapping', 'Air-gapped Mode'];

interface DemoScenarioPickerProps {
  disabled?: boolean;
  onRun: (scenario: DemoScenarioSummary) => void;
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
    <div className="mt-3 rounded-lg border border-cyan-500/20 bg-cyan-500/[0.03] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          <PlayCircle className="h-3.5 w-3.5 text-cyan-400" />
          Quick start
        </span>
        <Badge variant="outline">Experience Center</Badge>
      </div>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <select
          value={selected}
          disabled={disabled || !scenarios.length}
          onChange={(event) => setSelected(event.target.value)}
          className="min-h-9 flex-1 rounded-md border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-slate-100 outline-none transition focus:border-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <option value="">{loadError ? 'Scenarios unavailable' : 'Select a scenario'}</option>
          {grouped.map((group) => (
            <optgroup key={group.category} label={group.category}>
              {group.scenarios.map((scenario) => (
                <option key={scenario.scenario_id} value={scenario.scenario_id}>
                  {scenario.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <button
          type="button"
          disabled={disabled || !selectedScenario}
          onClick={() => selectedScenario && onRun(selectedScenario)}
          className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-md border border-cyan-400/40 bg-cyan-400/10 px-3 text-xs font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-900 disabled:text-slate-500"
        >
          <PlayCircle className="h-3.5 w-3.5" />
          Run
        </button>
      </div>
      {selectedScenario ? <ScenarioCapabilityChips category={selectedScenario.category} /> : null}
      {loadError ? <p className="mt-2 text-xs text-amber-100">{loadError}</p> : null}
    </div>
  );
}

function ScenarioCapabilityChips({ category }: { category: DemoScenarioSummary['category'] }) {
  const labels =
    category === 'Knowledge / SOP'
      ? ['Knowledge']
      : category === 'Generate SPL' || category === 'Air-gapped Mode'
        ? ['SPL', 'Knowledge']
        : category === 'Generate + Run'
          ? ['SPL', 'MCP preview']
        : category === 'MITRE Mapping'
          ? ['MITRE', 'Investigation']
          : ['Investigation', 'Knowledge', 'MITRE'];

  return (
    <div className="mt-2 flex flex-wrap gap-1.5 text-[0.65rem] text-slate-400">
      {labels.map((label) => (
        <Badge key={label} variant="secondary">{label}</Badge>
      ))}
    </div>
  );
}
