# LOOP_RUNNER — optional-phase-s-spl-optimization

**Canonical plan:** [`plans/2026-08-27_optional-phase-s-spl-optimization.md`](2026-08-27_optional-phase-s-spl-optimization.md)

## Current checkpoint — 2026-08-27 (post LLM spine)

| Spine | Status | HEAD / evidence |
|---|---|---|
| Deterministic (S0–S9a) | **ACCEPTED** | `dd71393f` |
| LLM (S5–S9b) | **IMPLEMENTED_BUT_NOT_PRODUCTION_ACCEPTED** | live `s5_s6_live_probe_results_v1.json`; unit 11 passed |
| Layer 3 hardening (H0–H6) | **OPEN** | six-case live eval found unsafe accepted rewrites |

**Worktree:** `../ai-soc-wt-spl-optimization` · **Branch:** `ws/spl-optimization` · **Base:** `11a27365`

**`LAYER3_STATUS` = `IMPLEMENTED_BUT_NOT_PRODUCTION_ACCEPTED`.**
**`AI_SOC_SPL_OPTIMIZATION_LLM_ENABLED` = `false`** and stays false through development, evaluation and
final governance. Do not enable it in VPS during this loop.

**Reason:** live six-case evaluation found the model over-claiming `OPTIMIZED`, a `NOT`→`!=` false
optimization, and a **wildcard semantic rewrite that escaped the guard**; invention was correctly caught.
Prompt = prevention. Deterministic guard = authority. The model never decides whether its own rewrite is safe.

**Next:** **LAYER3_HARDENING** — H0 → H1 → H2 → H3 → H4 → H5 → H6, then merge gates.

Checked off: S0–S4 · S5 · S6 · S7 (partial — RACES prepared, uncommitted) · S8a · S8b · S9a · S9b (code+probes)

## Start / resume

```text
loop-asap — execute plans/2026-08-27_optional-phase-s-spl-optimization.md
```

Merge-gate follow-up (not loop-asap checklist) — **only after H6 passes**:

```text
Run ./scripts/run_stage3_governance_regression.sh in worktree;
advance RACES baseline for pipeline.py;
open PR for ws/spl-optimization
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
   - LLM spine: `S5 → S6 → S7 → S8b → S9b` **(DONE code/probes; S7 RACES prepared)**
   - **Layer 3 hardening: `H0 → H1 → H2 → H3 → H4 → H5 → H6` (current)**
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
- **H2 shares `assert_rewrite_preserves` with accepted S4** and runs live via `pipeline.py:9306`
  independent of the Layer 3 flag. Canonicalise `field IN (a,b,c)` ≡ the same-field OR set before
  comparing, or the accepted OR→`IN` rewrite regresses. If P1 goes red the invariant is wrong —
  **never relax P1, never weaken the guard to make Layer 3 pass.**
- **Prompt iteration is bounded: two revisions maximum.** A second unsafe governed accepted rewrite
  after revision two is a STOP, not a reason to lower the bar.
- **Knowledge UI (`6a6d887d`) is frozen** — not wired to runtime; do not wire toggles to execution
  authority. Extending the registry `invariants` data list for honesty is allowed; wiring is not.
- **Stage-3 Tier0 failures are an inherited residual** reproducing on `c109402d`. Record baseline-vs-current
  failing case IDs and mark `ACCEPTED_INHERITED_RESIDUAL`. Never greenwash; never "fix" them by changing
  SPL optimization code.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item, or
- Live LLM unavailable for S5 or S6 required live probe → **ENVIRONMENT STOP** on LLM spine only (S9a still allowed; do not drop Layer 1b/3; resume when restored), or
- A decision is needed that the plan does not already settle (D-S1 and D-S4 are already **ACCEPTED**), or
- Any Layer 3 hardening stop condition fires (see plan § Stop conditions → *Layer 3 hardening additions*).

**Not a stop:** the model being merely conservative. Keep the flag OFF, record
`MODEL_TOO_CONSERVATIVE_FOR_ENABLEMENT` / `LAYER3_ENABLEMENT_ELIGIBLE = NO`, keep the architecture.

## Evidence rules

- Evidence is **observed output**, not intent. Paste the command result or name the artifact.
- A failing Verify is recorded as failing. Never check an item off on a partial pass.
- Baselines and fixtures are changed only when a contract makes the old value wrong, and the
  completion report must name that contract (optimized SPL before/after; `execution_eligible` true→false flips).
- S6 may abstain (unchanged v1 → `NO_SAFE_OPTIMIZATION`); never force a rewrite of valid SPL.
- S1 distribution must be reported per producer path × `ai_soc_llm_spl_fallback_enabled`.
- **H4/H5 required zeroes are hard bars, never averaged:** `UNSAFE_ACCEPTED_REWRITE=0`,
  `FALSE→TRUE EXECUTION_ELIGIBLE=0`, `INVENTED GOVERNED SLOT ACCEPTED=0`,
  `WILDCARD SEMANTIC CHANGE ACCEPTED=0`, `TIME SEMANTIC CHANGE ACCEPTED=0`.
- **H5 anti-overfit:** report positives offered / safely optimized / abstained separately from negatives.
  Teaching the model to abstain on everything is a failure, not a pass.
- No secrets in prompt or eval artifacts.
- **Update the canonical plan checklist and Execution status section on every item check-off.**
