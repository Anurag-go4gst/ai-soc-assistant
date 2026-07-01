#!/usr/bin/env bash
# Arm loop-asap and plan-create discipline flags from user prompt.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/plan-discipline-common.sh
source "$(dirname "$0")/lib/plan-discipline-common.sh"

input="$(cat)"
prompt="$(echo "$input" | jq -r '.prompt // .text // .user_message // .message // empty')"

# Hook-injected stop follow-ups contain "loop-asap" in the body — never re-arm from those.
if is_loop_asap_hook_followup_prompt "$prompt"; then
  exit 0
fi

if is_loop_asap_stop_prompt "$prompt"; then
  disarm_loop_asap "$ROOT"
  exit 0
fi

if is_user_loop_asap_arm_prompt "$prompt"; then
  plan_path=""
  if plan_path="$(resolve_loop_asap_plan_for_arm "$ROOT" "$prompt" 2>/dev/null)"; then
    arm_loop_asap "$ROOT" "$plan_path"
  else
    arm_loop_asap "$ROOT"
  fi
else
  disarm_loop_asap "$ROOT"
fi

if [[ -n "$prompt" ]] && echo "$prompt" | grep -Eiq '(create|write|draft|new|author).{0,40}\bplan\b|\bplan\b.{0,40}(create|write|draft)'; then
  arm_plan_create "$ROOT"
else
  disarm_plan_create "$ROOT"
fi

exit 0
