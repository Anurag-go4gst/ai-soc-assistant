#!/usr/bin/env bash
# Arm loop-asap and plan-create discipline flags from user prompt.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/plan-discipline-common.sh
source "$(dirname "$0")/lib/plan-discipline-common.sh"

input="$(cat)"
prompt="$(echo "$input" | jq -r '.prompt // .text // .user_message // .message // empty')"

if [[ -n "$prompt" ]] && echo "$prompt" | grep -Eiq '\bloop[\s-]?asap\b'; then
  arm_loop_asap "$ROOT"
else
  disarm_loop_asap "$ROOT"
fi

if [[ -n "$prompt" ]] && echo "$prompt" | grep -Eiq '(create|write|draft|new|author).{0,40}\bplan\b|\bplan\b.{0,40}(create|write|draft)'; then
  arm_plan_create "$ROOT"
else
  disarm_plan_create "$ROOT"
fi

exit 0
