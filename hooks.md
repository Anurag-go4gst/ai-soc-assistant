# hooks.md

Hook policy for this repository — **Cursor project hooks** (active) plus **optional Git pre-commit** (manual install).

Canonical agent rules: [`AGENTS.md`](AGENTS.md) (Agent Execution Playbook). Hooks automate guardrails and verification handoff; they do not replace reading that playbook.

## Cursor project hooks (active)

Config: [`.cursor/hooks.json`](.cursor/hooks.json)  
Scripts: [`.cursor/hooks/`](.cursor/hooks/)

Cursor reloads `hooks.json` on save. If hooks do not fire, restart Cursor and check **Settings → Hooks** or the **Hooks** output channel.

| Event | Script | Purpose |
|-------|--------|---------|
| `stop` | `stop-verify-handoff.sh` | Always updates [`.cursor/last-handoff.md`](.cursor/last-handoff.md). **Verify follow-up** (`loop_limit: 1`) only when uncommitted changes exist under `backend/`, `frontend/`, `scripts/`, or `test_harness/` — not on docs-only or read-only turns |
| `subagentStop` | `subagent-verify-handoff.sh` | Same gating: nudge parent to verify only when meaningful code changes are present |
| `beforeShellExecution` | `before-shell-guardrails.sh` | Block force-push to main/master, `git config` changes; ask on broad `git add` / public docker publish |
| `preToolUse` (Write/ApplyPatch/EditNotebook) | `block-secret-paths.sh` | Deny writes to `.env`, credential-like paths (`failClosed: true`) |

### Verify follow-up gating (default)

Follow-up verify turns on `stop` / `subagentStop` run **only** when the working tree has uncommitted changes under:

- `backend/`
- `frontend/`
- `scripts/`
- `test_harness/`

Docs-only edits (`AGENTS.md`, `plans/`, `docs/evals/`, etc.), restarts, and Q&A turns do **not** inject an extra verify loop.

The handoff file still updates every stop (short “verify not required” note when no code paths changed).

### Disable all verify follow-ups

```bash
touch .cursor/hooks/DISABLE_VERIFY_ON_STOP
```

Remove the file to re-enable gated follow-ups. Shared logic: `.cursor/hooks/lib/handoff-common.sh`.

### Cross-agent handoff (Cursor → Claude Code / Codex)

1. Cursor agent finishes → `stop` hook writes `.cursor/last-handoff.md`.
2. Open the same repo in Claude Code or Codex.
3. Paste the suggested verify prompt from that file, or ask: *"Follow `.cursor/last-handoff.md` and AGENTS.md playbook."*

Requires `jq` on the PATH for hook scripts (already used by guardrail scripts).

## Optional Git pre-commit hook

Script: [`scripts/hooks/run-pre-commit-checks.sh`](scripts/hooks/run-pre-commit-checks.sh)

**Not installed by default.** Install only when you want commit-time checks for all tools (not just Cursor):

```bash
chmod +x scripts/hooks/run-pre-commit-checks.sh
ln -sf ../../scripts/hooks/run-pre-commit-checks.sh .git/hooks/pre-commit
```

What it does on `git commit`:

- **Fail** if `.env` is staged
- **Fail** if staged diff matches private-key / bearer-token / session-secret patterns
- **Warn** on execution-boundary patterns (MCP exec flags, tool calling, etc.)
- **Warn** (non-blocking) if fast backend smoke tests fail when `backend/` is staged
- **Fail** if `frontend/` is staged and `npm run build` fails

`npm run build` runs `postbuild` (`chmod -R a+rX dist`) so Nginx (`www-data`) can serve production static files — without it the public site returns 403.

Uninstall: `rm .git/hooks/pre-commit`

## Manual pre-commit checks (no Git hook)

Run focused checks based on touched files:

- Backend Python changes:
  ```bash
  cd backend
  PYTHONPATH=../backend:.. python3 -m pytest
  ```

- Frontend TypeScript/React changes:
  ```bash
  cd frontend
  npm run build
  ```

- Control plane / intent changes:
  ```bash
  ./scripts/run_stage3_governance_regression.sh
  PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check
  ```

- Test harness or execution-boundary changes:
  ```bash
  PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json
  TELEMETRY_MODE=none PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json
  ```

## Secret guardrails

Reject commits that include:

- `.env`
- API keys, bearer tokens, session secrets, passwords, or private keys
- raw URLs containing credentials
- status payloads that expose secret values instead of configured booleans

Useful scan patterns:

```bash
git diff --cached --name-only
git diff --cached | grep -Ei 'api[_-]?key|bearer |password|token|session_secret|-----BEGIN'
```

Manual review is still required because placeholder examples may intentionally contain names such as `API_KEY=` with empty or fake values.

## Stage boundary guardrails

Until a later stage explicitly enables execution, review staged diffs for accidental additions of:

- SPL execution (beyond governed candidate generation)
- MCP tool execution
- final LLM synthesis enabled without COE approval
- Splunk telemetry write paths
- direct LLM-to-MCP tool calling (`supports_tool_calling: true`)

Useful scan:

```bash
git diff --cached | grep -Ei 'execute_validated_spl|run_query|complete_synthesis|record_mcp_execution|splunk_write|tool_calling.*true|MCP_GLOBAL_EXECUTION_ENABLED\s*=\s*true'
```

## Commit message convention

Use concise imperative messages:

- `Add workflow planning after skill routing`
- `Add multi-MCP and multi-LLM readiness registry`
- `Update agent guidance for readiness stages`

## Hook layers (summary)

| Layer | Scope | When it runs |
|-------|-------|--------------|
| `AGENTS.md` playbook | All agents | Every session (read manually) |
| Cursor hooks | Cursor agent | During edit / shell / stop |
| Git pre-commit | Any client | On `git commit` (optional) |
| CI / PR checks | Remote | On push (existing repo CI) |
