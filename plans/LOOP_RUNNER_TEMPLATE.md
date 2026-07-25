# LOOP_RUNNER — &lt;slug&gt;

> Template. Copy to `plans/LOOP_RUNNER_<slug>.md`, replace every `<…>`, delete this line.
> Referenced by [`CLAUDE.md`](../CLAUDE.md) § Plan discipline and [`AGENTS.md`](../AGENTS.md).

**Canonical plan:** [`plans/<YYYY-MM-DD_HHMM_slug>.md`](<YYYY-MM-DD_HHMM_slug>.md)

## Start

```text
loop-asap — execute plans/<YYYY-MM-DD_HHMM_slug>.md
```

> **Cursor only.** `loop-asap` is armed by `.cursor/hooks/before-submit-plan-discipline-arm.sh` and
> continued by `.cursor/hooks/stop-loop-asap-handoff.sh` (`loop_limit: 5`), both read from
> `.cursor/hooks.json`. **Claude Code does not fire these hooks** — there, run the same seven steps
> manually and call `audit-plan-discipline.sh` by hand. See `CLAUDE.md`: *"Claude Code follows the
> same discipline manually from `AGENTS.md`."*

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/<YYYY-MM-DD_HHMM_slug>.md` — fix every GAP.
2. Pick first unchecked checklist item in dependency order (`<order>`).
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence** (command output or observation).
6. Next item. Do not skip. Stop on decision-needed, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Guards (run before checking off any item that touched runtime code)

- `/invariant-check` — required for pipeline / planner / SPL / MCP / LLM diffs.
- `<project regression gate>` — e.g. `./scripts/run_stage3_governance_regression.sh`.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item, or
- A decision is needed that the plan does not already settle.

## Evidence rules

- Evidence is **observed output**, not intent. Paste the command result or name the artifact.
- A failing Verify is recorded as failing. Never check an item off on a partial pass.
- Baselines and fixtures are changed only when a contract makes the old value wrong, and the
  completion report must name that contract.
