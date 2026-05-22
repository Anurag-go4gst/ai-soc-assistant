import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Bug, ShieldCheck } from 'lucide-react';
import { AlertList } from '@/components/AlertList';
import { ApprovalPanel } from '@/components/ApprovalPanel';
import { ChatPanel } from '@/components/ChatPanel';
import { EvidencePanel } from '@/components/EvidencePanel';
import { GraphContextPanel } from '@/components/GraphContextPanel';
import { SopReferencePanel } from '@/components/SopReferencePanel';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { PlaceholderResponse } from '@/types/api';

export function SocCockpit() {
  const [lastTrace, setLastTrace] = useState<PlaceholderResponse | null>(null);

  return (
    <div className="grid h-full min-h-0 grid-cols-1 gap-4 p-4 lg:grid-cols-[19rem_minmax(0,1fr)_22rem] lg:p-5">
      {/* Left column: alerts + scenario state */}
      <ScrollArea className="hidden h-full lg:block">
        <div className="space-y-4 pr-2">
          <AlertList />
          <Card className="soc-panel">
            <CardHeader className="py-3">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                <Activity className="h-4 w-4 text-cyan-400" />
                Scenario State
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-300">
              <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
                <Badge variant="destructive">Critical</Badge>
                <p className="mt-2">Selected: brute-force login spike from VPN segment.</p>
              </div>
              {lastTrace ? (
                <div className="rounded-md border border-cyan-500/25 bg-cyan-500/8 p-3">
                  <Badge>Latest trace</Badge>
                  <p className="mt-2 break-all font-mono text-[0.7rem] text-cyan-100">{lastTrace.trace_id}</p>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </ScrollArea>

      {/* Center column: chat + trace summary */}
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="min-h-0 flex-1">
          <ChatPanel onTrace={setLastTrace} compactHeader />
        </div>
        <TraceSummaryStrip trace={lastTrace} />
      </div>

      {/* Right column: context tabs */}
      <Card className="soc-panel hidden h-full min-h-0 flex-col overflow-hidden lg:flex">
        <Tabs defaultValue="evidence" className="flex h-full min-h-0 flex-col">
          <TabsList className="mx-3 mt-3 justify-start overflow-x-auto">
            <TabsTrigger value="evidence">Evidence</TabsTrigger>
            <TabsTrigger value="sop">SOP</TabsTrigger>
            <TabsTrigger value="graph">Graph</TabsTrigger>
            <TabsTrigger value="mitre">MITRE</TabsTrigger>
            <TabsTrigger value="approval">Approval</TabsTrigger>
          </TabsList>
          <div className="min-h-0 flex-1 overflow-hidden">
            <ScrollArea className="h-full">
              <div className="space-y-3 p-3">
                <TabsContent value="evidence" className="m-0">
                  <EvidencePanel />
                </TabsContent>
                <TabsContent value="sop" className="m-0">
                  <SopReferencePanel />
                </TabsContent>
                <TabsContent value="graph" className="m-0">
                  <GraphContextPanel />
                </TabsContent>
                <TabsContent value="mitre" className="m-0">
                  <Card className="soc-panel">
                    <CardHeader className="py-3">
                      <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                        <ShieldCheck className="h-4 w-4 text-cyan-400" /> MITRE Mapping
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-wrap gap-2">
                      <Badge variant="warning">T1110 Brute Force</Badge>
                      <Badge variant="secondary">T1078 Valid Accounts</Badge>
                    </CardContent>
                  </Card>
                </TabsContent>
                <TabsContent value="approval" className="m-0">
                  <ApprovalPanel />
                </TabsContent>
              </div>
            </ScrollArea>
          </div>
        </Tabs>
      </Card>
    </div>
  );
}

function TraceSummaryStrip({ trace }: { trace: PlaceholderResponse | null }) {
  return (
    <Card className="soc-panel shrink-0">
      <CardContent className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs">
        <div className="flex flex-wrap items-center gap-3 text-slate-400">
          <span className="soc-eyebrow">Trace</span>
          <span>
            Route: <span className="font-medium text-slate-200">{trace?.selected_skill ?? '—'}</span>
          </span>
          <span>
            Confidence:{' '}
            <span className="font-medium text-slate-200">
              {typeof trace?.confidence === 'number' ? trace.confidence.toFixed(2) : '—'}
            </span>
          </span>
          <span>
            Plan: <span className="font-medium text-slate-200">{trace?.tool_plan?.join(' → ') ?? '—'}</span>
          </span>
          <span>
            Compare:{' '}
            <span className="font-medium text-slate-200">
              {typeof trace?.disagreement === 'boolean' ? (trace.disagreement ? 'disagree' : 'agree') : '—'}
            </span>
          </span>
        </div>
        <Link
          to="/debug"
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-900/70 px-2.5 py-1 font-medium text-slate-200 hover:border-cyan-500/50 hover:text-cyan-100"
        >
          <Bug className="h-3.5 w-3.5" />
          Open Debug
        </Link>
      </CardContent>
    </Card>
  );
}
