import { ClipboardCopy, Code2, Filter, Layers, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getSplOptimizationRegistry,
  saveSplOptimizationRegistryOverrides,
  type SplLogicEntry,
  type SplOptimizationRegistry,
} from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

const LAYER_LABELS: Record<string, string> = {
  draft_quality: 'Draft quality (preprocessor)',
  classification: 'Optimization classification',
  compiler: 'Layer 1a — plan compiler',
  deterministic_rewrite: 'Layer 2 — AUTO_FIX_SAFE',
  rewrite_guard: 'Rewrite guard (V1→V2)',
  simplifier: 'Post-validation simplifier',
  pending_llm: 'Pending LLM spine (S5–S7)',
};

const SEVERITY_VARIANT: Record<string, 'destructive' | 'warning' | 'outline' | 'secondary' | 'success'> = {
  hard_fail: 'destructive',
  warning: 'warning',
  advisory: 'outline',
  gate: 'secondary',
  transform: 'success',
  pending: 'secondary',
};

export function SplOptimizationRegistryPanel() {
  const [registry, setRegistry] = useState<SplOptimizationRegistry | null>(null);
  const [filter, setFilter] = useState('');
  const [layerFilter, setLayerFilter] = useState<string>('all');
  const [draftOverrides, setDraftOverrides] = useState<Record<string, { ui_enabled: boolean; ui_note: string }>>({});
  const [dirty, setDirty] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSplOptimizationRegistry();
      setRegistry(data);
      const initial: Record<string, { ui_enabled: boolean; ui_note: string }> = {};
      data.entries.forEach((entry) => {
        initial[entry.logic_id] = {
          ui_enabled: entry.ui_enabled,
          ui_note: entry.ui_note ?? '',
        };
      });
      setDraftOverrides(initial);
      setDirty(false);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const entries = useMemo(() => {
    if (!registry) return [];
    const needle = filter.trim().toLowerCase();
    return registry.entries.filter((entry) => {
      if (layerFilter !== 'all' && entry.layer !== layerFilter) return false;
      if (!needle) return true;
      const hay = [
        entry.logic_id,
        entry.title,
        entry.description,
        entry.rule_id ?? '',
        entry.code.display,
        entry.layer,
        entry.phase,
      ]
        .join(' ')
        .toLowerCase();
      return hay.includes(needle);
    });
  }, [registry, filter, layerFilter]);

  const toggleEntry = (logicId: string, enabled: boolean) => {
    setDraftOverrides((prev) => ({
      ...prev,
      [logicId]: { ui_enabled: enabled, ui_note: prev[logicId]?.ui_note ?? '' },
    }));
    setDirty(true);
  };

  const saveOverrides = async () => {
    try {
      const result = await saveSplOptimizationRegistryOverrides(draftOverrides);
      setRegistry(result.registry);
      setDirty(false);
      setNote('UI preferences saved (preference-only until runtime wiring).');
    } catch (err) {
      setNote(`Save failed: ${(err as Error).message}`);
    }
  };

  const copyPath = async (entry: SplLogicEntry) => {
    await navigator.clipboard?.writeText(entry.code.display);
    setNote(`Copied ${entry.code.display}`);
  };

  if (loading && !registry) {
    return (
      <Card className="soc-panel border-violet-900/40">
        <CardContent className="py-6 text-xs text-slate-400">Loading SPL optimization registry…</CardContent>
      </Card>
    );
  }

  if (error && !registry) {
    return (
      <Card className="soc-panel border-red-900/40">
        <CardContent className="py-6 text-xs text-red-300">Registry unavailable: {error}</CardContent>
      </Card>
    );
  }

  return (
    <Card className="soc-panel border-violet-900/40">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Layers className="h-4 w-4 text-violet-400" />
          SPL preprocessor &amp; optimization logic (live registry)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-xs text-slate-300">
        <p className="text-slate-400">
          Linked to committed code via inspect — line numbers refresh on each API call. Deterministic spine{' '}
          <Badge variant="success" className="mx-1 text-[0.65rem]">
            ACCEPTED
          </Badge>
          ; LLM layers marked pending until Foundation-Sec probes pass.
        </p>
        {registry?.ui_toggle_policy ? (
          <div className="rounded border border-amber-900/50 bg-amber-950/20 p-3 text-amber-100/90">
            {registry.ui_toggle_policy}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Input
            className="max-w-xs h-8 text-xs"
            placeholder="Filter rules…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <select
            className="h-8 rounded border border-slate-700 bg-slate-950 px-2 text-xs text-slate-200"
            value={layerFilter}
            onChange={(e) => setLayerFilter(e.target.value)}
          >
            <option value="all">All layers</option>
            {Object.keys(LAYER_LABELS).map((layer) => (
              <option key={layer} value={layer}>
                {LAYER_LABELS[layer]}
              </option>
            ))}
          </select>
          <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
            <RefreshCw className="mr-1 h-3 w-3" /> Refresh anchors
          </Button>
          <Button type="button" size="sm" onClick={() => void saveOverrides()} disabled={!dirty}>
            Save UI preferences
          </Button>
          {registry ? (
            <Badge variant="outline">{registry.entry_count} rules</Badge>
          ) : null}
        </div>

        {note ? <Badge variant="outline">{note}</Badge> : null}

        {Object.entries(LAYER_LABELS).map(([layer, label]) => {
          const layerEntries = entries.filter((e) => e.layer === layer);
          if (layerEntries.length === 0) return null;
          return (
            <section key={layer} className="space-y-2">
              <div className="flex items-center gap-2">
                <Filter className="h-3.5 w-3.5 text-violet-300" />
                <h3 className="font-medium text-slate-100">{label}</h3>
                <Badge variant="secondary">{layerEntries.length}</Badge>
              </div>
              <div className="space-y-2">
                {layerEntries.map((entry) => (
                  <LogicRow
                    key={entry.logic_id}
                    entry={entry}
                    uiEnabled={draftOverrides[entry.logic_id]?.ui_enabled ?? entry.ui_enabled}
                    onToggle={(enabled) => toggleEntry(entry.logic_id, enabled)}
                    onCopy={() => void copyPath(entry)}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </CardContent>
    </Card>
  );
}

function LogicRow({
  entry,
  uiEnabled,
  onToggle,
  onCopy,
}: {
  entry: SplLogicEntry;
  uiEnabled: boolean;
  onToggle: (enabled: boolean) => void;
  onCopy: () => void;
}) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950 p-3">
      <div className="flex flex-wrap items-start gap-3">
        <label className="flex items-center gap-2 pt-0.5">
          <input
            type="checkbox"
            className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-900"
            checked={uiEnabled}
            disabled={!entry.ui_toggle_allowed}
            onChange={(e) => onToggle(e.target.checked)}
            title={
              entry.ui_toggle_allowed
                ? 'UI preference (runtime still active until wired)'
                : 'Safety/gate rules cannot be toggled from UI'
            }
          />
          <span className="sr-only">Enable {entry.title}</span>
        </label>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-slate-100">{entry.title}</span>
            <Badge variant={SEVERITY_VARIANT[entry.severity] ?? 'outline'}>{entry.severity}</Badge>
            <Badge variant={entry.runtime_active ? 'success' : 'secondary'}>
              runtime {entry.runtime_active ? 'on' : 'off'}
            </Badge>
            <Badge variant="outline">{entry.phase}</Badge>
            {entry.rule_id ? (
              <Badge variant="outline" className="font-mono text-[0.65rem]">
                {entry.rule_id}
              </Badge>
            ) : null}
          </div>
          <p className="text-slate-400">{entry.description}</p>
          <div className="flex flex-wrap items-center gap-2 font-mono text-[0.65rem] text-cyan-200/90">
            <Code2 className="h-3 w-3 text-cyan-400" />
            <span>{entry.code.display}</span>
            <span className="text-slate-600">·</span>
            <span className="text-slate-500">{entry.code.symbol}</span>
            <Button type="button" size="sm" variant="ghost" className="h-6 px-2" onClick={onCopy}>
              <ClipboardCopy className="h-3 w-3" />
            </Button>
          </div>
          {entry.triggers_classification ? (
            <p className="text-violet-300/80">Routes to: {entry.triggers_classification}</p>
          ) : null}
          {entry.rewrite_step ? (
            <p className="text-emerald-300/80">Rewrite step: {entry.rewrite_step}</p>
          ) : null}
          {entry.guard_invariants.length > 0 ? (
            <p className="text-slate-500">Guard invariants: {entry.guard_invariants.join(', ')}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
