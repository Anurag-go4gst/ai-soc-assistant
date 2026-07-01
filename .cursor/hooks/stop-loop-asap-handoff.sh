#!/usr/bin/env bash
# Continue plan execution loop when user armed loop-asap.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/plan-discipline-common.sh
source "$(dirname "$0")/lib/plan-discipline-common.sh"

input="$(cat)"
prompt="$(echo "$input" | jq -r '.user_message // .prompt // empty')"
plan_path=""
plan_source="none"
stop_reason=""

if ! should_loop_asap_followup "$ROOT"; then
  exit 0
fi

if plan_path="$(loop_asap_bound_plan "$ROOT" 2>/dev/null)"; then
  plan_source="bound"
elif plan_path="$(plan_path_from_prompt "$ROOT" "$prompt" 2>/dev/null)"; then
  plan_source="prompt"
elif plan_path="$(read_active_plan "$ROOT" 2>/dev/null)"; then
  plan_source="active_plan"
elif [[ -f "$ROOT/.cursor/hooks/ALLOW_LOOP_ASAP_LATEST_PLAN_FALLBACK" ]]; then
  if latest="$(latest_plan_file "$ROOT")" && [[ -n "$latest" ]]; then
    plan_path="$latest"
    plan_source="latest_mtime"
  fi
fi

if [[ -n "$plan_path" ]] && plan_execution_complete "$plan_path"; then
  disarm_loop_asap "$ROOT"
  exit 0
fi

if loop_asap_turns_exhausted "$ROOT"; then
  disarm_loop_asap "$ROOT"
  exit 0
fi

increment_loop_asap_turn "$ROOT"

audit_snippet=""
if [[ -n "$plan_path" && -x "$ROOT/.cursor/hooks/audit-plan-discipline.sh" ]]; then
  audit_snippet="$( "$ROOT/.cursor/hooks/audit-plan-discipline.sh" "$plan_path" 2>&1 || true )"
fi

plan_ref="${plan_path#$ROOT/}"
if [[ -z "$plan_ref" ]]; then
  plan_ref="(none — include plans/<file>.md in your loop-asap prompt, or edit the plan to set plans/.active-plan)"
  stop_reason="No target plan resolved. Loop-asap disarmed after this turn."
  disarm_loop_asap "$ROOT"
fi

fallback_note=""
if [[ "${plan_source:-}" == "latest_mtime" ]]; then
  fallback_note="Note: used ALLOW_LOOP_ASAP_LATEST_PLAN_FALLBACK + most recently edited plan under plans/. Prefer an explicit plan path."
fi

turn_note="Follow-up turn $(loop_asap_turn_count "$ROOT")/${LOOP_ASAP_MAX_TURNS} for this loop-asap session."

jq -n \
  --arg plan "$plan_ref" \
  --arg audit "$audit_snippet" \
  --arg turn "$turn_note" \
  --arg stop "$stop_reason" \
  --arg msg "$(cat <<PROMPT
${LOOP_ASAP_HOOK_MARKER} Continue executing plan: $plan_ref.
$turn_note
$fallback_note
$stop_reason

1. If the plan lacks atomic checklist items with **Verify:** per item, restructure it first (template: .cursor/templates/plan-checklist-template.md). Run: .cursor/hooks/audit-plan-discipline.sh $plan_ref
2. Sequence by dependency; pick the first unchecked item.
3. implement → verify (stated method) → check off with evidence → next item.
4. Stop when all checklist items are checked with evidence, a decision is needed, or the same gate fails twice.
5. Re-audit all checkmarks before declaring the plan complete.
6. User can type **loop-asap stop** to end the loop without more follow-ups.

Audit snapshot:
$audit_snippet

Read AGENTS.md playbook. Do not commit unless asked.
PROMPT
)" '{followup_message: $msg}'
