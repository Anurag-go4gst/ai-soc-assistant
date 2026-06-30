import { BookOpen } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function SopReferencePanel() {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <BookOpen className="h-4 w-4 text-cyan-400" /> SOP References
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-slate-300">
        {['SOC-RB-104 Brute Force', 'Credential Attack Evidence Rules', 'Analyst Approval Before SPL Execute'].map((item) => (
          <div
            key={item}
            className="flex items-center gap-2.5 rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 transition hover:border-cyan-500/40 hover:bg-slate-900/60"
          >
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400/70" />
            {item}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
