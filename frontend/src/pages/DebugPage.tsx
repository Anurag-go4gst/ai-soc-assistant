import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, Bug, Check, Copy, RefreshCcw, Search } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import {
  getDebugReadiness,
  getDebugTraceBundle,
  getDebugTraceTimeline,
  getDebugTraces,
} from '@/api/client';
import { CopyButton } from '@/components/CopyButton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import type {
  DebugReadinessResponse,
  DebugTraceBundle,
  DebugTraceEvent,
  DebugTraceRun,
  DebugTraceTimeline,
} from '@/types/api';

type PageState = 'loading' | 'ready' | 'disabled' | 'forbidden' | 'error';

function formatRelativeTime(iso?: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diffMs = Date.now() - then;
  const sec = Math.round(diffMs / 1000);
  if (sec < 0) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(then).toLocaleDateString();
}

function formatExactTime(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString();
}

function statusTone(status?: string | null): string {
  switch (status) {
    case 'completed':
      return 'bg-emerald-950/40 text-emerald-300 border border-emerald-700/40';
    case 'human_review':
      return 'bg-amber-950/40 text-amber-300 border border-amber-700/40';
    case 'running':
      return 'bg-cyan-950/40 text-cyan-300 border border-cyan-700/40';
    case 'abandoned':
      return 'bg-slate-800/60 text-slate-400 border border-slate-600/40';
    case 'error':
      return 'bg-rose-950/40 text-rose-300 border border-rose-700/40';
    default:
      return 'bg-slate-800/60 text-slate-300 border border-slate-700/40';
  }
}

