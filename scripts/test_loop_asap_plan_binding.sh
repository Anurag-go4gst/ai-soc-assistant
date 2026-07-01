#!/usr/bin/env bash
# Smoke tests for loop-asap plan binding and stop conditions.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=../.cursor/hooks/lib/plan-discipline-common.sh
source "$ROOT/.cursor/hooks/lib/plan-discipline-common.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export ROOT_OVERRIDE="$TMP"
plan_a="$TMP/plans/plan-a.md"
plan_b="$TMP/plans/plan-b.md"
mkdir -p "$TMP/plans" "$TMP/.cursor/hooks"
printf '%s\n' '- [ ] **T1** — one' >"$plan_a"
printf '%s\n' '- [x] **T1** — done' >"$plan_b"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

# Hook follow-up must not count as user arm prompt
is_loop_asap_hook_followup_prompt "${LOOP_ASAP_HOOK_MARKER} Continue" || fail "hook followup detect"
is_user_loop_asap_arm_prompt "${LOOP_ASAP_HOOK_MARKER} Continue" && fail "hook followup should not arm"
is_user_loop_asap_arm_prompt "loop-asap — execute plans/plan-a.md" || fail "user arm detect"

# Arm binds plan path
arm_loop_asap "$TMP" "$plan_a"
loop_asap_bound_plan "$TMP" | grep -q 'plan-a.md' || fail "bound plan"
is_loop_asap_requested "$TMP" || fail "armed"

# Follow-up prompt must not re-arm via before-submit guard (simulated)
if is_user_loop_asap_arm_prompt "${LOOP_ASAP_HOOK_MARKER} You typed loop-asap"; then
  fail "hook body must not re-arm"
fi

# Completion stops loop
plan_execution_complete "$plan_b" || fail "plan-b complete"
plan_execution_complete "$plan_a" && fail "plan-a incomplete"

# Turn budget
arm_loop_asap "$TMP" "$plan_a"
for _ in 1 2 3 4 5; do
  increment_loop_asap_turn "$TMP"
done
loop_asap_turns_exhausted "$TMP" || fail "turns exhausted at 5"

# Active plan binding
bind_active_plan "$TMP" "plans/plan-a.md"
read_active_plan "$TMP" | grep -q 'plan-a.md' || fail "active plan read"

# Stop prompt disarms
arm_loop_asap "$TMP" "$plan_a"
is_loop_asap_stop_prompt "loop-asap stop" || fail "stop detect"
disarm_loop_asap "$TMP"
is_loop_asap_requested "$TMP" && fail "disarmed"

ok "loop-asap plan binding smoke tests passed"
