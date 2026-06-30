import { ShieldAlert } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function ApprovalPanel() {
  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <ShieldAlert className="h-4 w-4 text-amber-300" /> Approval Status
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="relative overflow-hidden rounded-lg border border-amber-400/25 bg-amber-500/[0.06] p-3 pl-4">
          <span className="absolute inset-y-0 left-0 w-1 bg-amber-400/80" />
          <Badge variant="warning">Human approval required</Badge>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">
            SPL execution and containment actions remain gated in this scaffold.
          </p>
        </div>
        <Button type="button" variant="outline" className="w-full transition hover:border-cyan-500/50 hover:text-cyan-100">
          Request analyst approval
        </Button>
      </CardContent>
    </Card>
  );
}
