import { DatabaseZap } from 'lucide-react';
import { GraphContextPanel } from '@/components/GraphContextPanel';
import { SopReferencePanel } from '@/components/SopReferencePanel';
import { ScrollArea } from '@/components/ui/scroll-area';

export function KnowledgePage() {
  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header>
          <p className="soc-eyebrow text-cyan-400">Knowledge</p>
          <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
            <DatabaseZap className="h-4 w-4 text-cyan-400" />
            SOPs and Graph Context
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Read-only view of approved SOPs and graph context. Ingestion lives in Settings → RAG.
          </p>
        </header>
        <div className="grid gap-4 md:grid-cols-2">
          <SopReferencePanel />
          <GraphContextPanel />
        </div>
      </div>
    </ScrollArea>
  );
}
