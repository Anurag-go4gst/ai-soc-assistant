import { useState } from 'react';
import { AlertTriangle, Server } from 'lucide-react';
import { toast } from 'sonner';
import { selectEnvProfile } from '@/api/client';
import { SettingRow } from '@/components/settings/SettingRow';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { EnvProfileStatus } from '@/types/api';

interface EnvProfileSettingsPanelProps {
  deployment: EnvProfileStatus | undefined;
  onRefresh?: () => void;
}

export function EnvProfileSettingsPanel({ deployment, onRefresh }: EnvProfileSettingsPanelProps) {
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);

  if (!deployment) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Deployment profile</CardTitle>
          <CardDescription>Environment profile status unavailable.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const activeId = deployment.active_profile_id;
  const selected = pendingId ?? activeId;

  async function applyProfile() {
    if (!selected || selected === activeId) return;
    setApplying(true);
    try {
      const result = await selectEnvProfile(selected);
      toast.success(`Profile "${result.profile_id}" saved. Restart backend to apply.`);
      if (result.root_env_error) {
        toast.warning(`Could not update root .env: ${result.root_env_error}`);
      }
      setPendingId(null);
      onRefresh?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to select profile');
    } finally {
      setApplying(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Server className="h-4 w-4 text-cyan-400" />
          Deployment profile
        </CardTitle>
        <CardDescription>
          Choose which environment file Docker Compose loads (
          <code className="text-xs">env/profiles/&lt;profile&gt;.env.example</code>
          ). Secrets stay in repo-root <code className="text-xs">.env</code>.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[240px] flex-1 space-y-1">
            <p className="text-xs text-slate-500">Active profile</p>
            <select
              id="env-profile-select"
              className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
              value={selected}
              onChange={(event) => setPendingId(event.target.value)}
            >
              {deployment.profiles.map((profile) => (
                <option key={profile.id} value={profile.id} disabled={!profile.example_exists}>
                  {profile.label}
                  {!profile.example_exists ? ' (missing file)' : ''}
                </option>
              ))}
            </select>
          </div>
          <Button
            type="button"
            disabled={applying || !selected || selected === activeId}
            onClick={() => void applyProfile()}
          >
            {applying ? 'Saving…' : 'Apply profile'}
          </Button>
        </div>

        {deployment.profiles
          .filter((p) => p.id === selected)
          .map((profile) => (
            <p key={profile.id} className="text-xs text-slate-400">
              {profile.description}
            </p>
          ))}

        <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100/90">
          <div className="mb-1 flex items-center gap-2 font-medium text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5" />
            Restart required
          </div>
          {deployment.reload_note}
          <pre className="mt-2 overflow-x-auto rounded bg-black/30 p-2 font-mono text-[11px] text-slate-300">
            docker compose up -d --force-recreate backend
          </pre>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <SettingRow label="Loaded profile id" value={activeId} mono />
          <SettingRow
            label="Profile file"
            value={deployment.profile_example_exists ? deployment.profile_example_path : 'missing'}
            mono
          />
          <SettingRow label="Active marker" value={deployment.active_profile_file} mono />
          <SettingRow label="Secrets file" value={deployment.root_env_path} mono />
        </div>

        {activeId === 'coe' ? (
          <Badge variant="secondary">COE LLM: http://10.52.1.13:8002/v1 · foundation-sec-8b-reasoning</Badge>
        ) : null}
      </CardContent>
    </Card>
  );
}
