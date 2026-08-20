# LOOP_RUNNER — agentic-investigation-production

**Canonical plan:** [`plans/2026-08-21_0034_agentic-investigation-production.md`](2026-08-21_0034_agentic-investigation-production.md)

## Start

```text
loop-asap — execute plans/2026-08-21_0034_agentic-investigation-production.md
```

> **Cursor only.** `loop-asap` is armed by `.cursor/hooks/before-submit-plan-discipline-arm.sh` and
> continued by `.cursor/hooks/stop-loop-asap-handoff.sh` (`loop_limit: 5`), both read from
> `.cursor/hooks.json`. **Claude Code does not fire these hooks** — there, run the same Agent-loop
> steps below manually and call `audit-plan-discipline.sh` by hand. See `CLAUDE.md`: *"Claude Code
> follows the same discipline manually from `AGENTS.md`."*

**Gate before the first item runs:** the plan's frontmatter `status` must be `active`, not `draft`.
Architecture review sign-off flips it (see the plan's own "Execution is not authorized until
architecture review" line). Do not start P0 while `status: draft`.

## Agent loop

1. Reconcile: `git status && git log --oneline -5` in this checkout. Read the plan's Dependency
   order, Stop conditions, Drift log, and **Implementation vs COE live acceptance environment**
   before any item. `/var/www/ai-soc-mcp` is an implementation checkout only — no `/chat` stack
   runs from here; do not use it as the live acceptance environment. Run pytest with mocks here.
   Model/MCP services may still be reachable on this host. Live acceptance is
   `/var/www/ai-soc-assistant` after deploy. Do not skip an item because "COE has the model."
   A live COE result never substitutes for this checkout's Verify command.
2. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-21_0034_agentic-investigation-production.md` — fix every GAP.
3. Pick the **first unchecked** checklist item whose **Depends on** are all checked, in order
   `P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → (P9 optional) → P10 → P11 → P13` (`P12` may run
   any time after P1). P8 depends on P5, not P7, and may be implemented in parallel with P6/P7.
   P13 still requires P7. Never skip a hard dependency.
4. Verify the item's file/symbol anchors before trusting them (`ls`, `grep -rn`) — anchors drift.
5. Implement only that item's **Do**. New test files are named in the item's **Verify** line; if a
   named test has no file yet, create one file per phase (`test_p<N>_<short-topic>.py` under
   `backend/app/tests/`) — do not scatter new tests across unrelated existing files.
6. Run **Verify** exactly as written. Fails once → fix inside scope, retry. **Fails twice on the
   same gate → STOP**, record output + hypothesis in Evidence, do not weaken the test or widen scope.
7. Before committing anything that touched `backend/app/chat`, `backend/app/planner`,
   `backend/app/orchestration`, `backend/app/spl`, `backend/app/llm`, or `backend/app/connectors`:
   run `/invariant-check` on the diff. One FAIL blocks the commit — fix and re-check, do not skip.
8. Commit per the plan's **Commit discipline** section (one commit per phase, scoped to that
   phase's files only — never bundled with the separate T1–T3 catalogue-matching patch). All code
   and test operations for steps 1–8 happen in **this worktree** (`/var/www/ai-soc-mcp`).
9. If the plan's **Live acceptance by phase** section marks this phase "required": deploy the
   exact committed hash to the deployed COE runtime at `/var/www/ai-soc-assistant` (a different
   checkout on this same host, `srv1399719` — not a second server) per the plan's **Phase
   execution model** and **Deployment safety** checklist. Before touching that checkout, check its
   `git status`, current branch, current commit, and running service status — if it has
   uncommitted or unexpected changes, **stop and report; do not `git checkout`/`reset`/force
   anything there** without the user's explicit approval. Deploy the flag OFF first, confirm
   baseline health, then enable only this phase's new flag(s) and run the live acceptance test.
   Live probes run against the deployed stack, never by starting a second stack in this worktree.
10. Check off `- [x]` and fill **Evidence** using the plan's **Phase evidence template** — LOCAL
    VERIFICATION always; COE LIVE VERIFICATION block filled too when step 9 applied.
11. At a phase boundary (after P0, P5, P8, P13; and any time the plan's own text says
    "regression"): `./scripts/run_stage3_governance_regression.sh` must PASS. If it fails, stop —
    do not proceed to the next phase on a red regression.
12. Next item. Stop on decision-needed, gate fails twice, or all items done.
13. Re-audit all checkmarks before declaring the plan complete.

## Guards (run before checking off any item that touched runtime code)

- `/invariant-check` — required for pipeline / planner / SPL / MCP / LLM diffs (every phase in
  this plan touches at least one of those).
- `./scripts/run_stage3_governance_regression.sh` — phase-boundary gate (see step 10 above).
- Runtime-flag-off: every **runtime** phase flag defaults to `false`. Flag-off restores old
  **scheduling/execution** for that seam. It does **not** restore the P2 `skills/catalog.json`
  guided-row correction — that JSON is a permanent architecture change (`git revert` only).
- P5 / P7 handoff: P5 must not introduce PlanDelta. P7 plugs adaptive reasoning into the P5 seam.
  Do not create a second investigation loop.
- Production UX is ChatPanel / `/chat`, not Experience Center fixtures or `app.demo` contracts.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item, or
- A decision is needed that the plan does not already settle (architecture review, T1–T3
  isolation/landing before P2, a COE-live capability behaving unexpectedly, or any point where the
  plan's own text says "stop and ask").

## Evidence rules

- Evidence is **observed output**, not intent. Paste the command result (or the relevant tail of
  it) and name the commit hash if committed.
- A failing Verify is recorded as failing. Never check an item off on a partial pass.
- Baselines and fixtures (`docs/evals/*.json`, `sentinel_baseline.json`, golden answers) are
  changed only when a contract makes the old value wrong, and the item's Evidence must name that
  contract.
- Do not touch files belonging to the separate `2026-08-19_1130_catalogue-matching-coverage-and-margin.md`
  workstream except the single `guided_investigation` row in `backend/app/skills/catalog.json` that
  P2 is explicitly scoped to edit (see the canonical plan's "T1–T3 workstream boundary" section).
