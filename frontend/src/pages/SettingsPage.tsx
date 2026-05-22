import { useEffect, useState } from 'react';
import { Settings as SettingsIcon, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { getSettingsStatus } from '@/api/client';
import { LlmSettingsPanel } from '@/components/settings/LlmSettingsPanel';
import { McpSettingsPanel } from '@/components/settings/McpSettingsPanel';
import { ObservabilityPanel } from '@/components/settings/ObservabilityPanel';
import { RagSettingsPanel } from '@/components/settings/RagSettingsPanel';
import { RoutingSettingsPanel } from '@/components/settings/RoutingSettingsPanel';
import { SafeguardsPanel } from '@/components/settings/SafeguardsPanel';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MOCK_SETTINGS_STATUS } from '@/mocks/settings';
import type { SettingsStatus } from '@/types/api';

export function SettingsPage() {
  const [status, setStatus] = useState<SettingsStatus>(MOCK_SETTINGS_STATUS);
  const [usingMock, setUsingMock] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getSettingsStatus()
      .then((live) => {
        if (cancelled) return;
        setStatus(live);
        setUsingMock(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        toast.error(`Settings status unavailable — using mock. (${err.message})`);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="soc-eyebrow text-cyan-400">Settings</p>
            <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
              <SettingsIcon className="h-4 w-4 text-cyan-400" />
              Configuration Surfaces
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Non-secret configuration status for MCP, RAG, LLM, Routing, Safeguards, and Observability.
              Edits and live connectors land in a later phase.
            </p>
          </div>
          {loading ? (
            <Badge variant="secondary">Loading…</Badge>
          ) : usingMock ? (
            <Badge variant="warning" className="gap-1">
              <AlertTriangle className="h-3 w-3" />
              Mock data (backend unreachable)
            </Badge>
          ) : (
            <Badge variant="success">Live status</Badge>
          )}
        </header>

        <Tabs defaultValue="mcp">
          <TabsList className="flex w-full justify-start overflow-x-auto">
            <TabsTrigger value="mcp">MCP</TabsTrigger>
            <TabsTrigger value="rag">RAG</TabsTrigger>
            <TabsTrigger value="llm">LLM</TabsTrigger>
            <TabsTrigger value="routing">Routing</TabsTrigger>
            <TabsTrigger value="safeguards">Safeguards</TabsTrigger>
            <TabsTrigger value="observability">Observability</TabsTrigger>
          </TabsList>
          <div className="mt-3">
            <TabsContent value="mcp" className="m-0">
              <McpSettingsPanel status={status.mcp} />
            </TabsContent>
            <TabsContent value="rag" className="m-0">
              <RagSettingsPanel status={status.rag} />
            </TabsContent>
            <TabsContent value="llm" className="m-0">
              <LlmSettingsPanel status={status.llm} />
            </TabsContent>
            <TabsContent value="routing" className="m-0">
              <RoutingSettingsPanel status={status.routing} />
            </TabsContent>
            <TabsContent value="safeguards" className="m-0">
              <SafeguardsPanel status={status.safeguards} />
            </TabsContent>
            <TabsContent value="observability" className="m-0">
              <ObservabilityPanel status={status.observability} />
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </ScrollArea>
  );
}
