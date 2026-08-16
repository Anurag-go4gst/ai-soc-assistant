import { useEffect, useMemo, useState } from 'react';
import { listEcScenarios } from '@/api/ecClient';
import type { EcScenarioSummary } from '@/components/ec/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface EcScenarioPickerProps {
  disabled?: boolean;
  selectedId: string;
  onSelect: (scenarioId: string) => void;
  onRun: (scenario: EcScenarioSummary) => void;
}

export function EcScenarioPicker({ disabled, selectedId, onSelect, onRun }: EcScenarioPickerProps) {
  const [scenarios, setScenarios] = useState<EcScenarioSummary[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listEcScenarios()
      .then((payload) => {
        if (!cancelled) {
          setScenarios(payload.scenarios);
          setLoadError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : 'Scenarios unavailable');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => scenarios.find((item) => item.scenario_id === selectedId) ?? scenarios[0],
    [scenarios, selectedId],
  );

  return (
    <div className="space-y-3">
      <label className="block text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
        Investigation
        <select
          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2 text-sm text-slate-100"
          disabled={disabled || !scenarios.length}
          value={selected?.scenario_id ?? ''}
          onChange={(event) => onSelect(event.target.value)}
        >
          {scenarios.map((item) => (
            <option key={item.scenario_id} value={item.scenario_id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      {selected ? (
        <p className="text-sm leading-relaxed text-slate-400">{selected.query}</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={disabled || !selected}
          onClick={() => selected && onRun(selected)}
        >
          Run investigation
        </Button>
        {selected ? <Badge variant="outline">{selected.expected_skill}</Badge> : null}
        {loadError ? <span className="text-xs text-rose-300">{loadError}</span> : null}
      </div>
    </div>
  );
}
