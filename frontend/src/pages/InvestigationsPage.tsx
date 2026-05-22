import { FileSearch } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';

const MOCK_INVESTIGATIONS = [
  { id: 'INV-0001', title: 'Brute-force triage', status: 'Draft', owner: 'analyst' },
  { id: 'INV-0002', title: 'DB pool review', status: 'Draft', owner: 'analyst' },
  { id: 'INV-0003', title: 'OT anomaly watch', status: 'Draft', owner: 'analyst' },
];

export function InvestigationsPage() {
  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-4 lg:p-6">
        <header>
          <p className="soc-eyebrow text-cyan-400">Investigations</p>
          <h2 className="mt-1 flex items-center gap-2 text-lg font-semibold">
            <FileSearch className="h-4 w-4 text-cyan-400" />
            Open Cases
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Mock investigations — persistence and timeline view land in a later phase.
          </p>
        </header>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {MOCK_INVESTIGATIONS.map((item) => (
            <Card key={item.id} className="soc-panel">
              <CardHeader className="py-3">
                <CardTitle className="text-sm font-semibold">{item.title}</CardTitle>
                <p className="font-mono text-[0.7rem] text-slate-500">{item.id}</p>
              </CardHeader>
              <CardContent className="flex items-center justify-between text-xs text-slate-400">
                <Badge variant="secondary">{item.status}</Badge>
                <span>Owner: {item.owner}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </ScrollArea>
  );
}
