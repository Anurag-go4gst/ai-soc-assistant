import { ShieldAlert } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function ApprovalPanel() {
  return (
    <Card className="soc-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-amber-300" /> Approval Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Badge variant="warning">Human approval required</Badge>
        <p className="text-sm text-slate-400">SPL execution and containment actions remain gated in this scaffold.</p>
        <Button type="button" variant="outline" className="w-full">Request analyst approval</Button>
      </CardContent>
    </Card>
  );
}
