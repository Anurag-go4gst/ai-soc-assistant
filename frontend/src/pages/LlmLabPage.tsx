import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Activity, Check, Copy, Cpu, Send, Sparkles, Zap } from 'lucide-react';
import { askLlmLab, getLlmLabStatus, getLlmRuntimeHealth } from '@/api/client';
import type { LlmLabAnswer, LlmLabStatus, LlmRuntimeHealth } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';

export function LlmLabPage() {
  const [status, setStatus] = useState<LlmLabStatus | null>(null);
  const [health, setHealth] = useState<LlmRuntimeHealth | null>(null);
  const [prompt, setPrompt] = useState('');
  const [result, setResult] = useState<LlmLabAnswer | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const loadHealth = () => {
    void getLlmRuntimeHealth().then(setHealth).catch(() => setHealth(null));
  };

  useEffect(() => {
    void getLlmLabStatus().then(setStatus).catch(() => setStatus(null));
    loadHealth();
    const id = window.setInterval(loadHealth, 30_000);
    return () => window.clearInterval(id);
  }, []);

  const onAsk = async () => {
    const trimmed = prompt.trim();
    if (!trimmed || asking) return;
    setAsking(true);
    setError(null);
    setResult(null);
    setCopied(false);
    try {
      const answer = await askLlmLab({ prompt: trimmed });
      setResult(answer);
      loadHealth();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ask failed');
    } finally {
      setAsking(false);
    }
  };

  const onCopy = () => {
    if (!result?.answer) return;
    void navigator.clipboard.writeText(result.answer).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    });
  };

  const available = status?.available ?? false;

  return (
    <ScrollArea className="h-full">
      <div className="min-h-full w-full bg-gradient-to-br from-slate-950 via-slate-950 to-cyan-950/30">
        <div className="w-full space-y-5 p-4 lg:p-8">
          <header className="rounded-xl border border-cyan-500/20 bg-gradient-to-r from-cyan-500/10 via-fuchsia-500/5 to-transparent p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="soc-eyebrow text-cyan-300">Direct LLM</p>
                <h2 className="mt-1 flex items-center gap-2 text-2xl font-semibold text-slate-100">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-fuchsia-500 text-slate-950">
                    <Sparkles className="h-5 w-5" />
                  </span>
                  Ask the model directly
                </h2>
                <p className="mt-1.5 text-sm text-slate-400">
                  Raw text-in / text-out probe of the on-prem model — no tools, no live data, no SOC governance.
                </p>
              </div>
              {status === null ? (
                <Badge variant="secondary">checking…</Badge>
              ) : available ? (
                <Badge className="bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30">model ready</Badge>
              ) : (
                <Badge className="bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30">
                  unavailable · {status.mode}
                </Badge>
              )}
            </div>
          </header>

          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <HealthCard
              icon={<Activity className="h-4 w-4" />}
              label="Reachable"
              value={health === null ? '—' : health.reachable ? 'Yes' : 'No'}
              tone={health?.reachable ? 'good' : 'bad'}
            />
            <HealthCard
              icon={<Zap className="h-4 w-4" />}
              label="Throughput"
              value={health?.tok_per_s != null ? `${health.tok_per_s.toFixed(1)} tok/s` : '—'}
              tone={health?.healthy ? 'good' : health ? 'warn' : 'idle'}
            />
            <HealthCard
              icon={<Cpu className="h-4 w-4" />}
              label="Status"
              value={health?.status ?? '—'}
              tone={health?.healthy ? 'good' : health ? 'warn' : 'idle'}
            />
            <HealthCard
              icon={<Sparkles className="h-4 w-4" />}
              label="Model"
              value={health?.model ?? '—'}
              tone="idle"
            />
          </section>

          <Card className="border-slate-800/80 bg-slate-900/50">
            <CardHeader>
              <CardTitle className="text-sm text-cyan-200">Prompt</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Ask anything — e.g. explain T1110 brute-force detection logic."
                rows={7}
                disabled={!available || asking}
                className="resize-y bg-slate-950/60 text-sm"
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') void onAsk();
                }}
              />
              <div className="flex items-center justify-between">
                <span className="text-[0.65rem] text-slate-500">⌘/Ctrl + Enter to send</span>
                <Button
                  size="sm"
                  disabled={!available || asking || !prompt.trim()}
                  onClick={() => void onAsk()}
                  className="bg-gradient-to-r from-cyan-500 to-fuchsia-500 text-slate-950 hover:opacity-90"
                >
                  <Send className={asking ? 'h-3.5 w-3.5 animate-pulse' : 'h-3.5 w-3.5'} />
                  {asking ? 'Asking…' : 'Ask'}
                </Button>
              </div>
              {!available && status !== null ? (
                <p className="text-xs text-slate-500">
                  LLM not enabled on this deployment. Set <code>AI_SOC_LLM_ENABLED=true</code> and configure a local /
                  instruct endpoint, then restart the backend.
                </p>
              ) : null}
            </CardContent>
          </Card>

          {error ? <p className="text-xs text-rose-400">{error}</p> : null}

          {result ? (
            <Card className="border-cyan-500/20 bg-slate-900/50">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-sm text-cyan-200">Response</CardTitle>
                <div className="flex items-center gap-2 text-[0.65rem] text-slate-500">
                  {result.provider ? (
                    <Badge variant="secondary" className="bg-fuchsia-500/10 text-fuchsia-200">
                      {result.provider}
                    </Badge>
                  ) : null}
                  <span>{result.latency_ms} ms</span>
                  {result.answer ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      className="h-7 gap-1 border border-cyan-500/30 bg-cyan-500/10 px-2.5 text-cyan-200 hover:bg-cyan-500/20"
                      onClick={onCopy}
                    >
                      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      {copied ? 'Copied' : 'Copy'}
                    </Button>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent>
                {result.answer ? (
                  <pre className="whitespace-pre-wrap break-words rounded-md bg-slate-950/60 p-4 font-sans text-sm leading-relaxed text-slate-100">
                    {result.answer}
                  </pre>
                ) : (
                  <p className="text-xs text-slate-400">
                    No answer returned
                    {result.timed_out ? ' — model timed out.' : result.reason ? ` (${result.reason}).` : '.'}
                  </p>
                )}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </ScrollArea>
  );
}

type Tone = 'good' | 'warn' | 'bad' | 'idle';

const TONE_RING: Record<Tone, string> = {
  good: 'border-emerald-500/30 text-emerald-300',
  warn: 'border-amber-500/30 text-amber-300',
  bad: 'border-rose-500/30 text-rose-300',
  idle: 'border-slate-700/60 text-slate-300',
};

function HealthCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone: Tone;
}) {
  return (
    <div className={`rounded-lg border bg-slate-900/40 p-3 ${TONE_RING[tone]}`}>
      <div className="flex items-center gap-2 text-[0.7rem] uppercase tracking-wide text-slate-500">
        {icon}
        {label}
      </div>
      <p className="mt-1.5 truncate text-base font-semibold" title={value}>
        {value}
      </p>
    </div>
  );
}
