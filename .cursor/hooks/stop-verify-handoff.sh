#!/usr/bin/env bash
# After Cursor agent completes: write handoff artifact + optional verify follow-up.
# Disable follow-up loop: touch .cursor/hooks/DISABLE_VERIFY_ON_STOP
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DISABLE="$ROOT/.cursor/hooks/DISABLE_VERIFY_ON_STOP"
HANDOFF="$ROOT/.cursor/last-handoff.md"
mkdir -p "$(dirname "$HANDOFF")"

input="$(cat)"
status="$(echo "$input" | jq -r '.status // "unknown"')"
conversation_id="$(echo "$input" | jq -r '.conversation_id // .session_id // "unknown"')"
ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat >"$HANDOFF" <<EOF
# Agent handoff — $ts

**Cursor session ended** (\`status=$status\`, \`id=$conversation_id\`).

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

EOF

if [[ -f "$DISABLE" ]]; then
  exit 0
fi

# Inject one follow-up turn so Cursor self-verifies before the user switches tools.
jq -n --arg msg "$(cat <<'PROMPT'
Verification handoff (AGENTS.md): Before finishing, review uncommitted changes against the Agent Execution Playbook. Run targeted pytest for touched backend files; run `./scripts/run_stage3_governance_regression.sh` if control-plane/routing changed; run `cd frontend && npm run build` if frontend changed. Report commands run and pass/fail. Do not commit unless the user asked. Handoff artifact: `.cursor/last-handoff.md`.
PROMPT
)" '{followup_message: $msg}'
