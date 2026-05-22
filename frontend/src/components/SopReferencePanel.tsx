import { BookOpen } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function SopReferencePanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><BookOpen className="h-4 w-4 text-cyan-300" /> SOP References</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-slate-300">
        {['SOC-RB-104 Brute Force', 'Credential Attack Evidence Rules', 'Analyst Approval Before SPL Execute'].map((item) => (
          <div key={item} className="rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2">{item}</div>
        ))}
      </CardContent>
    </Card>
  );
}
