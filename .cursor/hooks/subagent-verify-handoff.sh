#!/usr/bin/env bash
# After implementer/generalPurpose/shell subagent stops: nudge parent to verify
# only when meaningful code changes exist and user typed "test this".
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/handoff-common.sh
source "$(dirname "$0")/lib/handoff-common.sh"

input="$(cat)"
subagent_type="$(echo "$input" | jq -r '.subagent_type // .type // "unknown"')"
deploy_followup="$(deploy_actions_followup_summary "$ROOT")"

if ! should_verify_followup "$ROOT"; then
  exit 0
fi

jq -n \
  --arg type "$subagent_type" \
  --arg deploy "$deploy_followup" \
  --arg msg "Subagent ($type) finished after you typed test this; uncommitted code changes remain. Review diff against AGENTS.md playbook items 1–3 and 12–15. Run targeted tests. Prod deploy: $deploy Follow .cursor/last-handoff.md." \
  '{followup_message: $msg}'
