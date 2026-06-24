import { useCallback, useEffect, useState } from 'react';
import { Activity, RefreshCw, Power, RotateCcw, Play } from 'lucide-react';
import { toast } from 'sonner';
import { controlLlm, getLlmRuntimeHealth, type LlmRuntimeHealth } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const REASON_TONE: Record<string, string> = {
  ok: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200',
  slow: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
  prompt_stall: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
  rate_unknown: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  probe_timeout: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  no_tokens: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  unreachable: 'border-rose-500/40 bg-rose-500/10 text-rose-200',
  llm_disabled: 'border-slate-600/40 bg-slate-600/10 text-slate-400',
};

export function LlmRuntimeHealthPanel() {
  const [health, setHealth] = useState<LlmRuntimeHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setHealth(await getLlmRuntimeHealth());
    } catch (err) {
      toast.error(`LLM health probe failed: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const control = async (action: 'restart' | 'stop' | 'start') => {
    if (action !== 'start' && !window.confirm(`Confirm: ${action} the LLM service? In-flight generations will be interrupted.`)) {
      return;
    }
    setBusy(action);
    try {
      await controlLlm(action);
      toast.success(`LLM ${action} requested — host watcher will apply it shortly.`);
      window.setTimeout(() => void refresh(), 4000);
    } catch (err) {
      toast.error(`LLM ${action} failed: ${(err as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const tone = health ? REASON_TONE[health.reason] ?? REASON_TONE.rate_unknown : REASON_TONE.rate_unknown;
  const rate = health?.tok_per_s;
  const controlOn = Boolean(health?.control_available);

  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Activity className="h-4 w-4 text-cyan-400" /> LLM runtime health
          </CardTitle>
          <Button size="sm" variant="outline" disabled={loading} onClick={() => void refresh()}>
            <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="space-y-1">
              <p className="soc-eyebrow">Live generation throughput</p>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-2xl text-slate-100">
                  {rate === null || rate === undefined ? '—' : rate.toFixed(2)}
                </span>
                <span className="text-xs text-slate-500">tok/s</span>
                <Badge variant="outline" className={`border ${tone}`}>{health?.reason ?? 'probing'}</Badge>
              </div>
            </div>
            <div className="text-right text-[0.65rem] text-slate-500">
              {health?.model ? <div className="font-mono">{health.model}</div> : null}
              {health?.prompt_eval_s != null ? <div>prompt-eval {health.prompt_eval_s}s</div> : null}
              {health?.threshold_tok_per_s != null ? <div>healthy ≥ {health.threshold_tok_per_s} tok/s</div> : null}
            </div>
          </div>
          {rate !== null && rate !== undefined && rate < 2 ? (
            <p className="mt-2 text-[0.7rem] text-amber-200/80">
              Model is alive but slow (host CPU contention). Narration may fall back to deterministic answers.
            </p>
          ) : null}
        </div>

        <div className="rounded-md border border-slate-800 bg-slate-950/50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="soc-eyebrow">Service control</p>
            {controlOn ? (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => void control('restart')}>
                  <RotateCcw className="mr-1 h-3.5 w-3.5" /> Restart
                </Button>
                <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => void control('stop')}>
                  <Power className="mr-1 h-3.5 w-3.5" /> Stop
                </Button>
                <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => void control('start')}>
                  <Play className="mr-1 h-3.5 w-3.5" /> Start
                </Button>
              </div>
            ) : (
              <span className="text-[0.65rem] text-slate-500">
                Disabled — set AI_SOC_LLM_CONTROL_ENABLED + run the host watcher.
              </span>
            )}
          </div>
          {health?.last_control_result ? (
            <p className="mt-2 text-[0.65rem] text-slate-500">
              Last action: {String((health.last_control_result as { action?: string }).action ?? '?')} ·{' '}
              {(health.last_control_result as { ok?: boolean }).ok ? 'applied' : 'failed'}
            </p>
          ) : null}
        </div>
        <p className="text-[0.65rem] text-slate-500">
          Control requests are queued to a host watcher; the web app holds no host privileges.
        </p>
      </CardContent>
    </Card>
  );
}
