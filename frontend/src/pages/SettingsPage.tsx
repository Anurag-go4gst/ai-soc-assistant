import { Settings as SettingsIcon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

export function SettingsPage() {
  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header>
          <p className="soc-eyebrow text-cyan-400">Settings</p>
          <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
            <SettingsIcon className="h-4 w-4 text-cyan-400" />
            Configuration Surfaces
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Read-only snapshot of MCP / RAG / LLM / Routing / Safeguards / Observability config.
          </p>
        </header>
        <Card className="soc-panel">
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-semibold">Coming next</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-400">
            Settings panels land in the next commit.
          </CardContent>
        </Card>
      </div>
    </ScrollArea>
  );
}
