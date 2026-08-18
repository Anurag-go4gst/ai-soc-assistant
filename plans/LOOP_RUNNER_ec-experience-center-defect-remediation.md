# LOOP_RUNNER — ec-experience-center-defect-remediation

**Canonical plan:** [`plans/2026-08-18_1522_ec-experience-center-defect-remediation.md`](2026-08-18_1522_ec-experience-center-defect-remediation.md) — **revision 3.1**

> **Checklist:** 22 items (0–18 + 19–21). PR template checkboxes are not checklist items.

> This file is an execution helper only. The canonical plan owns the checklist, the defects, and every rule.
> **On conflict, the canonical plan wins.** Before item 0, read the canonical plan's
> **READ THIS FIRST — executor ground rules** and **Pre-existing failure baseline** sections in full.

## Start

```text
loop-asap — execute plans/2026-08-18_1522_ec-experience-center-defect-remediation.md
```

## Agent loop

1. Audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-18_1522_ec-experience-center-defect-remediation.md` — fix every GAP.
2. Pick the first unchecked checklist item in dependency order: `0 → 1 → … → 7 → 19 → 8 → 20 → 21 → 9 → … → 18`.
3. Implement **Do** only for that item. Items state exactly one implementation — there are no forks. If you think there is a choice, re-read; if it truly cannot be done as written, **stop and ask**.
4. Run **Verify** exactly as written.
5. Check off `- [x]` in the canonical plan and fill **Evidence** with pasted command output.
6. Next item. Do not skip. Stop on decision-needed, gate fails twice, or all items done.
7. Re-audit all checkmarks before declaring complete.

## Non-negotiables (canonical plan Hard STOP — repeated here so they are not missed)

- **Never merge.** Item 18 ends at "PR open, awaiting owner". No `gh pr merge`.
- **Never bump `RACES_BASELINE_SHA`** in `test_live_path_untouched_by_ec.py`.
- **Never edit `backend/app/schemas/responses.py`** — the EC envelope already carries every field this plan renders.
- **Never delete or weaken an assertion** to make a gate pass.
- **Never add an env flag.**
- **Two tests are already RED on `master`.** Do not fix them. See below.
- Plan checkbox + Evidence edits ride in the **same commit** as that item's code.

## Pre-existing failures — expected, do not fix

Measured on clean `master` (2026-08-18):

| Test | Line | Cause |
|---|---|---|
| `test_live_path_untouched_by_ec.py::test_races_freeze_files_unchanged_since_baseline` | 142 | stale `RACES_BASELINE_SHA=bf7c304` |
| `test_races_g2_frontend_isolation.py::test_g2_layer1_workspace_does_not_interpolate_internal_ids` | 46 | `Session active` string absent from `EcInvestigationWorkspace.tsx` |

Combined expected result: **`2 failed, 11 passed`**. Item 16 passes on **no new failures**, not zero failures.

## Regression gates

```bash
# EC flagship slice (item 13+)  → expect 0 failed
cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_s5_cisco_hardening_remediation.py \
  app/tests/test_s2_ai_application_security.py \
  app/tests/test_s3_firewall_team_coordination.py \
  app/tests/test_ec_s4_siem_first.py \
  app/tests/test_s6_investigation_continuity.py \
  app/tests/test_s7_conflicting_ot_evidence.py \
  app/tests/test_ec_siem_first_investigation.py -q

# Live isolation (item 16)  → expect EXACTLY 2 failed, 11 passed (the two known ones)
cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_live_path_untouched_by_ec.py \
  app/tests/test_races_g2_frontend_isolation.py -q

# Frontend  (npm run test already == "vitest run"; do NOT add --run)
cd frontend && npm run test -- src/components/ec/ src/lib/ecOperationalLink.test.ts && npm run build
```

Forbidden-path diff — **the single canonical form**, run before every commit and at item 15:

```bash
git diff --name-only origin/master...HEAD -- \
  backend/app/api/routes_chat.py \
  backend/app/api/routes_chat_stream.py \
  backend/app/api/routes_actions.py \
  backend/app/chat/pipeline.py \
  backend/app/graph/ \
  backend/app/planner/ \
  backend/app/routing/ \
  backend/app/schemas/responses.py \
  backend/app/orchestration/mcp_execution_gate.py \
  backend/app/safeguards/spl_validator.py \
  frontend/src/components/ChatPanel.tsx
# expected: empty output
```

Optional full gate before requesting merge (if time permits):

```bash
./scripts/run_stage3_governance_regression.sh
```

## Commit sequence (items map)

| After items | Commit |
|-------------|--------|
| 1–4 | C1 — `ec: add Layer 1 source evidence and closure panels` |
| 5–8, 19 | C2 — `ec: fix S5 evidence gating and follow-up journeys` (+ A1 HIL) |
| 20, 21 | C3 — `ec: credibility markers and believable journey copy` |
| 9–11 | C4 — `ec: improve continue-chip UX and operational linking` |
| 12 | C5 — `ec: surface policy evidence for S2/S4 continue chips` |
| 13–14 | C6 — `ec: add defect-remediation acceptance tests` |

**Fidelity order within branch:** item 19 (A1) → 20 (B3) → 21 (C1). **Deferred:** A2, B1, B2 — see canonical plan Follow-up scope.

**Item 20 traps:** `production_validator_read_only` on `ec_provenance` or `ec_spl_governance.validation.provenance` — not top-level. Fixture badge: `spl_validation.warnings` and/or `source_evidence[].warnings` — never `demo_fixture_not_live_data` on source_evidence alone.

**Item 21 traps:** Verify must walk all `journey_for()` paths (initial + follow-up/action), not `_INITIAL` only. Ban whole `Replaying` token. In `_LLM_ACTIVITY`, replace `captured Foundation-sec` only — **leave** `Final synthesis disabled for Experience Center` (B2 deferred).

Run `/invariant-check` **and** the forbidden-path diff before each commit.

## PR / merge

- Open the PR only when items 0–17 are checked with Evidence.
- **Item 18 = push + open PR + paste all gate output + STOP.** The owner merges, not the agent.
- Repo has **no CI** — pasted local gate output is the only evidence. Do not wait for checks.
- Merge mechanics (owner): `--merge`, never `--squash`.
- Confirm `architecture.md` SHA unchanged: `c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034`

## Stop

- Type `loop-asap stop`, or
- Items 0–18 `- [x]` with Evidence (18 ends at "AWAITING OWNER MERGE APPROVAL"), or
- Same Verify fails twice on one item, or
- Any Hard STOP in the canonical plan triggered.

## Evidence rules

- Evidence is observed output, not intent.
- A failing Verify stays failing — never check off on partial pass.
- Browser audit (item 14) may be `SKIP: stack down` with the item-13 pytest output pasted as substitute — not a substitute for any pytest/vitest gate.
