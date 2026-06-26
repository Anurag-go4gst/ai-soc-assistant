import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  Check,
  Copy,
  Cpu,
  Lightbulb,
  Loader2,
  Send,
  Sparkles,
  Wand2,
  Zap,
} from 'lucide-react';
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
  const [elapsedMs, setElapsedMs] = useState(0);
  const [suggestions, setSuggestions] = useState<string[] | null>(null);

  const loadHealth = () => {
    void getLlmRuntimeHealth().then(setHealth).catch(() => setHealth(null));
  };

  useEffect(() => {
    void getLlmLabStatus().then(setStatus).catch(() => setStatus(null));
    loadHealth();
    const id = window.setInterval(loadHealth, 30_000);
    return () => window.clearInterval(id);
  }, []);

  // Live elapsed ticker while a call is in flight — gives a visible heartbeat so
  // the slow on-prem model never looks frozen.
  useEffect(() => {
    if (!asking) return;
    const started = Date.now();
    setElapsedMs(0);
    const id = window.setInterval(() => setElapsedMs(Date.now() - started), 200);
    return () => window.clearInterval(id);
  }, [asking]);

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

  const applyPreset = (text: string) => {
    setPrompt((current) => (current.trim() ? `${text}\n\n${current.trim()}` : text));
    setSuggestions(null);
  };

  const onAnalyse = () => setSuggestions(analysePrompt(prompt));

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
              <div className="space-y-1.5">
                <p className="text-[0.65rem] uppercase tracking-wide text-slate-500">
                  Starter roles · optional — prepends to your prompt
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {PROMPT_PRESETS.map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      disabled={!available || asking}
                      onClick={() => applyPreset(preset.text)}
                      title={preset.text}
                      className="rounded-full border border-fuchsia-500/30 bg-fuchsia-500/10 px-3 py-1 text-xs text-fuchsia-200 transition hover:bg-fuchsia-500/20 disabled:opacity-40"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
              <Textarea
                value={prompt}
                onChange={(e) => {
                  setPrompt(e.target.value);
                  if (suggestions) setSuggestions(null);
                }}
                placeholder="Ask anything — e.g. explain T1110 brute-force detection logic."
                rows={7}
                disabled={!available || asking}
                className="resize-y bg-slate-950/60 text-sm"
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') void onAsk();
                }}
              />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[0.65rem] text-slate-500">⌘/Ctrl + Enter to send</span>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={asking || !prompt.trim()}
                    onClick={onAnalyse}
                    className="gap-1 border border-amber-500/30 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20"
                  >
                    <Wand2 className="h-3.5 w-3.5" />
                    Analyse
                  </Button>
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
              </div>

              {asking ? (
                <div className="flex items-center gap-2 rounded-md border border-cyan-500/20 bg-cyan-500/5 px-3 py-2 text-xs">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-300" />
                  <span className="font-mono text-cyan-200">{(elapsedMs / 1000).toFixed(1)}s</span>
                  <span className="text-slate-400">
                    {elapsedMs > 120_000
                      ? 'still running — model is slow under load, hold on…'
                      : elapsedMs > 45_000
                        ? 'generating — on-prem 8B can take 30–120s…'
                        : 'model is generating…'}
                  </span>
                </div>
              ) : null}

              {suggestions ? (
                <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3 text-xs">
                  <p className="mb-1.5 flex items-center gap-1.5 font-medium text-amber-200">
                    <Lightbulb className="h-3.5 w-3.5" />
                    Prompt analysis
                  </p>
                  {suggestions.length ? (
                    <ul className="list-disc space-y-1 pl-4 text-slate-300">
                      {suggestions.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-emerald-300">Looks well-formed — role, task, and output expectations are clear.</p>
                  )}
                </div>
              ) : null}

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

interface PromptPreset {
  label: string;
  text: string;
}

// Role/framing starters the on-prem 8B responds best to (concise role + scope +
// explicit output expectation). Optional — prepended to whatever the user types.
const PROMPT_PRESETS: PromptPreset[] = [
  {
    label: 'SOC analyst',
    text: 'You are a senior SOC analyst. Answer concisely and flag any assumption when you lack live data.',
  },
  {
    label: 'Detection engineer',
    text: 'You are a Splunk detection engineer. Give the detection logic and a sample SPL skeleton; mark fields that need tuning.',
  },
  {
    label: 'Threat hunter',
    text: 'You are a threat hunter. Frame the answer as a hypothesis, the data sources to check, and what would confirm or refute it.',
  },
  {
    label: 'MITRE mapper',
    text: 'You are a MITRE ATT&CK specialist. Map the behaviour to technique IDs and state your confidence for each.',
  },
  {
    label: 'IR responder',
    text: 'You are an incident responder. Give prioritised containment and investigation steps (P1–P4).',
  },
];

// Deterministic, instant prompt critique — no LLM round trip. Heuristics over
// what the on-prem model needs to answer well: role framing, scope, output
// shape, length, and time/context anchoring.
function analysePrompt(raw: string): string[] {
  const text = raw.trim();
  const lower = text.toLowerCase();
  const tips: string[] = [];

  if (text.length < 15) {
    tips.push('Very short — add what you actually want answered and any relevant context.');
  }
  const hasRole = /you are|act as|as a |role:/i.test(lower);
  if (!hasRole) {
    tips.push('No role framing — pick a starter (e.g. "SOC analyst") so the model answers in context.');
  }
  const hasOutputShape = /(list|steps|table|spl|json|bullet|summary|paragraph|example)/i.test(lower);
  if (!hasOutputShape) {
    tips.push('No output format — say if you want a list, steps, an SPL skeleton, or a short paragraph.');
  }
  const hasConstraint = /(concise|brief|short|detailed|only|do not|avoid|max|within)/i.test(lower);
  if (!hasConstraint) {
    tips.push('No constraint — add length/scope guidance (e.g. "concise", "3 bullets") to keep it focused.');
  }
  const mentionsData = /(log|splunk|index|sourcetype|event|alert|edr|firewall|dns|auth)/i.test(lower);
  if (mentionsData && !/(no live data|assume|hypothetical|in general)/i.test(lower)) {
    tips.push('References data sources — note this model has no live data, so ask for general logic or assumptions.');
  }
  const wordCount = text.split(/\s+/).filter(Boolean).length;
  if (wordCount > 200) {
    tips.push('Long prompt — trim to the core question; the 8B handles tight prompts better.');
  }
  return tips;
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
