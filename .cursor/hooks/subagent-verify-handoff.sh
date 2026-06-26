#!/usr/bin/env bash
# After implementer/generalPurpose/shell subagent stops: nudge parent to verify
# only when meaningful code changes exist in the working tree.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/handoff-common.sh
source "$(dirname "$0")/lib/handoff-common.sh"

input="$(cat)"
subagent_type="$(echo "$input" | jq -r '.subagent_type // .type // "unknown"')"

if ! should_verify_followup "$ROOT"; then
  exit 0
fi

jq -n \
  --arg type "$subagent_type" \
  --arg msg "Subagent ($type) finished and the repo has uncommitted code changes. Review its diff against AGENTS.md playbook items 1–3 and 12–15. Run targeted tests for changed files before accepting. See .cursor/last-handoff.md." \
  '{followup_message: $msg}'
