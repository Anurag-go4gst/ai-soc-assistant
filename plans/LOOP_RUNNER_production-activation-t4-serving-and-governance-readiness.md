# LOOP_RUNNER — production-activation-t4-serving-and-governance-readiness

**Canonical plan:** [`plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md`](2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md)

## Start

```text
loop-asap — execute plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md
```

> **Cursor only.** `loop-asap` is armed by `.cursor/hooks/before-submit-plan-discipline-arm.sh` and
> continued by `.cursor/hooks/stop-loop-asap-handoff.sh` (`loop_limit: 5`). **Claude Code does not
> fire these hooks** — run the seven steps manually and call `audit-plan-discipline.sh` by hand.

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md` — fix every GAP.
2. Pick the first unchecked checklist item **in the dependency order below**, not document-section order.
3. Implement **Do** only for that item.
4. Run **Verify** exactly as written.
5. Check off `- [x]` and fill **Evidence** (command output or observation).
6. Next item. Do not skip. Stop on a named STOP gate, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Dependency order (item IDs are NOT a numeric sequence)

```text
P0 → P0.1 → P0.2 → A0 → A1 → A2 → A3 → A-GATE
                                      ↓
                                     A4 (VPS Arm A)
                                      ↓
                                     B0 (VPS Arm B) → B1 (VPS Arm C, then restore Arm A)
                                      ↓
                     D0 → D1 → D2     B2 → B-GATE
                                      ↓
                    after B-GATE and D2: present C0 + D3 together (two STOPs, one handoff)
                                      ↓
                    C1 (after C0)     D4 (after D3)
                    C2 → C3 (STOP)
                    E0 / E1 → E2 (STOP) / E3 (STOP) → E4
                                      ↓
                    F0 → F1 → F-GATE → F2 → F3 → F4 → F5 (STOP P6_PRODUCTION_GO_LIVE)
                                      ↓
                                     G0 → G1 → G2
```

**Preferred single-agent walk:**
`P0, P0.1, P0.2, A0, A1, A2, A3, A-GATE, A4, B0, B1, D0, D1, D2, B2, B-GATE, then combined STOP C0+D3.` After C1/D4: `F0, F1, F-GATE, F2, F3, F4, then STOP F5.` Do not call the VPS production-ready until F5.

## Hard loop rules (Plan 6 specific)

1. **One VPS ⇒ serialize flag arms.** Never run B0, B1, and D0 overlapping. They mutate the same host env. After each VPS arm: `docker compose restart backend` (settings load at process start). B1 **restores Arm A flags** before D0.
2. **A-GATE is LOCAL.** It must not wait for A4. A4 is the first VPS item.
3. **No new env flags.** Ride existing Plan 5 flags. Schedule-compare is in-process/trace-only.
4. **Combined STOP after B-GATE + D2:** present `P6_RESOURCE_PLAN_EXECUTION_ACTIVATION` (C0) and `P6_T4_SERVING_POSTURE` (D3) in one handoff. Do not start C1 or D4 until the matching decision is recorded. C0 must record dispatch-v2 precedence if exec is any ON. `V2_WINS` is not Plan-5 merge activation.
5. **C3, E2, E3, F5** are additional STOPs. Do not self-approve. F2–F4 are required before `P6_PRODUCTION_GO_LIVE`. Test-arm success is not go-live. Persistent VPS ON does not require `config.py` defaults true.
6. **Live capability enforcement stays OFF.** Do not add it as an activation arm unless new evidence reopens Plan 5 B5.
7. **T4 only if D3 passes.** Do not add T4 to the persistent profile otherwise.
8. **Do not add keyword heuristics** for the 8 T4 paraphrases. Do not raise T4 timeout as the first D0 move.
9. After governance regression: revert **only** the six stale reports in `ARTIFACT_REFRESH_POLICY.md`. Never `git checkout -- docs/evals/` (destroys `docs/evals/plan6/`).
10. Do not commit unrelated dirt (`.claude/settings.local.json`, `detail_tools/__init__.py`, Playwright captures, `output/`).
11. Mock MCP may validate architecture. Live Splunk/MCP production-ready requires F3’s controlled read-only test; otherwise record `live_mcp_unproven`. F3 is not a smoke test — failure classes in the plan item must all be recorded. F5 `GO LIVE` requires zero critical blockers and a user choice.
12. **Git cadence** (full rules in the plan’s **Commit / PR / merge**):
   - Branch `feat/plan6-production-activation` from `1d32ac6`. Never commit on `master`.
   - Phase-scoped commits after Verify (`plan6(<item>): …`). C1 and D4 are never the same commit.
   - `/invariant-check` 7/7 before any runtime commit.
   - Draft PR after A-GATE. Do not put unapproved flag defaults or promoter runs in the PR.
   - Merge is **user-only**, `gh pr merge --merge` (not squash). G2 must not merge.

## Guards — run before checking off any item that touched runtime code

- `/invariant-check` — required for pipeline / planner / SPL / MCP / LLM / debug-trace diffs.
- Targeted pytest from the item's **Verify**.
- Phase-boundary items (`A-GATE`, `B-GATE`, `F-GATE`, `G2`): `./scripts/run_stage3_governance_regression.sh` when the item says so.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item, or
- A named STOP gate needs the user, or
- The user has not yet approved merge to `master` (G2 complete ≠ merged).

## Evidence rules

- Evidence is **observed output**, not intent.
- A failing Verify is recorded as failing. Never check an item off on a partial pass.
- Baselines and fixtures change only when a named gate makes the old value wrong.
- VPS evidence: SHA, flags (booleans/names), trace_ids — never tokens, passwords, raw SPL secrets, or MCP payloads.
