#!/usr/bin/env bash
# After Cursor agent completes: write handoff artifact; verify follow-up only when
# the user armed verify by typing "test this" in the prompt AND there are meaningful
# uncommitted code changes (backend/frontend/scripts/tests).
# Hard-disable all follow-ups: touch .cursor/hooks/DISABLE_VERIFY_ON_STOP
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

deploy_md="$(deploy_actions_markdown "$ROOT")"
deploy_followup="$(deploy_actions_followup_summary "$ROOT")"

verify_armed=0
if is_verify_requested "$ROOT"; then
  verify_armed=1
fi

if [[ "$meaningful" -eq 1 && "$verify_armed" -eq 1 ]]; then
  cat >"$HANDOFF" <<EOF_HANDOFF
# Agent handoff — $ts

**Cursor session ended** (\`status=$status\`, \`id=$conversation_id\`).

**Verify recommended** — you typed **test this** and uncommitted code changes were detected.

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
5. **Frontend tests** (if \`frontend/\` touched):
   \`\`\`bash
   cd frontend && npm run build
   \`\`\`
6. **Commit hygiene** — no \`.env\`, no accidental eval baseline drift unless task was to refresh baselines.
7. **Report** — list commands run and pass/fail counts in the PR or reply.

### Prod deploy (when required)

$deploy_md

### Suggested verify prompt (paste into Claude/Codex)

> Review the uncommitted diff against AGENTS.md playbook. Run targeted tests for touched paths. Run prod deploy steps from the handoff if required. Report gaps, deferrals, and verification results. Do not commit unless I ask.

EOF_HANDOFF
elif [[ "$meaningful" -eq 1 ]]; then
  cat >"$HANDOFF" <<EOF_HANDOFF
# Agent handoff — $ts

**Cursor session ended** (\`status=$status\`, \`id=$conversation_id\`).

**Verify not armed** — code changed but your prompt did not include **test this**, so no automatic verify loop ran.

Type **test this** when you want verify + prod deploy checks. Example: *test this — review the diff and run pytest*.

### Touched code paths

$changed_list
EOF_HANDOFF
else
  cat >"$HANDOFF" <<EOF_HANDOFF
# Agent handoff — $ts

**Cursor session ended** (\`status=$status\`, \`id=$conversation_id\`).

**Verify not required** — no uncommitted changes under \`backend/\`, \`frontend/\`, \`scripts/\`, or \`test_harness/\`.

Docs-only or read-only session. Type **test this** when you want automatic verify + deploy steps on code changes.

See \`AGENTS.md\` playbook when you do touch backend/frontend.
EOF_HANDOFF
fi

followup=0
if should_verify_followup "$ROOT"; then
  followup=1
fi

disarm_verify_request "$ROOT"

if [[ "$followup" -ne 1 ]]; then
  exit 0
fi

jq -n --arg deploy "$deploy_followup" --arg msg "$(cat <<PROMPT
Verification handoff (AGENTS.md): You typed "test this" and uncommitted code changes are present. Review the diff against the Agent Execution Playbook, run targeted pytest for touched backend files, governance regression if control-plane/routing changed, and frontend build/tests if frontend changed. Prod deploy: $deploy_followup Report commands and pass/fail. Do not commit or git push unless asked. Details: \`.cursor/last-handoff.md\`.
PROMPT
)" '{followup_message: $msg}'
