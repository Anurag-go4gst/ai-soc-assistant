# LOOP_RUNNER — guided-detail-tools-consumable-handoff

**Canonical plan:** [`plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md`](2026-07-24_2310_guided-detail-tools-consumable-handoff.md) (rev 11)

## Start

```text
loop-asap — execute plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md
```

> **Cursor only.** `loop-asap` is armed by `.cursor/hooks/before-submit-plan-discipline-arm.sh` and
> continued by `.cursor/hooks/stop-loop-asap-handoff.sh` (`loop_limit: 5`). **Claude Code does not
> fire these hooks** — run the seven steps manually and call `audit-plan-discipline.sh` by hand.

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-07-24_2310_guided-detail-tools-consumable-handoff.md` — fix every GAP.
2. Pick first unchecked checklist item **in the plan's dependency order, not numeric order** (below).
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence** (command output or observation).
6. Next item. Do not skip. Stop on decision-needed, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Dependency order (item numbers are NOT execution order)

```text
12 ✅ → 13 ✅ → 14 ✅ → 30 → 15 → 16 → 31 → 32 → 33 → 34 → 17 → 35
→ 18a → 19a → 10 → 21a → 18 → 19 → 21b → 20 → 21 → 22 → 23 → 24
→ 25 → 26 → 26a → 28 → 11 → 29 → 27
```

**Current batch: 30 → 15 → 16 → 31 → 32 → 33 → 34 → 17 → 35.** Do not start persistence (18/18a/19/19a),
migration, execution idempotency (20), telemetry catalog (21/21a/21b), or documentation in this batch.

Gate rules that override numeric intuition:
- **30 precedes 15** — parity root cause decides whether a pytest failure is a legacy assumption (A–F) or a real regression (G).
- **31 precedes 32** — define what "equal" means before changing code to achieve it.
- **33 follows 32** — the static guard must lock in the unified state, not be written against the forked one.
- **35 follows 32 and 34** — regenerate artifacts only once the runtimes agree.

## Guards — run before checking off any item that touched runtime code

- `/invariant-check` — **required**; this repo's 7-group governance diff review.
- Sentinel: `PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --check` → **17/17 PASS**.
- Full pytest: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q` → must not exceed the
  current **112** failures; **set-diff against a stashed baseline, never compare counts.**
- Governance regression at phase boundaries: `./scripts/run_stage3_governance_regression.sh`.

## Hard constraints carried from rev 11

- **No parity or eval artifact may be regenerated or committed before item 35.** The runners write
  directly over `docs/evals/`; point them at a scratch directory until item 35 lands the
  artifact-safe writer.
- The parity artifacts committed in `8792338` are **stale and non-authoritative** (`85 acceptable /
  35 mismatch`). The `107 acceptable / 13 mismatch` figure is **observational only**. Cite neither
  as final evidence.
- Parity classifications are `exact_match` / `approved_difference` / `critical_mismatch`. An
  `approved_difference` needs all six per-field records; routing, tier, lane, answer goal, intent,
  completeness, canonical input, plan authority, governance and execution differences **cannot be
  approved**.
- Never add a field to a tolerance or exclusion list to make a mismatch disappear.

## Known priority order and traps (from the plan's drift log)

- **Item 30 is analysis-only and blocks nothing** — do it first and completely. `classify_parity_row`
  returns `match` only when all ten compare keys are equal, and both its `hard_diffs` and
  `soft_diffs` branches return `acceptable_diff`, so `_ACCEPTABLE_DIFF_FIELDS` is currently **dead
  configuration**. "Acceptable" has never meant "approved".
- **Removing a state key that downstream nodes silently depend on is the dominant risk of this
  cutover.** It has already produced a live safety regression (blocked containment requests
  downgraded from `unsafe_action_blocked` to `policy_checks_passed`) and three silent channel drops.
  Set-diff the full suite against a stashed baseline every batch.
- **LangGraph drops undeclared `ChatPipelineState` keys.** Any new `state["key"]` that must survive
  the RP graph edge has to be declared on the TypedDict; verify on the compiled graph via
  `.invoke()`, not by calling node functions directly.
- **Two different meanings of "T2" exist here** — the tier table's `use_case_catalog` (a known lane)
  and the LLM-utilization sense (out-of-catalogue). The plan's tier table is authority for lanes.
- Three self-lowering eval artifacts have already occurred. Treat any eval summary whose corpus
  count shrank as a failure, not a result.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item, or
- Category **G** (genuine regression) appears in the item-15 inventory — that is a decision point,
  not something to fix inside the loop.

## Acceptance for this batch

- Full pytest: **0 failures**, category G empty.
- Parity: **0 `critical_mismatch`** across 120 rows; every non-exact row an `approved_difference`
  with complete six-part per-field records.
- Both runtimes free of independent routing / completeness / intent / planning logic (item 33 static
  guard, with a recorded negative control).
- Behavioural parity green across all seven canonical path classes (item 34).
- Governance regression **PASS**.
- No baseline or tolerance change hides a behavioural defect.