export function DebugPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [pageState, setPageState] = useState<PageState>('loading');
  const [error, setError] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<DebugReadinessResponse | null>(null);
  const [traces, setTraces] = useState<DebugTraceRun[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState(searchParams.get('trace_id') ?? '');
  const [traceInput, setTraceInput] = useState(searchParams.get('trace_id') ?? '');
  const [timeline, setTimeline] = useState<DebugTraceTimeline | null>(null);
  const [bundle, setBundle] = useState<DebugTraceBundle | null>(null);

  const loadOverview = async () => {
    setPageState('loading');
    setError(null);
    try {
      const [readinessResult, tracesResult] = await Promise.all([
        getDebugReadiness(),
        getDebugTraces({ limit: 50 }),
      ]);
      setReadiness(readinessResult);
      setTraces(tracesResult.traces);
      setPageState('ready');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Debug API unavailable';
      setError(message);
      setReadiness(null);
      setTraces([]);
      setTimeline(null);
      setBundle(null);
      setSelectedTraceId('');
      if (message.includes('404')) setPageState('disabled');
      else if (message.includes('403')) setPageState('forbidden');
      else setPageState('error');
    }
  };

  const loadTraceDetail = async (traceId: string) => {
    if (!traceId.trim()) {
      setTimeline(null);
      setBundle(null);
      return;
    }
    try {
      const [timelineResult, bundleResult] = await Promise.all([
        getDebugTraceTimeline(traceId),
        getDebugTraceBundle(traceId),
      ]);
      setTimeline(timelineResult);
      setBundle(bundleResult);
      setSelectedTraceId(traceId);
      if (searchParams.get('trace_id') !== traceId) {
        setSearchParams({ trace_id: traceId });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Trace load failed';
      setError(message);
      setTimeline(null);
      setBundle(null);
    }
  };

  const refreshAll = async () => {
    const traceId = selectedTraceId.trim();
    await loadOverview();
    if (traceId) {
      await loadTraceDetail(traceId);
    }
  };

  useEffect(() => {
    void loadOverview();
  }, []);

  useEffect(() => {
    const fromUrl = searchParams.get('trace_id')?.trim();
    if (!fromUrl || pageState !== 'ready') return;
    setTraceInput(fromUrl);
    if (selectedTraceId === fromUrl && bundle?.trace_id === fromUrl) return;
    void loadTraceDetail(fromUrl);
  }, [pageState, searchParams, selectedTraceId, bundle?.trace_id]);

  return (
    <ScrollArea className="h-full">
      <div className="min-w-0 max-w-full space-y-4 p-4 lg:p-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="soc-eyebrow text-cyan-400">Debug</p>
            <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
              <Bug className="h-4 w-4 text-cyan-400" />
              COE Observability
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Live telemetry traces, event timelines, debug bundles, and infra readiness.
            </p>
          </div>
          <Button size="sm" variant="secondary" disabled={pageState === 'loading'} onClick={() => void refreshAll()}>
            <RefreshCcw className={pageState === 'loading' ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
            Refresh
          </Button>
        </header>

        {pageState === 'disabled' ? (
          <NoticeCard
            title="Debug API disabled"
            detail="Set AI_SOC_DEBUG_API_ENABLED=true and restart the backend. It defaults to on; this message means an operator turned it off."
          />
        ) : null}

        {pageState === 'forbidden' ? (
          <NoticeCard
            title="Debug access disabled for your profile"
            detail="Open Settings → Profile and enable “Debug observability”, or ask your COE admin to toggle debug_access in the user registry."
          />
        ) : null}

        {pageState === 'error' ? (
          <NoticeCard title="Debug load failed" detail={error ?? 'Could not load debug surfaces.'} />
        ) : null}

        {readiness ? <ReadinessPanel readiness={readiness} /> : null}

        {pageState === 'ready' ? (
          <>
            <Card className="soc-panel">
              <CardHeader className="py-3">
                <CardTitle className="text-sm font-semibold">Lookup trace</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                <Input
                  value={traceInput}
                  onChange={(event) => setTraceInput(event.target.value)}
                  placeholder="Paste trace_id from chat response"
                  className="max-w-xl font-mono text-xs"
                />
                <Button size="sm" onClick={() => void loadTraceDetail(traceInput.trim())}>
                  <Search className="mr-1 h-3.5 w-3.5" />
                  Load trace
                </Button>
              </CardContent>
            </Card>

            <section className="grid gap-4 xl:grid-cols-[1fr_1.2fr]">
              <TraceList traces={traces} selectedTraceId={selectedTraceId} onSelect={(id) => void loadTraceDetail(id)} />
              <TraceTimelinePanel timeline={timeline} />
            </section>

            <BundlePanel bundle={bundle} />
          </>
        ) : null}
      </div>
    </ScrollArea>
  );
}

function ReadinessPanel({ readiness }: { readiness: DebugReadinessResponse }) {
  const telemetry = readiness.telemetry as Record<string, unknown>;
  const metrics = (telemetry.metrics as Record<string, number> | undefined) ?? {};
  return (
    <Card className="soc-panel">
      <CardHeader className="flex flex-row items-center justify-between gap-2 py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Activity className="h-4 w-4 text-cyan-300" />
          Readiness snapshot
        </CardTitle>
        <CopyButton value={JSON.stringify(readiness, null, 2)} label="Copy readiness" />
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 text-xs text-slate-300">
        <Metric label="Telemetry sink" value={String(telemetry.telemetry_sink ?? '—')} />
        <Metric label="Connector" value={String(telemetry.connector_detail ?? '—')} />
        <Metric
          label="Write failures"
          value={String(metrics.telemetry_write_failures ?? 0)}
        />
        <Metric
          label="Global write disabled"
          value={telemetry.global_write_disabled ? 'yes' : 'no'}
        />
        <Metric label="RAG retrieval" value={String((readiness.rag as Record<string, unknown>).retrieval_enabled ?? '—')} />
        <Metric label="Debug API" value={readiness.debug_api_enabled ? 'enabled' : 'disabled'} />
      </CardContent>
    </Card>
  );
}

function TraceList({
  traces,
  selectedTraceId,
  onSelect,
}: {
  traces: DebugTraceRun[];
  selectedTraceId: string;
  onSelect: (traceId: string) => void;
}) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="text-sm font-semibold">Recent traces</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {traces.length === 0 ? (
          <p className="p-4 text-xs text-slate-500">No trace runs yet. Live /chat turns appear here after the trace spine ships.</p>
        ) : (
          <ul className="divide-y divide-slate-800/70">
            {traces.map((trace) => {
              const selected = selectedTraceId === trace.trace_id;
              const question = trace.question_preview ?? null;
              return (
                <li
                  key={trace.trace_id}
                  className={`cursor-pointer px-4 py-2.5 hover:bg-slate-900/50 ${selected ? 'bg-cyan-950/30' : ''}`}
                  onClick={() => onSelect(trace.trace_id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="line-clamp-2 text-xs font-medium text-slate-100">
                      {question ?? <span className="italic text-slate-500">No question captured (early exit)</span>}
                    </p>
                    <span
                      className="shrink-0 text-[0.65rem] text-slate-500"
                      title={formatExactTime(trace.started_at)}
                    >
                      {formatRelativeTime(trace.started_at)}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <span className={`rounded px-1.5 py-0.5 text-[0.6rem] font-medium ${statusTone(trace.status)}`}>
                      {trace.status ?? '—'}
                    </span>
                    {trace.selected_skill ? (
                      <span className="rounded bg-slate-800/70 px-1.5 py-0.5 text-[0.6rem] text-slate-300">
                        {trace.selected_skill}
                      </span>
                    ) : null}
                    {trace.llm_used ? (
                      <span className="rounded bg-violet-950/40 px-1.5 py-0.5 text-[0.6rem] text-violet-300">LLM</span>
                    ) : null}
                    {trace.mcp_used ? (
                      <span className="rounded bg-sky-950/40 px-1.5 py-0.5 text-[0.6rem] text-sky-300">MCP</span>
                    ) : null}
                    {typeof trace.duration_ms === 'number' ? (
                      <span className="text-[0.6rem] text-slate-500">{(trace.duration_ms / 1000).toFixed(1)}s</span>
                    ) : null}
                    <span className="ml-auto font-mono text-[0.6rem] text-slate-600">{trace.trace_id.slice(0, 8)}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function TraceTimelinePanel({ timeline }: { timeline: DebugTraceTimeline | null }) {
  const run = timeline?.run;
  const timelineJson = timeline ? JSON.stringify(timeline, null, 2) : '';
  const nodeNames = (timeline?.events ?? [])
    .filter((e) => e.kind === 'step')
    .map((e) => e.step_name)
    .filter((n): n is string => Boolean(n));
  return (
    <Card className="soc-panel">
      <CardHeader className="flex flex-row items-center justify-between gap-2 py-3">
        <CardTitle className="text-sm font-semibold">Query journey</CardTitle>
        {timeline ? <CopyButton value={timelineJson} label="Copy timeline" /> : null}
      </CardHeader>
      <CardContent>
        {!timeline ? (
          <p className="text-xs text-slate-500">Select a trace or paste a trace_id to load the question, answer, and node-by-node journey.</p>
        ) : (
          <div className="space-y-3">
            {run ? (
              <div className="space-y-2 rounded-md border border-slate-800/80 bg-slate-950/50 p-3 text-xs">
                <SummaryRow label="Question asked" value={run.question_preview} emptyHint="not captured (early exit)" />
                <SummaryRow label="Final answer" value={run.answer_preview} emptyHint="no answer returned" />
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <span className={`rounded px-1.5 py-0.5 text-[0.6rem] font-medium ${statusTone(run.status)}`}>
                    {run.status ?? '—'}
                  </span>
                  {run.selected_skill ? <MetaChip text={`skill: ${run.selected_skill}`} /> : null}
                  {run.answer_mode ? <MetaChip text={`why: ${run.answer_mode}`} /> : null}
                  <MetaChip text={`LLM: ${run.llm_used ? 'yes' : 'no'}`} />
                  <MetaChip text={`MCP: ${run.mcp_used ? 'yes' : 'no'}`} />
                  {typeof run.duration_ms === 'number' ? <MetaChip text={`${(run.duration_ms / 1000).toFixed(1)}s`} /> : null}
                </div>
                {nodeNames.length ? (
                  <p className="pt-1 text-[0.65rem] text-slate-500">
                    <span className="text-slate-400">Nodes traversed:</span> {nodeNames.join(' → ')}
                  </p>
                ) : null}
              </div>
            ) : null}
            <p className="text-[0.65rem] uppercase tracking-wide text-slate-500">Event spine ({timeline.events.length})</p>
            <div className="max-h-80 space-y-2 overflow-auto">
              {timeline.events.map((event, index) => (
                <TimelineRow key={`${event.kind}-${event.created_at}-${index}`} event={event} />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SummaryRow({ label, value, emptyHint }: { label: string; value?: string | null; emptyHint: string }) {
  return (
    <div>
      <p className="text-[0.6rem] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-slate-200">
        {value ? value : <span className="italic text-slate-500">{emptyHint}</span>}
      </p>
    </div>
  );
}

function MetaChip({ text }: { text: string }) {
  return <span className="rounded bg-slate-800/70 px-1.5 py-0.5 text-[0.6rem] text-slate-300">{text}</span>;
}

function TimelineRow({ event }: { event: DebugTraceEvent }) {
  const label = event.step_name ?? event.kind;
  return (
    <div className="rounded-md border border-slate-800/80 bg-slate-950/50 p-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{event.kind}</Badge>
        <span className="font-medium text-slate-200">{label}</span>
        {event.status ? <Badge variant="outline">{event.status}</Badge> : null}
        <span className="ml-auto font-mono text-[0.65rem] text-slate-500">{event.created_at ?? ''}</span>
      </div>
    </div>
  );
}

function BundlePanel({ bundle }: { bundle: DebugTraceBundle | null }) {
  const [copied, setCopied] = useState(false);
  const bundleJson = bundle ? JSON.stringify(bundle, null, 2) : '';

  const copyBundle = async () => {
    if (!bundleJson) return;
    try {
      await navigator.clipboard.writeText(bundleJson);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  const copyLabel = copied ? 'Copied' : 'Copy bundle';

  return (
    <Card className="soc-panel min-w-0 max-w-full overflow-hidden">
      <CardHeader className="flex flex-row flex-wrap items-center gap-2 space-y-0 p-5 py-3">
        <CardTitle className="text-sm font-semibold">Debug bundle</CardTitle>
        {bundle ? (
          <Button type="button" size="sm" variant="default" className="shrink-0" onClick={() => void copyBundle()}>
            {copied ? <Check className="mr-1.5 h-3.5 w-3.5" /> : <Copy className="mr-1.5 h-3.5 w-3.5" />}
            {copyLabel}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="min-w-0 max-w-full">
        {!bundle ? (
          <p className="text-xs text-slate-500">Bundle JSON appears here for the selected trace (COE handoff artifact).</p>
        ) : (
          <div className="min-w-0 max-w-full overflow-hidden rounded-md border border-slate-800 bg-slate-950/70">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 bg-slate-900/60 px-3 py-2">
              <span className="min-w-0 truncate font-mono text-[0.65rem] text-slate-500">{bundle.trace_id}</span>
              <Button type="button" size="sm" variant="outline" className="shrink-0" onClick={() => void copyBundle()}>
                {copied ? <Check className="mr-1.5 h-3.5 w-3.5 text-emerald-400" /> : <Copy className="mr-1.5 h-3.5 w-3.5" />}
                {copyLabel}
              </Button>
            </div>
            <pre className="max-h-[28rem] overflow-auto p-3 text-[0.7rem] leading-relaxed text-slate-300">
              {bundleJson}
            </pre>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-slate-500">{label}</p>
      <p className="mt-0.5 font-medium text-slate-100">{value}</p>
    </div>
  );
}

function NoticeCard({ title, detail }: { title: string; detail: string }) {
  return (
    <Card className="border-amber-500/30 bg-amber-950/20">
      <CardContent className="flex gap-3 py-4 text-sm text-amber-100">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-medium">{title}</p>
          <p className="mt-1 text-xs text-amber-100/80">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}
