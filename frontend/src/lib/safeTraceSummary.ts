import type { PlaceholderResponse } from '@/types/api';

export interface SafeControlPlaneSummary {
  canonicalStatus?: string;
  dispatchSource?: string;
  blockedAction?: {
    status?: string;
    blockClass?: string;
    reason?: string;
    safeMessage?: string;
  };
  llmCalls: string[];
  composerSkipReason?: string;
  composerFallbackReason?: string;
}

export function buildSafeControlPlaneSummary(trace: PlaceholderResponse): SafeControlPlaneSummary {
  const cp = (trace.control_plane_trace ?? {}) as Record<string, unknown>;
  const planDispatch = (cp.plan_dispatch ?? {}) as Record<string, unknown>;
  const blocked = (trace.blocked_action_state ?? cp.blocked_action_state ?? {}) as Record<string, unknown>;
  const composer = (cp.llm_composer ?? {}) as Record<string, unknown>;

  const llmCalls: string[] = [];
  const summary = Array.isArray(cp.llm_calls) ? (cp.llm_calls as Array<Record<string, unknown>>) : [];
  for (const row of summary) {
    const role = String(row.role ?? row.kind ?? 'llm');
    const outcome = row.outcome ? ` ${String(row.outcome)}` : '';
    llmCalls.push(`${role}${outcome}`);
  }

  return {
    canonicalStatus: planDispatch.canonical_status ? String(planDispatch.canonical_status) : undefined,
    dispatchSource: planDispatch.dispatch_source ? String(planDispatch.dispatch_source) : undefined,
    blockedAction:
      blocked.visible === true
        ? {
            status: blocked.status ? String(blocked.status) : undefined,
            blockClass: blocked.block_class ? String(blocked.block_class) : undefined,
            reason: blocked.reason ? String(blocked.reason) : undefined,
            safeMessage: blocked.safe_message ? String(blocked.safe_message) : undefined,
          }
        : undefined,
    llmCalls,
    composerSkipReason: composer.composer_skipped_reason ? String(composer.composer_skipped_reason) : undefined,
    composerFallbackReason:
      composer.provider_skip_reason ? String(composer.provider_skip_reason) :
      composer.llm_blocked_reason ? String(composer.llm_blocked_reason) :
      undefined,
  };
}
