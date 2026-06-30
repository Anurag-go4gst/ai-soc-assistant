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

if plan_path="$(plan_path_from_prompt "$ROOT" "$prompt" 2>/dev/null)"; then
  plan_source="prompt"
elif latest="$(latest_plan_file "$ROOT")" && [[ -n "$latest" ]]; then
  plan_path="$latest"
  plan_source="latest_mtime"
fi

followup=0
if should_loop_asap_followup "$ROOT"; then
  followup=1
fi

disarm_loop_asap "$ROOT"

if [[ "$followup" -ne 1 ]]; then
  exit 0
fi

audit_snippet=""
if [[ -n "$plan_path" && -x "$ROOT/.cursor/hooks/audit-plan-discipline.sh" ]]; then
  audit_snippet="$( "$ROOT/.cursor/hooks/audit-plan-discipline.sh" "$plan_path" 2>&1 || true )"
fi

plan_ref="${plan_path#$ROOT/}"
if [[ -z "$plan_ref" ]]; then
  plan_ref="(none — include plans/<file>.md in your loop-asap prompt)"
fi

fallback_note=""
if [[ "${plan_source:-}" == "latest_mtime" ]]; then
  fallback_note="Note: no plan path in prompt — used most recently edited plan under plans/ (excluding LOOP_RUNNER_*). Prefer: loop-asap — execute plans/<file>.md"
fi

jq -n \
  --arg plan "$plan_ref" \
  --arg audit "$audit_snippet" \
  --arg msg "$(cat <<PROMPT
Plan loop-asap (plan-discipline rule): You typed loop-asap. Target plan: $plan_ref.
$fallback_note

1. If the plan lacks atomic checklist items with **Verify:** per item, restructure it first (template: .cursor/templates/plan-checklist-template.md). Run: .cursor/hooks/audit-plan-discipline.sh $plan_ref
2. Sequence by dependency; pick the first unchecked item.
3. implement → verify (stated method) → check off with evidence → next item.
4. Stop only on decision-needed, same gate fails twice, or all items checked with evidence.
5. Re-audit all checkmarks before declaring the plan complete.

Audit snapshot:
$audit_snippet

Read AGENTS.md playbook. Do not commit unless asked.
PROMPT
)" '{followup_message: $msg}'
