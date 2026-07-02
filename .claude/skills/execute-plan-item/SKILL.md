---
name: execute-plan-item
description: Execute one checklist item from a plans/*.md file in this repo with full evidence discipline — verify anchors, implement, run the item's Verify command verbatim, record Evidence, check the box. Use when executing any plan under plans/, when the user says "loop-asap", "execute the plan", "next item", or /execute-plan-item.
---

# execute-plan-item — one item, fully proven, then the next

Canonical rules live in `AGENTS.md` (§ Plan discipline) and the plan file itself. This skill turns them into a mechanical loop a fresh agent can follow without prior context. Work on exactly ONE checklist item at a time.

## Step 0 — Reconcile (every session, before anything)

```bash
cd /var/www/ai-soc-assistant
git status && git log --oneline -5     # user runs parallel agents; tree may have moved
cat .env | head -20                     # profile selector: AI_SOC_ENV_PROFILE=<name>
```
Read the plan's **User directives / Governance invariants / Decision gates / Drift log** sections before any item. If the tree contradicts the plan's assumptions, record it in the Drift log and stop.

## Step 1 — Pick the item

First unchecked item whose **Depends on** are all checked. Never skip ahead. If the item's dependency is unchecked and blocked, report why instead of starting something else.

## Step 2 — Verify the item's anchors (do not trust them)

For every file, symbol, test, flag, or line number the item cites:
```bash
ls <path>                                             # exists?
grep -rn "<symbol>" backend/app --include="*.py"      # real location (line numbers drift)
```
- Anchor says `file.py:~1410` — the `~` means approximate; grep for the function name, don't trust the number.
- Test file marked **NEW** in the plan → you create it. Not marked NEW → it must already exist; if it doesn't, STOP and record drift.
- If an anchor is wrong, fix your understanding first, then note the correction in the item's Evidence.

## Step 3 — Implement (small, scoped)

- Only what the item's **Do** says. Adjacent improvements go to a note, not the diff.
- Match surrounding code style; type hints on signatures; handle unhappy paths; no hardcoded secrets.
- Repo gotchas that WILL bite you (memorize):
  - **Two dispatch paths**: imperative `backend/app/chat/pipeline.py` AND LangGraph `backend/app/graph/chat_workflow.py`. Behavior changes must work on both.
  - **LangGraph drops undeclared state keys silently** — any new `state["key"]` must be declared in the pipeline-state TypedDict, and verified on the langgraph path.
  - **`validate_spl` splits on `|`** — regex alternation inside `match()` reads as pipe-commands and gets rejected.
  - **Settings load at process start** — after any `.env` / `env/profiles/*` edit: `docker compose restart backend`.
  - **Pytest blocks live LLM calls** (conftest autouse guard). Never remove it; `AI_SOC_TESTS_ALLOW_LIVE_LLM=1` is the deliberate opt-in.
  - **EC/demo path (`backend/app/demo/`) is fixture-only** — never wire live LLM/MCP/trace behavior into it.
  - **Frontend prod = Nginx serving `frontend/dist`** — `cd frontend && npm run build` publishes; postbuild chmod must survive or Nginx 403s.
  - **LLM never calls MCP directly; `candidate_spl` never executes; HIL confirmation gates stay** — these are invariants, not preferences.

## Step 4 — Verify (verbatim, no substitutes)

Run the item's **Verify** command exactly as written:
```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest <paths from the item> -q
```
- Command must PASS and you must see the output. "It should pass" is not verification.
- Fails once → diagnose and fix (stay inside the item's scope).
- **Fails twice on the same gate → STOP.** Record what failed, exact output, your hypothesis. Do not weaken the test, do not widen scope, do not move to the next item.

## Step 5 — Record Evidence and check the box

Edit the plan file:
- `- [ ]` → `- [x]`
- **Evidence:** one or two lines — command run, result (e.g. `pytest app/tests/test_x.py -q → 14 passed`), plus commit hash if committed, plus any anchor corrections found in Step 2.

Then re-run the discipline audit:
```bash
cd /var/www/ai-soc-assistant && .cursor/hooks/audit-plan-discipline.sh plans/<file>.md
```

## Step 6 — Gate check, then next item

- Before any commit: run `/invariant-check` (project skill) on the diff — one FAIL blocks the commit.
- Phase boundary or plan says regression → `./scripts/run_stage3_governance_regression.sh` must PASS (0 failures, harness 6/6).
- Decision gate (DG-x) reached → STOP and ask the user; never self-approve a gate.
- Ending the session mid-plan → run `/handoff` (global skill) so the next agent continues without re-deriving.
- Otherwise: back to Step 1 for the next item.

## Stop conditions (from the plan — they override momentum)

1. All items checked with evidence. 2. Same gate failed twice on one item. 3. Decision gate needs the user. When you stop, your report states: items completed (with evidence), item in progress and its exact state, what blocks, drift-log additions.
