import { useEffect, useState } from 'react';
import { UserCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { getCurrentUser, updateUserProfile } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { AuthResponse } from '@/types/api';

export function UserProfilePanel() {
  const [user, setUser] = useState<AuthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .catch((err: Error) => toast.error(`Profile unavailable: ${err.message}`))
      .finally(() => setLoading(false));
  }, []);

  const toggleDebugAccess = async () => {
    if (!user?.authenticated) return;
    setSaving(true);
    try {
      const next = !user.debug_access;
      const updated = await updateUserProfile({ debug_access: next });
      setUser(updated);
      toast.success(next ? 'Debug observability enabled for your account' : 'Debug observability disabled for your account');
      window.dispatchEvent(new CustomEvent('ai-soc-profile-updated', { detail: updated }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Profile update failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="soc-panel">
        <CardContent className="py-6 text-sm text-slate-500">Loading profile…</CardContent>
      </Card>
    );
  }

  if (!user?.authenticated) {
    return (
      <Card className="soc-panel">
        <CardContent className="py-6 text-sm text-slate-500">Sign in to manage your profile.</CardContent>
      </Card>
    );
  }

  return (
    <Card className="soc-panel">
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <UserCircle2 className="h-4 w-4 text-cyan-300" />
          User profile
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-slate-300">
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <p className="text-xs text-slate-500">Username</p>
            <p className="mt-1 font-medium text-slate-100">{user.username}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Role</p>
            <p className="mt-1">
              <Badge variant="secondary">{user.role ?? 'analyst'}</Badge>
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Debug observability</p>
            <p className="mt-1">
              <Badge variant={user.debug_access ? 'success' : 'secondary'}>
                {user.debug_access ? 'enabled' : 'disabled'}
              </Badge>
            </p>
          </div>
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-950/60 p-4">
          <p className="font-medium text-slate-100">Telemetry &amp; debug access</p>
          <p className="mt-1 text-xs text-slate-500">
            Controls whether you can open the Debug page and call `/api/debug/*` (trace list, timeline, bundle,
            readiness). Your role stays the same; this is a per-user yes/no preference.
          </p>
          <Button className="mt-3" size="sm" variant="secondary" disabled={saving} onClick={() => void toggleDebugAccess()}>
            {user.debug_access ? 'Disable debug access' : 'Enable debug access'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
