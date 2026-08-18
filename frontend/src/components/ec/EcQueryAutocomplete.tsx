import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import type { EcQuerySuggestion } from '@/lib/ecQuerySuggestions';
import { suggestEcQueries } from '@/lib/ecQuerySuggestions';
import type { EcScenarioSummary } from '@/components/ec/types';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export function EcQueryAutocomplete({
  scenarios,
  disabled,
  value,
  onChange,
  onSubmit,
}: {
  scenarios: EcScenarioSummary[];
  disabled?: boolean;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (query: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const suggestions = useMemo(
    () => (open && value.trim().length >= 2 ? suggestEcQueries(scenarios, value, 8) : []),
    [open, scenarios, value],
  );

  useEffect(() => {
    setHighlight(0);
  }, [value, suggestions.length]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, []);

  const selectSuggestion = (item: EcQuerySuggestion) => {
    onChange(item.question);
    setOpen(false);
    onSubmit(item.question);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!open || !suggestions.length) {
      if (event.key === 'Enter' && value.trim()) {
        event.preventDefault();
        setOpen(false);
        onSubmit(value.trim());
      }
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlight((current) => (current + 1) % suggestions.length);
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlight((current) => (current - 1 + suggestions.length) % suggestions.length);
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      selectSuggestion(suggestions[highlight]);
      return;
    }
    if (event.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <Label className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
        Ask in your own words
        <Input
          className="mt-1"
          disabled={disabled}
          placeholder="Type a question (e.g. suspicious IP, firewall block, zero-day…)"
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          aria-autocomplete="list"
          aria-expanded={open && suggestions.length > 0}
          role="combobox"
        />
      </Label>
      {open && suggestions.length > 0 ? (
        <ul
          className="absolute bottom-full z-20 mb-1 w-full overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-lg"
          role="listbox"
        >
          {suggestions.map((item, index) => (
            <li key={`${item.scenario_id}-${item.question}`} role="option" aria-selected={index === highlight}>
              <button
                type="button"
                className={`w-full px-3 py-2 text-left text-sm transition-colors ${
                  index === highlight ? 'bg-cyan-950/60 text-cyan-50' : 'text-slate-200 hover:bg-slate-900'
                }`}
                onMouseDown={(event) => {
                  event.preventDefault();
                  selectSuggestion(item);
                }}
              >
                <span className="block leading-snug">{item.question}</span>
                <span className="mt-0.5 block text-xs text-slate-500">{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-1 text-xs text-slate-500">
        Suggestions appear after 2 characters. Arrow keys navigate; Enter selects. Submit your own wording anytime.
      </p>
    </div>
  );
}
