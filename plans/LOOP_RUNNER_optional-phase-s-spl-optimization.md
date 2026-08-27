# LOOP_RUNNER — optional-phase-s-spl-optimization

**Canonical plan:** [`plans/2026-08-27_optional-phase-s-spl-optimization.md`](2026-08-27_optional-phase-s-spl-optimization.md)

## Current checkpoint — 2026-08-27

| Spine | Status | HEAD |
|---|---|---|
| Deterministic (S0–S9a) | **ACCEPTED** | `dd71393f` |
| LLM (S5–S9b) | **PENDING_LIVE_VALIDATION** | — |

**Worktree:** `../ai-soc-wt-spl-optimization` · **Branch:** `ws/spl-optimization` · **Base:** `11a27365`

**Next item when LLM restored:** **S5** (Foundation-Sec `:8081` was UNAVAILABLE at S9a close).

Checked off: S0 `283598e1` · S1 `fa1b2182` · S2 `2649f2c1` · S3 `d8b4385a` · S4 `3742fbb9` · S8a `d9d11963` · S9a `dd71393f`

Pending: S5 · S6 · S7 · S8b · S9b

## Start

```text
loop-asap — execute plans/2026-08-27_optional-phase-s-spl-optimization.md
```

Resume after LLM restore:

```text
loop-asap — resume OPTIONAL_PHASE_S from S5 in ../ai-soc-wt-spl-optimization
```

> **Cursor only.** `loop-asap` is armed by `.cursor/hooks/before-submit-plan-discipline-arm.sh` and
> continued by `.cursor/hooks/stop-loop-asap-handoff.sh` (`loop_limit: 5`), both read from
> `.cursor/hooks.json`. **Claude Code does not fire these hooks** — there, run the same seven steps
> manually and call `audit-plan-discipline.sh` by hand. See `CLAUDE.md`: *"Claude Code follows the
> same discipline manually from `AGENTS.md`."*

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-27_optional-phase-s-spl-optimization.md` — fix every GAP.
2. Pick first unchecked checklist item in dependency order:
   - Deterministic spine: `S0 → S1 → S2 → {S3 ‖ S4} → S8a → S9a` **(DONE)**
   - LLM spine: `S5` / `S6 → S7 → S8b → S9b` **(resume S5)**
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence** (command output or observation).
6. Next item. Do not skip. Stop on decision-needed, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Guards (run before checking off any item that touched runtime code)

- `/invariant-check` — required for pipeline / planner / SPL / MCP / LLM diffs.
- `./scripts/run_stage3_governance_regression.sh` — before S9a/S9b close; after S7 if risk/validator path touched.
- Authority: `approved` identical to S0; `execution_eligible` one-way tighten only; `normalized_spl` only differs on optimized rows under guard+chain+recorded delta.
- Never touch `spl_validator.py` or `policy.py`. Never promote new efficiency rules off `advisory`. Never generalize Q13.
- **S7:** D-S4 protected packet for `pipeline.py` + RACES baseline advance required before/with the edit.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item, or
- Live LLM unavailable for S5 or S6 required live probe → **ENVIRONMENT STOP** on LLM spine only (S9a still allowed; do not drop Layer 1b/3; resume when restored), or
- A decision is needed that the plan does not already settle (D-S1 and D-S4 are already **ACCEPTED**).

## Evidence rules

- Evidence is **observed output**, not intent. Paste the command result or name the artifact.
- A failing Verify is recorded as failing. Never check an item off on a partial pass.
- Baselines and fixtures are changed only when a contract makes the old value wrong, and the
  completion report must name that contract (optimized SPL before/after; `execution_eligible` true→false flips).
- S6 may abstain (unchanged v1 → `NO_SAFE_OPTIMIZATION`); never force a rewrite of valid SPL.
- S1 distribution must be reported per producer path × `ai_soc_llm_spl_fallback_enabled`.
- **Update the canonical plan checklist and Execution status section on every item check-off.**
