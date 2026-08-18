import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Send, Sparkles } from 'lucide-react';
import { listEcScenarios } from '@/api/ecClient';
import type { EcScenarioSummary } from '@/components/ec/types';
import { resolveEcQueryLocal, suggestEcQueries, type EcQuerySuggestion } from '@/lib/ecQuerySuggestions';
import { isClearChatCommand } from '@/lib/chatCommands';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

interface EcCockpitComposerProps {
  disabled?: boolean;
  busy?: boolean;
  selectedId: string;
  activeSkill?: string | null;
  onSelect: (scenarioId: string) => void;
  onRun: (scenario: EcScenarioSummary, queryText: string) => void;
  onClear?: () => void;
}

export function EcCockpitComposer({
  disabled,
  busy,
  selectedId,
  activeSkill,
  onSelect,
  onRun,
  onClear,
}: EcCockpitComposerProps) {
  const [scenarios, setScenarios] = useState<EcScenarioSummary[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef<HTMLDivElement | null>(null);

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

  const flagship = scenarios.filter((item) => item.category === 'Flagship' || /^s[1-7]_/.test(item.scenario_id));
  const rest = scenarios.filter((item) => !flagship.some((row) => row.scenario_id === item.scenario_id));

  const suggestions = useMemo(
    () => (open && text.trim().length >= 2 ? suggestEcQueries(scenarios, text, 6) : []),
    [open, scenarios, text],
  );

  useEffect(() => {
    setHighlight(0);
  }, [text, suggestions.length]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, []);

  const submit = (raw: string) => {
    const value = raw.trim();
    if (!value) return;
    if (isClearChatCommand(value)) {
      setQueryError(null);
      setText('');
      setOpen(false);
      onClear?.();
      return;
    }
    if (disabled) return;
    const match = resolveEcQueryLocal(scenarios, value);
    if (!match) {
      setQueryError('No matching investigation for that wording. Try the catalog or refine your question.');
      return;
    }
    setQueryError(null);
    setText('');
    setOpen(false);
    onSelect(match.scenario_id);
    onRun(match, value);
  };

  const selectSuggestion = (item: EcQuerySuggestion) => {
    setText(item.question);
    submit(item.question);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (open && suggestions.length) {
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
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        selectSuggestion(suggestions[highlight]);
        return;
      }
      if (event.key === 'Escape') {
        setOpen(false);
        return;
      }
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit(text);
    }
  };

  return (
    <div className="soc-composer relative z-20 shrink-0 border-t border-slate-800/90 px-4 py-3 lg:px-8 backdrop-blur-md">
      <div className="w-full space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
          <div className="flex flex-wrap items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
            <span>Investigation command</span>
            {activeSkill ? <Badge variant="outline" className="text-[10px]">{activeSkill}</Badge> : null}
          </div>
          <span className="hidden sm:inline">Enter to send · /clear to reset · Shift+Enter new line</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor="ec-scenario-select">Scenario catalog</label>
          <select
            id="ec-scenario-select"
            className="min-w-[min(100%,320px)] max-w-full rounded-lg border border-slate-700/80 bg-slate-950/70 px-3 py-2 text-sm text-slate-200"
            disabled={disabled || !scenarios.length}
            value={selected?.scenario_id ?? ''}
            onChange={(event) => {
              setQueryError(null);
              onSelect(event.target.value);
              const next = scenarios.find((item) => item.scenario_id === event.target.value);
              if (next) setText(next.query);
            }}
          >
            {flagship.length ? (
              <optgroup label="Flagship">
                {flagship.map((item) => (
                  <option key={item.scenario_id} value={item.scenario_id}>
                    {item.label}
                  </option>
                ))}
              </optgroup>
            ) : null}
            {rest.length ? (
              <optgroup label="Lab">
                {rest.map((item) => (
                  <option key={item.scenario_id} value={item.scenario_id}>
                    {item.label}
                  </option>
                ))}
              </optgroup>
            ) : null}
          </select>
          {selected ? (
            <button
              type="button"
              className="text-xs text-cyan-400/90 hover:text-cyan-300"
              disabled={disabled || !scenarios.length}
              onClick={() => selected && submit(selected.query)}
            >
              Use scenario prompt
            </button>
          ) : null}
        </div>

        <div ref={containerRef} className="relative flex items-end gap-3">
          {open && suggestions.length > 0 ? (
            <ul
              className="absolute bottom-full z-30 mb-2 w-full overflow-hidden rounded-xl border border-slate-700/90 bg-slate-950/95 shadow-2xl ring-1 ring-cyan-500/10"
              role="listbox"
            >
              {suggestions.map((item, index) => (
                <li key={`${item.scenario_id}-${item.question}`} role="option" aria-selected={index === highlight}>
                  <button
                    type="button"
                    className={cn(
                      'w-full px-3 py-2.5 text-left text-sm transition-colors',
                      index === highlight ? 'bg-cyan-950/70 text-cyan-50' : 'text-slate-200 hover:bg-slate-900/80',
                    )}
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

          <Textarea
            rows={4}
            className="min-h-[112px] max-h-56 flex-1 resize-y border-slate-700/80 bg-slate-950/60 text-base leading-relaxed transition-shadow focus-visible:ring-cyan-500/40"
            disabled={disabled || !scenarios.length}
            placeholder="Ask V.AI SOC — suspicious IP, firewall block, zero-day exposure, OT evidence… (/clear to reset)"
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setQueryError(null);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            aria-autocomplete="list"
            aria-expanded={open && suggestions.length > 0}
            role="combobox"
          />
          <Button
            type="button"
            size="icon"
            disabled={disabled || !text.trim()}
            onClick={() => submit(text)}
            aria-label="Send investigation query"
            className="h-12 w-12 shrink-0 self-end transition-transform duration-150 enabled:hover:-translate-y-0.5 enabled:hover:shadow-[0_6px_18px_-8px_hsl(192_88%_52%/0.7)]"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>

        {(loadError || queryError) ? (
          <p className="text-xs text-rose-300">{loadError ?? queryError}</p>
        ) : null}
      </div>
    </div>
  );
}
