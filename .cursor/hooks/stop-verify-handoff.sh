#!/usr/bin/env bash
# After Cursor agent completes: write handoff artifact; verify follow-up only when
# there are meaningful uncommitted code changes (backend/frontend/scripts/tests).
# Disable all follow-ups: touch .cursor/hooks/DISABLE_VERIFY_ON_STOP
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/handoff-common.sh
source "$(dirname "$0")/lib/handoff-common.sh"

HANDOFF="$ROOT/.cursor/last-handoff.md"
mkdir -p "$(dirname "$HANDOFF")"

input="$(cat)"
status="$(echo "$input" | jq -r '.status // "unknown"')"
conversation_id="$(echo "$input" | jq -r '.conversation_id // .session_id // "unknown"')"
ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

meaningful=0
if has_meaningful_code_changes "$ROOT"; then
  meaningful=1
fi

changed_list="$(changed_code_paths "$ROOT" | sed 's/^/- /')"
if [[ -z "$changed_list" ]]; then
  changed_list="_(none under backend/, frontend/, scripts/, test_harness/)_"
fi

if [[ "$meaningful" -eq 1 ]]; then
  cat >"$HANDOFF" <<EOF_HANDOFF
# Agent handoff — $ts

**Cursor session ended** (\`status=$status\`, \`id=$conversation_id\`).

**Verify recommended** — uncommitted code changes detected.

### Touched code paths

$changed_list

## For Claude Code / Codex / next agent

Read \`AGENTS.md\` **Agent Execution Playbook** before changing anything.

### Verify before marking done

1. **Repo vs plan** — grep for existing code; do not recreate completed work.
2. **Targeted tests** — pytest on every touched package.
3. **Intent / control plane** — if routing/intent changed:
   \`\`\`bash
   cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_advisory_promotion.py app/tests/test_cisco_intent_distribution.py app/tests/test_query_to_intent.py -q
   PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check
   \`\`\`
4. **Governance gate** (control-plane or cross-cutting changes):
   \`\`\`bash
   ./scripts/run_stage3_governance_regression.sh
   \`\`\`
5. **Frontend** (if \`frontend/\` touched):
   \`\`\`bash
   cd frontend && npm run build
   \`\`\`
6. **Commit hygiene** — no \`.env\`, no accidental eval baseline drift unless task was to refresh baselines.
7. **Report** — list commands run and pass/fail counts in the PR or reply.

### Suggested verify prompt (paste into Claude/Codex)

> Review the uncommitted diff against AGENTS.md playbook. Run targeted tests for touched paths. Report gaps, deferrals, and verification results. Do not commit unless I ask.

EOF_HANDOFF
else
  cat >"$HANDOFF" <<EOF_HANDOFF
# Agent handoff — $ts

**Cursor session ended** (\`status=$status\`, \`id=$conversation_id\`).

**Verify not required** — no uncommitted changes under \`backend/\`, \`frontend/\`, \`scripts/\`, or \`test_harness/\`.

Docs-only or read-only session. Run targeted tests only when you later change code paths.

See \`AGENTS.md\` playbook when you do touch backend/frontend.
EOF_HANDOFF
fi

if ! should_verify_followup "$ROOT"; then
  exit 0
fi

jq -n --arg msg "$(cat <<'PROMPT'
Verification handoff (AGENTS.md): Uncommitted code changes are present. Before finishing, review the diff against the Agent Execution Playbook, run targeted pytest for touched backend files, governance regression if control-plane/routing changed, and `cd frontend && npm run build` if frontend changed. Report commands and pass/fail. Do not commit unless asked. Details: `.cursor/last-handoff.md`.
PROMPT
)" '{followup_message: $msg}'
