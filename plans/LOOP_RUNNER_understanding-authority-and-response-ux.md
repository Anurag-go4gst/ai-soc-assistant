# LOOP_RUNNER — understanding-authority-and-response-ux

**Canonical plan:** [`plans/2026-08-21_1937_understanding-authority-and-response-ux.md`](2026-08-21_1937_understanding-authority-and-response-ux.md)

**Architecture freeze:** `architecture.md` @ `49c5a494` — **read-only**. Never modify during this loop.

## Start

```text
loop-asap — execute plans/2026-08-21_1937_understanding-authority-and-response-ux.md
```

> **Cursor only.** `loop-asap` is armed by `.cursor/hooks/before-submit-plan-discipline-arm.sh` and
> continued by `.cursor/hooks/stop-loop-asap-handoff.sh`. **Claude Code** runs the same steps
> manually from `AGENTS.md` and calls `audit-plan-discipline.sh` by hand.

## Agent loop (one phase at a time)

1. Reconcile: `git status && git log --oneline -5`. Confirm branch `feat/complete-or-abstain-t4-ux` (or current feature branch). Read plan Dependency order, Stop conditions, Drift log, and frozen `architecture.md` §§2.2 / 7 / 9 / 11 / 12 / invariants 51–52.
2. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-21_1937_understanding-authority-and-response-ux.md` — fix every GAP in the plan before coding.
3. Pick the **first unchecked** item whose **Depends on** are all checked: `P0 → P1 → P2 → P3 → P4 → P5 → P6 → P6.1 → P7 → P8`.
4. Verify anchors (`ls`, `rg`) before trusting file/line claims — they drift.
5. **AUDIT FIRST** existing modules named in the plan before editing. Prefer extend over recreate.
6. Implement only that phase’s **Do**. Smallest architecture-conformant change.
7. Run **Verify** exactly as written. Fail once → fix in scope and retry. **Fail twice → STOP**.
8. If the phase touched `pipeline` / `planner` / `SPL` / `MCP` / `LLM`: run `/invariant-check` on the diff. One FAIL blocks commit.
9. `git diff` + `git diff --check` for the phase.
10. Record **Evidence** (observed command output). Check `- [x]`.
11. Commit **one logical commit per phase** (scoped files only). Do not bundle unrelated workstreams.
12. Proceed only if green. Re-audit all checkmarks before declaring the plan complete.

## Test runners (MAC-FIRST — established 2026-08-21)

Final acceptance stays on this Mac. Do not relocate P7 to COE/VPS.

```bash
# application tests — container (./backend mounted rw at /app)
docker compose exec -T backend python -m pytest app/tests/<file>.py -q

# application tests — host venv (equivalent; 77 passed on both for the P1 suites)
cd backend && ../.venv/bin/python -m pytest app/tests/<file>.py -q

# governance — host venv ONLY (never in the container: /workspace is read-only)
PATH="$PWD/.venv/bin:$PATH" ./scripts/run_stage3_governance_regression.sh
```

- Bare `python3` has **no pytest**; the gitignored `.venv` is the fix. Never `pip install -e backend`
  (setuptools flat-layout error), and never edit `backend/pyproject.toml` to make it work.
- Governance **step 1 = `KNOWN_MACOS_GOVERNANCE_ENV_LIMITATION`** (ratified 2026-08-21). The committed
  discovery index embeds a Linux absolute `clone_root_used` and macOS resolves `/tmp` to `/private/tmp`,
  so **no** clone path can satisfy it here. Do **not** clone, vendor, regenerate the 754 rows, fake
  `clone_root_used`, edit the governance script, or hide/xfail the failure. It does **not** block P1–P6.
  Every other governance step still runs and must pass on Mac.
  **Release gate:** P8 RELEASE_READY additionally needs `OS=Linux` + `governance step 1=PASS` against the
  **exact same final candidate SHA** (VPS fine; LLM/MCP not required for it).
  Deferred fix: `docs/operations/deferred_github_skill_factory_governance_maintenance.md`.
- `rg` is host-only; not present in the container.

## Guards

- **Never** modify `architecture.md`.
- **Never** special-case individual user questions or add firewall keyword patches.
- **Never** implement embeddings in this plan.
- **Never** create a second router, second T4 service, or T4-only investigation runtime.
- **Never** weaken HIL / RBAC / exact-call / candidate_spl non-executability.
- **Never** make the LLM authoritative for route, ResourcePlan, CapabilitySnapshot, MCP, or remediation.
- **Never** fake LLM/MCP availability; report honest degrade.
- Missing MCP ≠ investigation; Final RQC product shape selects lifecycle.
- **Never** present workflow control status/action as a security containment action. `BLOCKED` (status)
  and `BLOCK` (next-action) are workflow-control vocabulary; they must never reach the analyst as
  "Block IP" / "Block firewall traffic". Containment language may originate **only** from a governed
  remediation/action contract. Remapping `investigation_status` alone does **not** close this — the
  `recommended_next_action` derivation leaks the raw token too (P6.1).
- **Never** rename governed backend enum values (`SufficiencyStatus`, `SufficiencyNextAction`,
  `InvestigationStatus`, `Disposition`) to fix presentation. If that looks required → **STOP**.
- **Never** let a T4 failure resurrect a partial T1–T3 contract, revive old intent/goal locks, invent a
  Final RQC, or start an investigation lifecycle. Fail closed: clarify or honest degrade.
- **Never** assume an SPL-domain contract is the architecture-wide explicit-literal authority; audit
  generality first, and never create a second literal parser or duplicate entity/time extraction.
- Related investigation-envelope work stays in `plans/2026-08-21_0034_agentic-investigation-production.md` — do not merge scopes.

## Stop

- Type `loop-asap stop`, or
- All items `- [x]` with Evidence, or
- Same Verify fails twice on one item, or
- Architecture interpretation ambiguous / would require editing `architecture.md`, or
- A new authority decision is required, or
- Implementation would require deleting legitimate existing work, or
- A second router/planner/runtime appears necessary, or
- Security / HIL / RBAC / exact-call would be weakened

## Evidence rules

- Evidence is **observed output**, not intent.
- Never check off on a partial pass.
- Baselines change only when a contract makes the old value wrong; name that contract in Evidence.
