import { useEffect, useState } from 'react';
import { AlertTriangle, ClipboardCheck, RefreshCcw } from 'lucide-react';
import { getQualityFlaggedTurns } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { QualityFlaggedTurn, QualityFlaggedTurnsResponse } from '@/types/api';

type LoadState = 'loading' | 'ready' | 'empty' | 'unavailable' | 'error';

export function QualityPage() {
  const [state, setState] = useState<LoadState>('loading');
  const [data, setData] = useState<QualityFlaggedTurnsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadFlaggedTurns = async () => {
    setState('loading');
    setError(null);
    try {
      const result = await getQualityFlaggedTurns(50);
      setData(result);
      setState(result.turns.length ? 'ready' : 'empty');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Quality queue unavailable';
      setError(message);
      setState(message.includes('404') ? 'unavailable' : 'error');
    }
  };

  useEffect(() => {
    void loadFlaggedTurns();
  }, []);

  const turns = data?.turns ?? [];

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="soc-eyebrow text-cyan-400">Quality</p>
            <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
              <ClipboardCheck className="h-4 w-4 text-cyan-400" />
              Answer Review Queue
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Flagged answer turns for analyst review and golden-regression promotion.
            </p>
          </div>
          <Button size="sm" variant="secondary" disabled={state === 'loading'} onClick={() => void loadFlaggedTurns()}>
            <RefreshCcw className={state === 'loading' ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'} />
            Refresh
          </Button>
        </header>

        <section className="grid gap-3 md:grid-cols-3">
          <MetricCard label="Flagged turns" value={String(data?.count ?? turns.length)} />
          <MetricCard label="Visible queue" value={String(turns.length)} />
          <MetricCard label="Endpoint" value={state === 'unavailable' ? 'pending' : state === 'error' ? 'error' : 'ready'} />
        </section>

        {state === 'unavailable' ? (
          <NoticeCard
            tone="warning"
            title="Quality endpoint not available"
            detail="The frontend client is wired for /quality/flagged-turns. This page will populate when the backend route is enabled."
          />
        ) : null}

        {state === 'error' ? (
          <NoticeCard
            tone="error"
            title="Quality queue failed"
            detail={error ?? 'The flagged-turn queue could not be loaded.'}
          />
        ) : null}

        {state === 'empty' ? (
          <NoticeCard
            tone="neutral"
            title="No flagged turns"
            detail="There are no down-rated answer turns in the current review queue."
          />
        ) : null}

        {state === 'loading' ? (
          <Card className="soc-panel">
            <CardContent className="flex items-center gap-2 p-4 text-sm text-slate-400">
              <RefreshCcw className="h-4 w-4 animate-spin text-cyan-300" />
              Loading flagged answer turns…
            </CardContent>
          </Card>
        ) : null}

        {turns.length ? (
          <section className="space-y-3">
            {turns.map((turn) => (
              <FlaggedTurnRow key={turn.turn_id} turn={turn} />
            ))}
          </section>
        ) : null}
      </div>
    </ScrollArea>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="text-xs font-medium text-slate-400">{label}</CardTitle>
      </CardHeader>
      <CardContent className="pb-4 pt-0">
        <p className="font-mono text-xl font-semibold text-slate-100">{value}</p>
      </CardContent>
    </Card>
  );
}

function NoticeCard({ detail, title, tone }: { detail: string; title: string; tone: 'error' | 'neutral' | 'warning' }) {
  const badgeVariant = tone === 'error' ? 'destructive' : tone === 'warning' ? 'warning' : 'secondary';
  return (
    <Card className="soc-panel">
      <CardContent className="flex gap-3 p-4">
        <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-300" />
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">{title}</h3>
            <Badge variant={badgeVariant}>{tone}</Badge>
          </div>
          <p className="mt-1 text-sm text-slate-400">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function FlaggedTurnRow({ turn }: { turn: QualityFlaggedTurn }) {
  const latestFeedback = turn.latest_feedback ?? turn.feedback?.[0] ?? null;
  const answerPreview = turn.final_message ?? turn.analyst_summary ?? 'No answer preview saved.';
  const queryPreview = turn.user_query ?? 'No query captured.';

  return (
    <Card className="soc-panel">
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="warning">{turn.quality_status ?? 'flagged'}</Badge>
          {latestFeedback?.rating ? <Badge variant="secondary">rating {latestFeedback.rating}</Badge> : null}
          {turn.golden_candidate ? <Badge variant="success">golden candidate</Badge> : null}
          {turn.selected_skill ? <Badge variant="outline">{turn.selected_skill}</Badge> : null}
          <span className="ml-auto font-mono text-[0.7rem] text-slate-500">{formatDate(turn.created_at)}</span>
        </div>
        <div className="grid gap-3 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-[0.7rem] font-semibold uppercase text-slate-500">Question</p>
            <p className="mt-1 text-sm leading-6 text-slate-100">{queryPreview}</p>
          </div>
          <div>
            <p className="text-[0.7rem] font-semibold uppercase text-slate-500">Answer Preview</p>
            <p className="mt-1 line-clamp-3 text-sm leading-6 text-slate-300">{answerPreview}</p>
          </div>
        </div>
        {latestFeedback?.remark ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/55 p-3 text-sm text-slate-300">
            <p className="text-[0.7rem] font-semibold uppercase text-slate-500">Analyst remark</p>
            <p className="mt-1 leading-6">{latestFeedback.remark}</p>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[0.7rem] text-slate-500">
          <span>turn {turn.turn_id}</span>
          {turn.trace_id ? <span>trace {turn.trace_id}</span> : null}
          {turn.selected_use_case_id ? <span>use_case {turn.selected_use_case_id}</span> : null}
          {turn.response_mode ? <span>mode {turn.response_mode}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function formatDate(value?: string | null) {
  if (!value) return 'time unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
