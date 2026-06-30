# hooks.md

Hook policy for this repository — **Cursor project hooks** (active) plus **optional Git pre-commit** (manual install).

Canonical agent rules: [`AGENTS.md`](AGENTS.md) (Agent Execution Playbook). Hooks automate guardrails and verification handoff; they do not replace reading that playbook.

## Cursor project hooks (active)

Config: [`.cursor/hooks.json`](.cursor/hooks.json)  
Scripts: [`.cursor/hooks/`](.cursor/hooks/)

Cursor reloads `hooks.json` on save. If hooks do not fire, restart Cursor and check **Settings → Hooks** or the **Hooks** output channel.

| Event | Script | Purpose |
|-------|--------|---------|
| `beforeSubmitPrompt` | `before-submit-verify-arm.sh` | Arms verify follow-up **only** when your prompt contains **`test this`** (case-insensitive) |
| `beforeSubmitPrompt` | `before-submit-plan-discipline-arm.sh` | Arms **`loop-asap`** when prompt contains `loop-asap` / `loop asap`; arms **plan-create** when prompt asks to create/write/draft a plan |
| `stop` | `stop-verify-handoff.sh` | Always updates [`.cursor/last-handoff.md`](.cursor/last-handoff.md). **Verify follow-up** (`loop_limit: 1`) only when you typed **`test this`** **and** uncommitted changes exist under `backend/`, `frontend/`, `scripts/`, or `test_harness/` |
| `stop` | `stop-loop-asap-handoff.sh` | **Plan loop follow-up** (`loop_limit: 5`) when you typed **`loop-asap`** — audits checklist gaps, continues implement→verify→check-off loop |
| `subagentStop` | `subagent-verify-handoff.sh` | Same opt-in gating as `stop` when meaningful code changes are present |
| `subagentStop` | `stop-loop-asap-handoff.sh` | Same **`loop-asap`** follow-up for implementer/generalPurpose/shell subagents |
| `postToolUse` (Write/ApplyPatch) | `post-plan-edit-reminder.sh` | Injects checklist-discipline context after editing `plans/*.md` |
| `beforeShellExecution` | `before-shell-guardrails.sh` | Block force-push to main/master, `git config` changes; ask on broad `git add` / public docker publish |
| `preToolUse` (Write/ApplyPatch/EditNotebook) | `block-secret-paths.sh` | Deny writes to `.env`, credential-like paths (`failClosed: true`) |

### Verify follow-up gating (opt-in via `test this`)

**Default: verify hooks are off.** No automatic verify loop after agent turns.

To arm verification for one turn, type **`test this`** in your prompt (case-insensitive), for example:

> test this — fix the wineventlog off-shift SPL and run pytest

The `beforeSubmitPrompt` hook sets a one-shot flag. When the agent stops, `stop` / `subagentStop` run the verify follow-up **only if both**:

1. You typed **`test this`** in that prompt, and
2. The working tree has uncommitted changes under `backend/`, `frontend/`, `scripts/`, or `test_harness/`

Normal Q&A, docs-only edits, and code changes without **`test this`** do **not** inject an extra verify loop.

The handoff file still updates every stop (notes whether verify was armed).

### Hard-disable all verify follow-ups (even with `test this`)

```bash
touch .cursor/hooks/DISABLE_VERIFY_ON_STOP
```

Remove the file to allow opt-in **`test this`** arming again. Shared logic: `.cursor/hooks/lib/handoff-common.sh`.

### Plan discipline (`loop-asap` + plan creation)

**Rule:** [`.cursor/rules/plan-discipline.mdc`](.cursor/rules/plan-discipline.mdc) (always on).  
**Template:** [`.cursor/templates/plan-checklist-template.md`](.cursor/templates/plan-checklist-template.md).  
**Audit script:** `.cursor/hooks/audit-plan-discipline.sh <plan-path>`.

When **creating a plan**, the agent must decompose into atomic checklist items, attach a **Verify** method to each, sequence by dependency, and document stop conditions — before writing code. Editing `plans/*.md` triggers `post-plan-edit-reminder.sh`.

When a plan is ready to execute, type **`loop-asap`** **with the plan path** (recommended):

> loop-asap — execute `plans/2026-06-29_conditional-pipeline-canonical-dispatch.md`

If you omit the path, the hook falls back to the most recently edited file under `plans/` (excluding `LOOP_RUNNER_*` and `*_TEMPLATE.md`).

The agent will:

1. Run the audit script and fix checklist gaps in the plan.
2. Loop: implement → verify (stated method) → check off with evidence → next item.
3. Stop only on decision-needed, same gate fails twice, or all items checked with evidence.

If the agent stops mid-loop, `stop-loop-asap-handoff.sh` injects up to **5** follow-up turns to continue.

**Hard-disable loop-asap follow-ups:**

```bash
touch .cursor/hooks/DISABLE_LOOP_ASAP_ON_STOP
```

Generic loop runner prompt pattern: [`plans/LOOP_RUNNER_TEMPLATE.md`](plans/LOOP_RUNNER_TEMPLATE.md).

### Prod deploy steps (included in `test this` verify)

When verify is armed, the handoff inspects changed paths and tells the agent which prod actions to run:

| Action | When (changed paths) |
|--------|----------------------|
| `cd frontend && npm run build` | `frontend/src/`, `index.html`, Tailwind/Vite/PostCSS config |
| `docker compose build && docker compose up -d` | `backend/pyproject.toml`, `Dockerfile`, `docker-compose*.yml`, `frontend/package.json` |
| `docker compose restart backend` | `backend/` only (if reload looks stale; dev uses uvicorn `--reload`) |
| `git push` | Branch ahead of upstream — remind only; **do not push unless user asks** |

Public site (Nginx) serves `frontend/dist`; API proxies to the Docker backend on this host.

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
| `AGENTS.md` § Plan discipline | All agents | Creating or executing `plans/`; canonical for Claude/Codex |
| `.cursor/rules/plan-discipline.mdc` | Cursor agent | Always — mirrors playbook; `loop-asap` |
| Cursor hooks | Cursor agent | During edit / shell / stop |
| Git pre-commit | Any client | On `git commit` (optional) |
| CI / PR checks | Remote | On push (existing repo CI) |
