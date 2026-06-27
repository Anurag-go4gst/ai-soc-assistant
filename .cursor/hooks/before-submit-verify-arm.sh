#!/usr/bin/env bash
# Arm verify follow-up only when the user prompt contains "test this".
# Clears the arm flag on normal prompts so verify hooks stay off by default.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/handoff-common.sh
source "$(dirname "$0")/lib/handoff-common.sh"

input="$(cat)"
prompt="$(echo "$input" | jq -r '.prompt // .text // .user_message // .message // empty')"

if [[ -n "$prompt" ]] && echo "$prompt" | grep -Eiq '\btest\s+this\b'; then
  arm_verify_request "$ROOT"
else
  disarm_verify_request "$ROOT"
fi

exit 0
