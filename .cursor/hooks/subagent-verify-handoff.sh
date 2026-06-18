#!/usr/bin/env bash
# After implementer/generalPurpose/shell subagent stops: nudge parent to verify output.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DISABLE="$ROOT/.cursor/hooks/DISABLE_VERIFY_ON_STOP"

input="$(cat)"
subagent_type="$(echo "$input" | jq -r '.subagent_type // .type // "unknown"')"

if [[ -f "$DISABLE" ]]; then
  exit 0
fi

jq -n \
  --arg type "$subagent_type" \
  --arg msg "Subagent ($type) finished. Review its diff against AGENTS.md playbook items 1–3 and 12–15. Run targeted tests for changed files before accepting the result. See .cursor/last-handoff.md for the full checklist." \
  '{followup_message: $msg}'
