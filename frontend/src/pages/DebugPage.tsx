import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, Bug, RefreshCcw, Search } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import {
  getDebugReadiness,
  getDebugTraceBundle,
  getDebugTraceTimeline,
  getDebugTraces,
} from '@/api/client';
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

  useEffect(() => {
    void loadOverview();
  }, []);

  useEffect(() => {
    const fromUrl = searchParams.get('trace_id');
    if (fromUrl && pageState === 'ready' && fromUrl !== selectedTraceId) {
      setTraceInput(fromUrl);
      void loadTraceDetail(fromUrl);
    }
  }, [pageState, searchParams, selectedTraceId]);

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
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
          <Button size="sm" variant="secondary" disabled={pageState === 'loading'} onClick={() => void loadOverview()}>
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
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Activity className="h-4 w-4 text-cyan-300" />
          Readiness snapshot
        </CardTitle>
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
      <CardContent>
        {traces.length === 0 ? (
          <p className="text-xs text-slate-500">No trace runs yet. Live /chat turns appear here after the trace spine ships.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 pr-2">Trace</th>
                <th className="py-1 pr-2">Status</th>
                <th className="py-1 pr-2">Skill</th>
                <th className="py-1">Started</th>
              </tr>
            </thead>
            <tbody className="text-slate-300">
              {traces.map((trace) => (
                <tr
                  key={trace.trace_id}
                  className={`cursor-pointer border-t border-slate-800/70 hover:bg-slate-900/50 ${
                    selectedTraceId === trace.trace_id ? 'bg-cyan-950/30' : ''
                  }`}
                  onClick={() => onSelect(trace.trace_id)}
                >
                  <td className="py-1.5 pr-2 font-mono">{trace.trace_id.slice(0, 8)}</td>
                  <td className="py-1.5 pr-2">
                    <Badge variant="secondary">{trace.status ?? '—'}</Badge>
                  </td>
                  <td className="py-1.5 pr-2">{trace.selected_skill ?? '—'}</td>
                  <td className="py-1.5 font-mono text-[0.65rem]">{trace.started_at ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function TraceTimelinePanel({ timeline }: { timeline: DebugTraceTimeline | null }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="text-sm font-semibold">Event timeline</CardTitle>
      </CardHeader>
      <CardContent>
        {!timeline ? (
          <p className="text-xs text-slate-500">Select a trace or paste a trace_id to load the ordered event spine.</p>
        ) : (
          <div className="max-h-96 space-y-2 overflow-auto">
            {timeline.events.map((event, index) => (
              <TimelineRow key={`${event.kind}-${event.created_at}-${index}`} event={event} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
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
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="text-sm font-semibold">Debug bundle</CardTitle>
      </CardHeader>
      <CardContent>
        {!bundle ? (
          <p className="text-xs text-slate-500">Bundle JSON appears here for the selected trace (COE handoff artifact).</p>
        ) : (
          <pre className="max-h-[28rem] overflow-auto rounded-md border border-slate-800 bg-slate-950/70 p-3 text-[0.7rem] leading-relaxed text-slate-300">
            {JSON.stringify(bundle, null, 2)}
          </pre>
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
