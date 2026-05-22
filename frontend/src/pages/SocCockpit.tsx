import { useEffect, useState } from 'react';
import { Activity, FileSearch, MessageSquareText, ShieldCheck } from 'lucide-react';
import { getHealth } from '@/api/client';
import { AlertList } from '@/components/AlertList';
import { AppShell } from '@/components/AppShell';
import { ApprovalPanel } from '@/components/ApprovalPanel';
import { ChatPanel } from '@/components/ChatPanel';
import { EvidencePanel } from '@/components/EvidencePanel';
import { GraphContextPanel } from '@/components/GraphContextPanel';
import { SopReferencePanel } from '@/components/SopReferencePanel';
import { SplTracePanel } from '@/components/SplTracePanel';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CompareResultPanel } from '@/components/debug/CompareResultPanel';
import { DeterministicRouterPanel } from '@/components/debug/DeterministicRouterPanel';
import { NodeTimeline } from '@/components/debug/NodeTimeline';
import { PlannerDecisionPanel } from '@/components/debug/PlannerDecisionPanel';
import { RouteAdjudicatorPanel } from '@/components/debug/RouteAdjudicatorPanel';
import type { SocSection } from '@/components/SideNav';
import type { HealthResponse, PlaceholderResponse } from '@/types/api';

interface SocCockpitProps {
  username: string;
  onLogout: () => Promise<void>;
}

export function SocCockpit({ username, onLogout }: SocCockpitProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<SocSection>('cockpit');
  const [lastTrace, setLastTrace] = useState<PlaceholderResponse | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <AppShell
      activeSection={activeSection}
      health={health}
      healthError={error}
      username={username}
      onLogout={onLogout}
      onSectionChange={setActiveSection}
    >
      <div className="space-y-5 p-4 lg:p-6">
        <section className="grid gap-4 xl:grid-cols-[22rem_minmax(0,1fr)_24rem]">
          <div className="space-y-4">
            <AlertList />
            <Card className="soc-panel">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-cyan-300" />
                  Scenario State
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                  <Badge variant="destructive">Critical</Badge>
                  <p className="mt-2">Selected: brute-force login spike from VPN segment.</p>
                </div>
                {lastTrace ? (
                  <div className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 p-3">
                    <Badge>Latest trace</Badge>
                    <p className="mt-2 font-mono text-xs text-cyan-100">{lastTrace.trace_id}</p>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <div className="min-w-0">
            <Tabs value={activeSection} onValueChange={(value) => setActiveSection(value as SocSection)}>
              <TabsList className="mb-4 flex w-full justify-start overflow-x-auto">
                {[
                  ['cockpit', 'Cockpit'],
                  ['chat', 'Chat'],
                  ['investigations', 'Investigations'],
                  ['scenarios', 'Scenarios'],
                  ['knowledge', 'Knowledge'],
                  ['debug', 'Debug'],
                ].map(([value, label]) => (
                  <TabsTrigger key={value} value={value}>{label}</TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="cockpit">
                <ChatPanel onTrace={setLastTrace} />
              </TabsContent>
              <TabsContent value="chat">
                <ChatPanel onTrace={setLastTrace} />
              </TabsContent>
              <TabsContent value="investigations">
                <Card className="soc-panel">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2"><FileSearch className="h-4 w-4 text-cyan-300" /> Investigations</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-2">
                    {['INV-0001 Brute-force triage', 'INV-0002 DB pool review', 'INV-0003 OT anomaly watch'].map((item) => (
                      <div key={item} className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
                        <Badge variant="secondary">Draft</Badge>
                        <p className="mt-3 font-semibold text-slate-100">{item}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </TabsContent>
              <TabsContent value="scenarios">
                <AlertList />
              </TabsContent>
              <TabsContent value="knowledge">
                <div className="grid gap-4 md:grid-cols-2">
                  <SopReferencePanel />
                  <GraphContextPanel />
                </div>
              </TabsContent>
              <TabsContent value="debug">
                <DebugGrid />
              </TabsContent>
            </Tabs>
          </div>

          <div className="space-y-4">
            <EvidencePanel />
            <SopReferencePanel />
            <GraphContextPanel />
            <Card className="soc-panel">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-cyan-300" /> MITRE Mapping</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Badge variant="warning">T1110 Brute Force</Badge>
                <Badge variant="secondary">T1078 Valid Accounts</Badge>
              </CardContent>
            </Card>
            <ApprovalPanel />
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.2fr_2fr]">
          <SplTracePanel />
          <DebugGrid />
        </section>
      </div>
    </AppShell>
  );
}

function DebugGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      <PlannerDecisionPanel />
      <DeterministicRouterPanel />
      <CompareResultPanel />
      <RouteAdjudicatorPanel />
      <NodeTimeline />
    </div>
  );
}
