---
name: ec-experience-center-defect-remediation
overview: "Close Experience Center Layer-1 evidence/action UX defects across S1–S7 (S5 priority): honest EvidenceState/InvestigationOutcome projections, source_evidence surfacing, follow-up journeys, and acceptance tests — EC/demo only; architecture.md and live /chat frozen."
status: active
date: 2026-08-18
canonical_plan: plans/2026-08-18_1522_ec-experience-center-defect-remediation.md
loop_runner: plans/LOOP_RUNNER_ec-experience-center-defect-remediation.md
revision: 3.1
parent_plans:
  - plans/2026-08-16_2310_races-experience-center.md
  - plans/2026-08-17_races-investigation-execution-ux.md
architecture_contract: architecture.md
architecture_sha256: c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034
---

# EC Experience Center defect remediation (CTO/CSO demo readiness)

## Objective

Remove measured Experience Center defects so a CTO/CSO demo shows **honest, architecture-aligned projections** without touching production authority:

```text
Layer 1 — SOC answer (evidence + gaps + next steps, no architecture dump)
Layer 2 — Investigation path (projected EvidenceState / InvestigationOutcome / controls)
Layer 3 — Action journey (HIL → simulated execute → receipt → verify)
```

**Done** when all **22 checklist items** (0–18 + 19–21) are `- [x]` with Evidence (the PR template's 7 gate checkboxes are paste targets only, not checklist items), invariant check PASS, live-path isolation meets the **no-new-failures** criterion in item 16, flagship EC pytest + vitest green, `npm run build` green, and a PR is open per **Merge conditions**. **The executing agent never merges.**

This plan **projects** `architecture.md` §EvidenceState, §InvestigationOutcome, and §Action flow inside EC fixtures only. It does **not** wire EC into production ResourcePlan, PhaseContract, MCP gate, or `/chat`.

**Fidelity audit input:** [`docs/evals/ec_architecture_fidelity_audit_2026-08-18.md`](../docs/evals/ec_architecture_fidelity_audit_2026-08-18.md). Purity is **PASS** — no work. This branch adds **A1, B3, C1** only; **A2, B1, B2** are deferred (see **Follow-up scope**).

---

## READ THIS FIRST — executor ground rules (rev 3)

These rules exist because a weaker executor previously had room to guess. They are binding.

1. **No forks.** Every item below states exactly one implementation. If you believe an item offers a choice, you have misread it — re-read. If an item genuinely cannot be done as written, **stop and ask** (Stop conditions).
2. **No new backend response fields.** The EC envelope already carries `source_evidence`, `ec_investigation_outcome.closure_summary`, `ec_evidence_state`, and `ec_action_readiness`. This was measured on 2026-08-18. Frontend work is **rendering only**. Editing `backend/app/schemas/responses.py` is a Hard STOP.
3. **Two named tests are already RED on `master` before you start.** See **Pre-existing failure baseline**. You must not fix them, not weaken them, and not delete their assertions. Item 16 passes on *no new failures*, not on zero failures.
4. **`RACES_BASELINE_SHA` in `test_live_path_untouched_by_ec.py` must not be bumped.** Changing it is a test edit dressed as a config bump → Hard STOP.
5. **Plan bookkeeping rides with code.** The `- [x]` + Evidence edit for an item goes in the **same commit** as that item's code. Never leave the tree dirty across a gate.
6. **Evidence is pasted command output**, not a claim that you ran it.
7. When an item names a file and a symbol, **open the file and confirm the symbol exists** before editing. If the anchor moved, stop and ask.

---

## Pre-existing failure baseline (measured on `master`, 2026-08-18, before any plan work)

Both live-isolation tests already fail on a clean `master`. This is **not** caused by this plan and **must not** be fixed by this plan.

| Test node ID | Line | Cause (measured) |
|---|---|---|
| `backend/app/tests/test_live_path_untouched_by_ec.py::test_races_freeze_files_unchanged_since_baseline` | 142 | `RACES_BASELINE_SHA = bf7c304` is stale. `git diff bf7c304...HEAD` shows freeze files already changed: `backend/app/chat/pipeline.py`, `backend/app/orchestration/mcp_execution_gate.py`, `frontend/src/components/ChatPanel.tsx` |
| `backend/app/tests/test_races_g2_frontend_isolation.py::test_g2_layer1_workspace_does_not_interpolate_internal_ids` | 46 | Fails on the **first** assert — the literal string `Session active` is absent from `frontend/src/components/ec/EcInvestigationWorkspace.tsx` (removed by an earlier UX change). The other four asserts pass. |

Measured counts on clean `master`:

```text
test_live_path_untouched_by_ec.py        1 failed, 7 passed
test_races_g2_frontend_isolation.py      1 failed, 4 passed
```

**Executor rules for these two:**

- Do **not** re-add `Session active`, do **not** edit the assert, do **not** bump the SHA.
- Item 9 edits `EcInvestigationWorkspace.tsx` — the file that test reads. After item 9, that test must still fail on **line 46 only**, with the other four asserts still passing. Any *additional* assert failing = you introduced a regression.
- Both failures are logged as **owner decisions** in the PR body (see template). They are out of scope here.

## User decision (locked for rev 1, unchanged in rev 2)

**S5 initial policy posture — honest gating:**

- Initial turn: breach + `current_version=14` **may** be stated. The initial journey **does** include the version probe, and the version evidence **is** genuinely obtained on turn 0.
- Initial turn: **must not** claim hardening policy applicability until `show_hardening_policy` follow-up.
- Initial journey: **must not** animate “Retrieving EC hardening policy” before policy is obtained.

> **Consequence you must not get backwards (rev 2 correction):** because version=14 is legitimately obtained on turn 0, the readiness row `Confirm current version (cisco.get_version)` **should be `OBTAINED` on turn 0**. The bug is that `missing_evidence` simultaneously lists `cisco.get_version`. **Fix the missing list, not the readiness row.** Rev 1 of this plan said the opposite; it was wrong.

## Governing invariant (subsumes D3 / D4 / D5)

For each of the four S5 evidence items — **version**, **hardening policy**, **change ticket**, **maintenance window** — these three surfaces **must agree on every turn**:

| Surface | Field |
|---|---|
| Investigation outcome | `ec_investigation_outcome.missing_evidence` |
| Evidence state | `ec_evidence_state` item status |
| Action readiness | `ec_action_readiness` row state |

An item present in `missing_evidence` may not simultaneously be `OBTAINED` in `ec_evidence_state` or `OBTAINED` in `ec_action_readiness`. Item 13 encodes this as a test that loops all four items across the full follow-up sequence.

## Defect inventory (measured 2026-08-18)

| ID | Defect | Root cause (verified) |
|----|--------|-----------|
| D1 | “Show hardening policy” appears to do nothing | Backend populates `source_evidence` (`ev-s5-policy`); **no EC Layer-1 renderer** — `grep -rn source_evidence frontend/src/components/ec/` is empty |
| D2 | Policy applies before policy opened | `pack.py::build_s5_turn` `found=` is a static f-string “Policy applies because…” and `assessment=` says “must be upgraded to version 15” on turn 0 |
| D3 | “Confirm current version” OBTAINED on turn 0 **while `cisco.get_version` is in `missing_evidence`** | `ec_remediation_s5.py:75` `if "check_current_version" in applied or version:` — `version` is always ≥14 (truthy). Readiness is right by accident; `missing_evidence` is the liar |
| D4 | `cisco.get_version` in missing list while version OBTAINED | `pack.py:200–202` add `ev-s5-initial-version` and set `cisco_version=OBTAINED` unconditionally, but `_base_outcome()["missing_evidence"]` still lists `cisco.get_version` |
| D5 | Maintenance window not cleared from missing | `pack.py:113` `check_maintenance_window` branch sets state OBTAINED but has no `missing_evidence` filter |
| D6 | Closure summary invisible | `closure_summary` set on outcome (`pack.py:188`); no frontend renderer in `components/ec/` |
| D7 | Continue chips replay full investigation | `EcInvestigationWorkspace.tsx:162` `keepAnswer = isActionChip(chip)`; non-action chips hit `setRevealed(false)` at line 168 |
| D8 | No scroll/highlight to result | `readinessLabelForActionChip` returns `null` for non-action chips (`ecOperationalLink.ts:19–20`) |
| D9 | Duplicate “Recommended actions” headings | `EcFollowUpBar.tsx:39` **and** `EcInvestigationQuality.tsx:85` (inside `EcActionReadinessPanel`) both render the literal `Recommended actions` |
| D10 | S2/S4 `show_*` policy chips same surfacing gap | Same as D1 — evidence lands in `source_evidence` only |
| D11 | S5 continue follow-ups use generic journey | `_FOLLOW_UPS["s5_cisco_hardening_remediation"]` (`ec_journeys.py:758`) has only the five action chips; the five evidence chips fall through to `_fallback_non_initial` |
| **A1** | S5 Cisco upgrade animates with **no HIL stage** | `_cisco_action` non-verify: Select → Connect → Receipt. `_firewall_action` has `("Approval required","hil")`. FSM gates correctly; animation contradicts invariant 37 / §20 SIDE_EFFECTING |
| **B3** | Strongest credibility markers hidden | `production_validator_read_only`, `live_llm_called`, `demo_fixture_not_live_data` in backend/tests only — **not rendered** in any EC component |
| **C1** | Journey activity saturated with demo tells | CIO-visible strings: `Replaying…`, `Fixture replay:…`, `Loading captured Foundation-sec…`. Layer 1 is clean; **relocate** honesty to badges/Layer 2, not delete it |

### Not defects — do not “fix”

- EC purity (no live LLM/MCP/RAG) — **PASS**; `capture_loader` fail-closed behaviour is correct.
- Cisco device MCP / CMDB / SOAR / ITSM / email — permitted §20 + invariant 36.
- Layer-1 answer quality (refuses to over-conclude) — **keep**; this is the value proposition.
- **Label risk only:** architecture “Cisco” = Foundation-Sec 8B LLM; S5 “Cisco MCP” = router device API — item 20 must distinguish them in copy.

## Follow-up scope (NOT this branch — separate plan)

| ID | Finding | Why deferred |
|----|---------|--------------|
| **A2** | `llm-advisory` animates **before** `outcome` on all 7 flagships | Contradicts §2.7 / invariant 27 in **animation only**; code is correct. Requires swapping/retitling `INITIAL_ARCHITECTURE_STEP_COUNT` stage order across S1–S7 — large blast radius. |
| **B1** | EC shows ~6/12 architecture phases; T4/RQC/clarification/PhaseContract/sufficiency invisible | “Why AI SOC” gap — needs new projected stages, not a copy edit. |
| **B2** | `"Final synthesis disabled for Experience Center"` on all 7 | Advertises absence of shipped capability; needs positive framing or Layer-2-only placement. |
| **polish** | Layer-2 negation string volume (S1=27 … S7=10) | Honesty relocation follow-on after C1. |

## Hard STOP (do not proceed — stop and ask the owner)

- Editing [`architecture.md`](../architecture.md) (read-only per Plan 8 freeze)
- Editing any path in `EC_FORBIDDEN_PREFIXES` (authoritative list, from `test_live_path_untouched_by_ec.py`):
  `backend/app/api/routes_chat.py`, `backend/app/api/routes_chat_stream.py`, `backend/app/api/routes_actions.py`, `backend/app/chat/pipeline.py`, `backend/app/graph/`, `backend/app/planner/`, `backend/app/routing/`, `backend/app/schemas/responses.py`, `backend/app/orchestration/mcp_execution_gate.py`, `backend/app/safeguards/spl_validator.py`, `frontend/src/components/ChatPanel.tsx`
- Live MCP/LLM/RAG in EC animation or fixtures
- Production `/api/actions` or ResourcePlan / PhaseContract behavior changes
- `PlaceholderResponse` schema changes
- Weakening, deleting, or "fixing" any assertion in `test_live_path_untouched_by_ec.py` or `test_races_g2_frontend_isolation.py` — **including bumping `RACES_BASELINE_SHA`**
- Deleting or relaxing any existing test to make a gate pass
- `/invariant-check` FAIL on final diff
- Any need to add a new environment flag

## Architecture alignment (EC projections only)

| `architecture.md` role | EC implementation (this plan) |
|------------------------|----------------------------------|
| Minimal EvidenceState (§941) | `ec_evidence_state` + Layer-1 evidence cards; status must match missing/readiness per **Governing invariant** |
| InvestigationOutcome (§1028) | `ec_investigation_outcome`; no free-form prose as action authority |
| Action flow (§1118) | Existing `ec_actions` chain unchanged; Layer-3 `EcActionFlow` linking improved |
| Deterministic authority (§2.1) | Fixture packs remain deterministic; no LLM execution authority |
| Side effects (§1145) | `production_side_effect=false`; simulated receipts only |
| Trust boundaries (§2.8) | Provenance `ec_scenario_policy` / `simulated_mcp` in Layer 2; natural copy in Layer 1 |

## Allowed touch surfaces

Union of `EC_SCOPE_PREFIXES` and `EC_ALLOWED_PREFIXES` in [`test_live_path_untouched_by_ec.py`](../backend/app/tests/test_live_path_untouched_by_ec.py), plus paths that are in neither forbidden nor scope lists (untracked by the gate):

**In `EC_SCOPE_PREFIXES` / `EC_ALLOWED_PREFIXES`:**
- `backend/app/demo/**` (fixtures, `ec_journeys.py`, `ec_remediation_s5.py`, etc.)
- `backend/app/tests/test_ec_*`
- `frontend/src/components/ec/**`
- `frontend/src/pages/ScenariosPage.tsx` (presentation only)
- `frontend/src/api/ecClient.ts` (read-only client only if needed)
- `frontend/src/types/api.ts`
- `backend/app/api/routes_scenarios.py`

**Not gate-tracked, but in scope for this plan:**
- `frontend/src/lib/ecOperationalLink.ts` (+ its test)
- `scripts/ec_browser_walk_audit.mjs`
- New backend tests named `backend/app/tests/test_ec_*` (other new backend test filenames are **not** in `EC_ALLOWED_PREFIXES` — extend the existing `test_s5_*` file instead of creating a new non-`test_ec_` file)

## Stop conditions

- All checklist items checked with Evidence, **or**
- Same Verify fails twice on one item, **or**
- Decision needed (tradeoff / COE deferral / anchor moved / Hard STOP triggered) — stop and ask

## Dependency order

`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 19 → 8 → 20 → 21 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18`

**Fidelity fix order within this branch (owner):** A1 (item 19) → B3 (item 20) → C1 (item 21). Items 2–3, 6, 8 remain the UX-defect owners already in the list — do not duplicate their work in 19–21.

## Commit hygiene (required before PR)

Stage **scoped commits** only (no mixed production + EC). Each commit includes that item's plan checkbox + Evidence edit.

| # | Subject (Conventional Commits) | Items |
|---|--------------------------------|-------|
| C1 | `ec: add Layer 1 source evidence and closure panels` | 1–4 |
| C2 | `ec: fix S5 evidence gating and follow-up journeys` | 5–8, **19** |
| C3 | `ec: credibility markers and believable journey copy` | **20**, **21** |
| C4 | `ec: improve continue-chip UX and operational linking` | 9–11 |
| C5 | `ec: surface policy evidence for S2/S4 continue chips` | 12 |
| C6 | `ec: add defect-remediation acceptance tests` | 13–14 |

Run `/invariant-check` **before each commit**.

Before every commit, the forbidden-path diff must be empty (**single canonical command**, use this exact form everywhere):

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

Never commit: `.env`, secrets, `architecture.md` changes, eval baseline drift.

## PR conditions (open PR only when all true)

1. Branch: `feat/ec-experience-center-defect-remediation` from current `master`
2. All checklist items 0–14 and 15–17 `- [x]` with Evidence pasted in the plan (items 19–21 included in 0–14 gate before item 15)
3. **Invariant check** — all 7 groups PASS (paste verdict block in PR body)
4. **Live isolation (no-new-failures criterion, item 16):**
   ```bash
   cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
     app/tests/test_live_path_untouched_by_ec.py \
     app/tests/test_races_g2_frontend_isolation.py -q
   ```
   Accepted result: **exactly the two known pre-existing failures**, same node IDs, same lines (142 / 46) → `2 failed, 11 passed`. Any third failure blocks the PR.
5. Forbidden-path diff command above → empty output
6. **EC regression:**
   ```bash
   cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
     app/tests/test_s5_cisco_hardening_remediation.py \
     app/tests/test_s2_ai_application_security.py \
     app/tests/test_s3_firewall_team_coordination.py \
     app/tests/test_ec_s4_siem_first.py \
     app/tests/test_s6_investigation_continuity.py \
     app/tests/test_s7_conflicting_ot_evidence.py \
     app/tests/test_ec_siem_first_investigation.py -q
   ```
   → `0 failed`
   ```bash
   cd frontend && npm run test -- src/components/ec/ src/lib/ecOperationalLink.test.ts && npm run build
   ```
   → PASS (note: `npm run test` already expands to `vitest run`; do not add `--run`)
7. **Architecture freeze:** `sha256sum architecture.md` = `c1c4ba8a88d8f245752188a76442102978eceb0c1bdb410717b789649fb9a034`
8. PR body includes `EC_DEFECT_REMEDIATION_STATUS` block (template below)
9. No secrets in diff: `git diff origin/master...HEAD | grep -riE 'password\s*=|api_key\s*=|BEGIN (RSA|OPENSSH)'` → clean

## Merge conditions (human gate — the agent never merges)

**This repo has no CI.** Local gate output pasted into the PR body is the only evidence. Do not wait for checks that will never run.

Merge to `master` only when:

1. PR approved by repo owner / COE reviewer (CTO/CSO demo sign-off)
2. All 9 PR conditions above satisfied, with output pasted in the PR body
3. `/invariant-check` re-run on the final PR head — 7/7 PASS
4. `git diff --name-only origin/master...HEAD -- architecture.md` → empty
5. Plan checklist re-audit: `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-18_1522_ec-experience-center-defect-remediation.md` → 0 GAP
6. Owner has acknowledged the two **pre-existing** test failures as out-of-scope (they will still be red after merge)

**Merge mechanics:** merge with `--merge` (a merge commit), **never `--squash`**, per repo convention for plan branches.

**Do not merge** if any `EC_FORBIDDEN_PREFIXES` path appears in the diff, or invariant FAIL, or a third test failure appeared.

### Post-merge follow-up (owner, not a merge gate)

- Operator smoke: `/scenarios` → S5 → click each continue/action chip; policy rule visible in Layer 1 without opening Investigation path
- Update `plans/README.md` row → **Done** with PR number and evidence summary
- Open a separate issue/plan for the two pre-existing failures (stale `RACES_BASELINE_SHA`; missing `Session active` string)

## PR body template

```markdown
## Summary
- Layer 1: render `source_evidence` and closure summary for EC flagships
- S5: honest policy gating; missing_evidence/state/readiness agree; named follow-up journeys; **Cisco upgrade action journey shows HIL**
- Credibility: surface `production_validator_read_only` / live-call flags / fixture warnings (B3)
- Believability: relocate replay/fixture honesty from journey activity to badges/Layer 2 (C1)
- UX: continue chips keep answer + scroll to evidence; de-duplicate action headings
- Tests: S5 evidence-agreement contract + browser walk audit extension
- Deferred: A2 stage-order swap, B1 extra architecture phases, B2 synthesis messaging (follow-up plan)

## Scope
EC/demo only. No `EC_FORBIDDEN_PREFIXES` path touched. No new env flags. No backend schema change.

## Test plan (local gates — repo has no CI)
- [ ] EC flagship pytest slice → 0 failed  (paste)
- [ ] live isolation → 2 failed / 11 passed, known pre-existing only  (paste)
- [ ] forbidden-path diff → empty  (paste)
- [ ] vitest ec components  (paste)
- [ ] npm run build  (paste)
- [ ] invariant-check 7/7 PASS  (paste verdict)
- [ ] architecture.md SHA unchanged  (paste)

## Known pre-existing failures (NOT introduced here, NOT fixed here)
| Test | Line | Cause |
|---|---|---|
| `test_races_freeze_files_unchanged_since_baseline` | 142 | stale `RACES_BASELINE_SHA=bf7c304` |
| `test_g2_layer1_workspace_does_not_interpolate_internal_ids` | 46 | `Session active` string absent from `EcInvestigationWorkspace.tsx` |

## EC_DEFECT_REMEDIATION_STATUS
| Check | Result |
|-------|--------|
| Live /chat untouched (forbidden diff empty) | |
| architecture.md frozen (SHA match) | |
| S5 show_hardening_policy → rule visible Layer 1 | |
| S5 missing/state/readiness agree on all 4 items | |
| S5 state machine 14→15 | |
| S5 cisco.upgrade journey has HIL stage (A1) | |
| production_validator_read_only visible (B3) | |
| Journey activity: zero `Replaying` / `Fixture replay` / `captured Foundation-sec` / `configured fixture` on all `journey_for()` paths (C1) | |
| Invariant 7/7 | |
| No new test failures vs baseline | |
```

## Checklist

- [x] **0** — Plan audit, branch, and pre-existing-failure baseline capture
  - **Do:**
    1. `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-18_1522_ec-experience-center-defect-remediation.md` — fix any `GAP:`
    2. `git checkout -b feat/ec-experience-center-defect-remediation` from `master`
    3. **Capture the baseline before touching any code:**
       ```bash
       cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
         app/tests/test_live_path_untouched_by_ec.py \
         app/tests/test_races_g2_frontend_isolation.py -q 2>&1 | tail -20
       ```
       Paste the full failure list into Evidence. This is the reference item 16 compares against.
  - **Verify:** audit exit 0; `git branch --show-current` = `feat/ec-experience-center-defect-remediation`; Evidence contains the two known failure node IDs and `2 failed, 11 passed`
  - **Depends on:** none
  - **Evidence:** audit exit 0 (0 gap). Branch `feat/ec-experience-center-defect-remediation` @ `8093a75`. Baseline: `test_races_freeze_files_unchanged_since_baseline` (line 142), `test_g2_layer1_workspace_does_not_interpolate_internal_ids` (line 46) → **2 failed, 11 passed**.

- [x] **1** — Add `source_evidence` to the EC TypeScript contract
  - **Do:** In [`frontend/src/components/ec/types.ts`](../frontend/src/components/ec/types.ts) add:
    ```ts
    export interface EcSourceEvidenceItem {
      evidence_id: string;
      source_type: string;
      source_name: string;
      preview_rows?: Array<Record<string, unknown>>;
      provenance?: string | null;
      tool_name?: string | null;
    }
    ```
    and add `source_evidence?: EcSourceEvidenceItem[];` to `ExperienceCenterResponse`.
    **This is frontend types only.** The backend already emits `source_evidence` on the EC envelope (measured: S5 turn 0 returns `['ev-s5-breach','ev-s5-initial-version']`). Do **not** edit `backend/app/schemas/responses.py` — Hard STOP. Do not reuse `frontend/src/types/api.ts::SourceEvidenceEnvelope`; the EC types file is self-contained by design.
  - **Verify:** `cd frontend && npm run build`
  - **Depends on:** 0
  - **Evidence:** `npm run build` → PASS. Added `EcSourceEvidenceItem` + `source_evidence` on `ExperienceCenterResponse` in `types.ts`.

- [x] **2** — Layer-1 `EcSourceEvidencePanel`
  - **Do:** Add `frontend/src/components/ec/EcSourceEvidencePanel.tsx`. Render one card per `EcSourceEvidenceItem`: `source_name` as the card title, each `preview_rows` entry as key/value lines, and a provenance badge. Root element carries `data-ec-section="source-evidence"`. Accept an optional `highlightEvidenceId?: string | null` prop; when it matches `evidence_id`, set `data-ec-evidence-highlight="true"` and a ring class (mirror the highlight styling already in `EcActionReadinessPanel`).
    **Exact enum values measured in the fixtures — do not invent others:**
    - `provenance` ∈ `experience_center_fixture` | `simulated_mcp` | `ec_scenario_policy`
    - `source_type` ∈ `splunk_mcp_fixture` | `cisco_mcp_fixture` | `kb_fixture` | `itsm_fixture`
    Unknown values must render the raw string, never crash.
  - **Verify:** new `frontend/src/components/ec/EcSourceEvidencePanel.test.tsx` renders a `kb_fixture` item whose `preview_rows[0].rule` is `A compromised device running version 14 must be upgraded to version 15` and asserts that string is in the DOM. `cd frontend && npm run test -- src/components/ec/EcSourceEvidencePanel.test.tsx`
  - **Depends on:** 1
  - **Evidence:** `npm run test -- src/components/ec/EcSourceEvidencePanel.test.tsx` → 1 passed; policy rule string in DOM.

- [x] **3** — Wire evidence panel into the SOC answer
  - **Do:** In [`EcInvestigationAnswer.tsx`](../frontend/src/components/ec/EcInvestigationAnswer.tsx) render `<EcSourceEvidencePanel />` inside Layer 1 when `envelope.source_evidence?.length`. Placement: **after** the important-evidence block (`analyst.important_evidence`, currently read at line 65) and **before** the collapsible scope section. It must be inside `data-ec-layer="soc-answer"`.
  - **Verify:** `cd frontend && npm run test -- src/components/ec/flagshipWorkspace.test.tsx` with a mock envelope carrying a `kb_fixture` item; assert the rule text is inside `[data-ec-layer="soc-answer"]`
  - **Depends on:** 2
  - **Evidence:** `npm run test -- src/components/ec/flagshipWorkspace.test.tsx` → `renders source evidence inside the SOC answer layer` PASS.

- [x] **4** — Closure summary panel
  - **Do:** Add `EcClosureSummaryCard` as an exported component **inside [`EcInvestigationQuality.tsx`](../frontend/src/components/ec/EcInvestigationQuality.tsx)** (single location — do not create a new file). It takes `summary: string` and renders `data-ec-section="closure-summary"`. Render it from `EcInvestigationAnswer.tsx` in Layer 1 when `envelope.ec_investigation_outcome?.closure_summary` is non-empty. Add `closure_summary?: string | null` to the outcome type in `types.ts` if absent.
    **Scope note:** the chip is `generate_closure_summary` in S1, S2, S3, S5, S6, S7. **S4 has no such chip** — it uses `generate_executive_summary` and is out of scope for this item. Do not add a chip to S4.
  - **Verify:** `cd frontend && npm run test -- src/components/ec/` — a mock envelope with `closure_summary` renders the text; without it, `[data-ec-section="closure-summary"]` is absent
  - **Depends on:** 3
  - **Evidence:** `npm run test -- src/components/ec/flagshipWorkspace.test.tsx` → closure summary present/absent test PASS; `npm run build` PASS.

- [x] **5** — S5 honest initial narrative (D2)
  - **Do:** In [`backend/app/demo/fixtures/s5/pack.py`](../backend/app/demo/fixtures/s5/pack.py) `build_s5_turn()`:
    - `found=` is currently a static f-string `"Policy applies because the device is affected, current_version={version}, and the breach condition is met."`. Make it **conditional on `"show_hardening_policy" in applied`**: before policy, state only breach + `current_version=14` and that policy applicability is not yet established; after policy, the current text is correct.
    - `assessment=` currently asserts "a compromised device running version 14 must be upgraded to version 15" on turn 0. Apply the same conditional split.
    **Do not touch** `_base_outcome()["missing_evidence"]` here — item 6 owns it. **Do not change** the `ev-s5-policy` `rule` string; item 14 asserts a substring of it. **Do not change** the `important=[...]` list; its "Policy is EC scenario policy, not vendor production guidance" line is a disclaimer, not a claim of applicability.
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -c "
    from app.demo.fixtures.s5.pack import build_s5_turn
    a=build_s5_turn(session_id='v5a',turn=0,applied_follow_up_ids=[]).model_dump()['analyst']
    b=build_s5_turn(session_id='v5b',turn=0,applied_follow_up_ids=['show_hardening_policy']).model_dump()['analyst']
    assert 'Policy applies' not in a['what_we_found'], a['what_we_found']
    assert 'Policy applies' in b['what_we_found'], b['what_we_found']
    print('OK')"
    ```
    plus `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s5_cisco_hardening_remediation.py -q` → 0 failed
  - **Depends on:** 0
  - **Evidence:** item-5 verify script OK; `pytest app/tests/test_s5_cisco_hardening_remediation.py -q` → 5 passed.

- [x] **6** — S5 missing_evidence / state / readiness agreement (D3, D4, D5)
  - **Do:** Enforce the **Governing invariant**. Three edits, all required:
    1. **`pack.py` `_base_outcome()`** — remove `"cisco.get_version"` from the initial `missing_evidence` list. Rationale (locked user decision): `ev-s5-initial-version` is added unconditionally at `pack.py:200` and `cisco_version` is set `OBTAINED` at `pack.py:202`, so the version genuinely *is* obtained on turn 0. The readiness row is correct; the missing list was the lie. **Do not defer the initial version evidence** — that would contradict the locked decision and `S5_INITIAL_TITLES[5]` "Version 14 identified".
    2. **`pack.py` `_apply()`, `check_maintenance_window` branch (line ~113)** — add the missing filter, matching the pattern already used for policy and version:
       ```python
       outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "maintenance" not in item.lower()]
       ```
    3. **[`ec_remediation_s5.py`](../backend/app/demo/ec_remediation_s5.py) line 75** — replace `if "check_current_version" in applied or version:` with a condition that reflects *evidence actually present*, not `version` truthiness (`version` is always ≥14, so the current test is always true) and not `applied` membership alone (after `execute_upgrade`+`verify_version` without `check_current_version`, an `applied`-only test would flip the row back to `RECOMMENDED`). Correct form:
       ```python
       if True:  # version evidence is obtained on every S5 turn (initial probe + any refresh)
       ```
       i.e. set row 1 to `OBTAINED` unconditionally, and drop the now-dead `version` operand. Keep the `RECOMMENDED` default row in the list for readability but note in Evidence that it is always overridden.
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -c "
    from app.demo.fixtures.s5.pack import build_s5_turn
    for ap in ([], ['show_hardening_policy'], ['check_maintenance_window'], ['show_hardening_policy','check_current_version','check_maintenance_window']):
        d=build_s5_turn(session_id='v6-'+('-'.join(ap) or 'init'),turn=0,applied_follow_up_ids=ap).model_dump()
        m=d['ec_investigation_outcome']['missing_evidence']
        r={x['action']:x['state'] for x in d['ec_action_readiness']}
        assert not any('get_version' in i for i in m), (ap,m)
        assert r['Confirm current version (cisco.get_version)']=='OBTAINED', (ap,r)
        if 'check_maintenance_window' in ap:
            assert not any('maintenance' in i.lower() for i in m), (ap,m)
        if 'show_hardening_policy' in ap:
            assert not any('policy' in i.lower() for i in m), (ap,m)
    print('OK')"
    ```
  - **Depends on:** 5
  - **Evidence:** item-6 verify script OK. Edit 1: `_base_outcome()` dropped `cisco.get_version` from missing list. Edit 2: maintenance branch filters missing_evidence. Edit 3: `build_s5_action_readiness` sets version row OBTAINED unconditionally.

- [x] **7** — S5 named follow-up journeys (D11)
  - **Do:** In [`ec_journeys.py`](../backend/app/demo/ec_journeys.py), add five entries to `_FOLLOW_UPS["s5_cisco_hardening_remediation"]` (currently at line ~758, holding only the five action chips): `show_hardening_policy`, `check_current_version`, `check_maintenance_window`, `update_incident`, `generate_closure_summary`. Build them with the existing `_continue(...)` helper (same shape as the `s6_investigation_continuity` entries at line ~766) with scenario-specific stage titles — not the generic `_fallback_non_initial`. The `show_hardening_policy` journey's stage titles must mention the hardening policy / knowledge source.
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -c "
    from app.demo.ec_journeys import journey_for
    for f in ['show_hardening_policy','check_current_version','check_maintenance_window','update_incident','generate_closure_summary']:
        j=journey_for('s5_cisco_hardening_remediation',[f]); assert j is not None, f
        print(f, [s.title for s in j.stages])
    j=journey_for('s5_cisco_hardening_remediation',['show_hardening_policy'])
    assert any('polic' in s.title.lower() for s in j.stages)
    print('OK')"
    ```
    plus `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s5_cisco_hardening_remediation.py -q` → 0 failed
  - **Depends on:** 5
  - **Evidence:** item-7 verify script OK (5 named follow-ups); s5 pytest 5 passed.

- [x] **8** — S5 initial journey / policy step alignment
  - **Do:** In `ec_journeys.py`, `S5_INITIAL_TITLES` (line ~52) and `s5_initial()` (line ~263) currently claim policy retrieval on the initial turn: `titles[6] = "Retrieving hardening policy"` with activity `"Retrieving EC hardening policy…"`, and `titles[7] = "Evaluating policy applicability"`. **Reword both to a planning/pending framing** (e.g. "Identifying applicable hardening policy source" / "Deferring policy applicability to analyst review") so nothing claims the policy was obtained.
    **Structural trap — read before editing:** `S5_INITIAL_TITLES` is a 10-element tuple indexed positionally as `titles[0]`…`titles[9]` inside `s5_initial()`. **Reword in place; do not delete entries.** Deleting one shifts every later index and raises `IndexError`. Tuple length must stay 10 and the `specs` list must stay 10 entries.
    Leave `titles[4]` ("Checking R-17 version") and `titles[5]` ("Version 14 identified") **unchanged** — the version probe is honest per the locked decision and `test_s5_initial_journey_titles_disclose_version_14_as_fixture_replay` pins `outcome_change="current_version=14"`.
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -c "
    from app.demo.ec_journeys import S5_INITIAL_TITLES, s5_initial
    assert len(S5_INITIAL_TITLES)==10
    j=s5_initial(); assert len(j.stages)==10
    blob=' '.join(list(S5_INITIAL_TITLES)+[a for s in j.stages for a in s.activity]).lower()
    assert 'retrieving hardening policy' not in blob and 'retrieving ec hardening policy' not in blob, blob
    assert 'version 14 identified' in ' '.join(S5_INITIAL_TITLES).lower()
    print('OK')"
    ```
    plus `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s5_cisco_hardening_remediation.py -q` → 0 failed
  - **Depends on:** 7, 19
  - **Evidence:** item-8 verify script OK; s5 pytest 5 passed.

- [x] **19** — S5 Cisco upgrade action journey shows HIL (A1)
  - **Do:** In [`ec_journeys.py`](../backend/app/demo/ec_journeys.py) `_cisco_action()` (~line 490), non-verify branch currently: Select → Connect → Record receipt. **Mirror `_firewall_action` non-verify** by inserting a third stage before receipt:
    ```python
    ("Approval required", "hil", "No production device change until Execute…"),
    ```
    between Connect and Record receipt. Verify branch unchanged. **Do not** change the action FSM in `ec_actions` — animation only. Applies to `approve_upgrade` and `execute_upgrade` follow-up journeys that call `_cisco_action`.
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -c "
    from app.demo.ec_journeys import journey_for
    j=journey_for('s5_cisco_hardening_remediation',['execute_upgrade'])
    assert any(s.semantic_type=='hil' for s in j.stages), [s.semantic_type for s in j.stages]
    print('OK')"
    ```
    plus extend `test_s5_cisco_hardening_remediation.py` (same file — gate allowlist) asserting `execute_upgrade` journey includes a `hil` stage.
  - **Depends on:** 7
  - **Evidence:** item-19 verify OK; `test_s5_execute_upgrade_journey_includes_hil_stage` added; s5 pytest 5 passed.

- [x] **20** — Surface credibility markers (B3)
  - **Do:** Add `EcCredibilityStrip` exported from [`EcInvestigationQuality.tsx`](../frontend/src/components/ec/EcInvestigationQuality.tsx) (same file family as item 4 — **no new top-level file**). Render from [`EcInvestigationAnswer.tsx`](../frontend/src/components/ec/EcInvestigationAnswer.tsx) at the **bottom of Layer 1** (`data-ec-section="credibility-strip"`), compact badges not a wall of negation:
    1. `ec_provenance.live_llm_called` / `live_mcp_called` / `live_rag_called` — show `Live model: off` / `Live MCP: off` / `Live RAG: off` when false (measured default on all flagships).
    2. When `envelope.ec_spl_governance?.validation?.provenance === 'production_validator_read_only'` **or** `envelope.ec_provenance?.production_validator_read_only === true` — badge `SPL: production validate_spl`.
       **Measured field paths (do not guess):** `ec_spl_governance.validation` = `{engine:"validate_spl", provenance:"production_validator_read_only", search_1_approved:true, search_2_approved:true, override:false}` on S1. `production_validator_read_only` lives under **`ec_provenance`**, and is **not** a top-level envelope field — reading `envelope.production_validator_read_only` returns `undefined` and the badge silently never renders.
    3. Fixture-data badge `Fixture data · not live customer telemetry`. **Measured — the token and the array are on different objects:**
       - `spl_validation.warnings` = `['demo_fixture_not_live_data']`
       - `source_evidence[].warnings` = `['coe_synthetic_fixture', 'no_live_customer_data']` / `['coe_synthetic_fixture', 'partial_coverage_only']`
       Render the badge when **either** `envelope.spl_validation?.warnings?.includes('demo_fixture_not_live_data')` **or** any `source_evidence[].warnings` contains `coe_synthetic_fixture` or `no_live_customer_data`. Do **not** look for `demo_fixture_not_live_data` inside `source_evidence[].warnings` — it is never there, and the badge would never render.
    4. When `scenario_id === 's5_cisco_hardening_remediation'` — footnote line distinguishing **Cisco device MCP (simulated router API)** from **Foundation-Sec 8B (not used on this path)**.
    **No new backend fields.** Read only fields already on `ExperienceCenterResponse` / `ec_provenance` / `ec_spl_governance`.
  - **Verify:** vitest in `src/components/ec/` — mock S1 envelope shows `production validate_spl` badge; mock S5 shows device-MCP vs Foundation-Sec distinction; `grep -rn production_validator_read_only frontend/src/components/ec/EcInvestigationAnswer.tsx` matches
  - **Depends on:** 3
  - **Evidence:** vitest `renders credibility strip badges for S1 validator and S5 device MCP footnote` PASS; `EcCredibilityStrip` wired in `EcInvestigationAnswer.tsx`.

- [x] **21** — Believable journey activity copy (C1)
  - **Do:** In [`ec_journeys.py`](../backend/app/demo/ec_journeys.py) `_LLM_ACTIVITY` and per-scenario `InitialStepSpec.activity` / `_cisco_action` / S1 saved-search stages: **replace CIO-visible demo-tell substrings** with believable operator copy. Relocate provenance to item-20 badges and existing Layer-2 provenance — do **not** remove honesty, **relocate** it.
    **Scope is every journey reachable from `journey_for()` — initial AND follow-up/action journeys.** Measured: `ec_journeys.py` contains **11** `Replaying` occurrences; only 3 sit on initial journeys. The rest are on follow-up/action journeys the visitor also watches, including `_cisco_action` line ~500 (`"Replaying cisco.get_version…"`) and lines ~613 / ~658 / ~685 / ~697. An initial-journey-only edit leaves the action animation full of demo tells.

    **Banned substrings (case-sensitive), zero hits in any stage `activity` string on any journey:**
    - `Fixture replay`
    - `Replaying`  (the whole token — this subsumes `Replaying approved saved search`, `Replaying first governed Splunk search`, `Replaying approved detection`, `Replaying the version probe`, `Replaying cisco.get_version`)
    - `captured Foundation-sec`
    - `configured fixture`
    **Example direction (not optional verbatim):** `Executing governed Splunk search…` + simulated badge; `Reading device version via governed MCP…` instead of `Fixture replay: current_version=14`.
    **`_LLM_ACTIVITY` caution:** that one list holds **two** strings from different findings. Replace the `Loading captured Foundation-sec instruct signal…` line (C1, in scope). **Leave `Final synthesis disabled for Experience Center` exactly as-is** — that is B2, deferred to the follow-up plan. Editing it here is out of scope; so is deleting the list.

    **Out of scope:** item 8 already owns S5 **policy stage titles** in `S5_INITIAL_TITLES` — do not re-edit those here except activity lines item 8 did not touch. **Out of scope:** A2 stage order / B2 synthesis-disabled string (follow-up).
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -c "
    from app.demo.ec_journeys import _INITIAL, _FOLLOW_UPS, journey_for
    banned=('Fixture replay','Replaying','captured Foundation-sec','configured fixture')
    seen=0
    def check(tag, j):
        global seen
        if j is None: return
        seen+=1
        blob=' '.join(a for s in j.stages for a in (s.activity or []))
        for b in banned:
            assert b not in blob, (tag,b,blob[:200])
    for sid in _INITIAL:
        check(('initial',sid), journey_for(sid, []))
    for sid, m in _FOLLOW_UPS.items():
        for fid in m:
            check((sid,fid), journey_for(sid, [fid]))
    assert seen >= 30, seen
    print('OK journeys checked:', seen)"
    ```
    plus `pytest app/tests/test_s1_governed_splunk_investigation.py app/tests/test_s5_cisco_hardening_remediation.py -q` → 0 failed (journey title pins may need title-only updates if tests assert exact activity strings — update **tests only** to match new copy, never weaken assertions)
  - **Depends on:** 8, 19, 20
  - **Evidence:** journey gate OK journeys checked: 58; `pytest test_s1 + test_s5` → 23 passed.

- [x] **9** — Continue-chip UX: keep the answer visible (D7)
  - **Do:** In [`EcInvestigationWorkspace.tsx`](../frontend/src/components/ec/EcInvestigationWorkspace.tsx) line ~162, `keepAnswer` is currently `isActionChip(chip)` (`chip.group === 'action' || chip.leads_to_action`, line 35). Extend it so **evidence continue chips also keep the answer**: a chip whose `follow_up_id` starts with `show_` or `check_` and which is **not** an action chip gets `keepAnswer: true`. These use the existing action-progress slot (`setActionProgress`, line 91) rather than resetting `revealed` at line 168. Action chips keep their current behaviour exactly.
    **Pre-existing red test in this file — read the Pre-existing failure baseline section.** `test_g2_layer1_workspace_does_not_interpolate_internal_ids` already fails at line 46 because the literal `Session active` is absent. Do **not** re-add that string and do **not** edit the assert. After your change, that test must still fail on **line 46 only**; the other four asserts (`ec_fixture_selected`, `route_source`, `experience_center_fixture`, `simulated_phase10_action` all absent) must still pass. Practically: **do not introduce any of those four literals** into this file.
  - **Verify:**
    ```bash
    cd frontend && npm run test -- src/components/ec/
    cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_races_g2_frontend_isolation.py -q
    ```
    Second command must still be `1 failed, 4 passed`, failing at line 46. New/extended vitest asserts that a `show_*` chip click leaves the answer mounted.
  - **Depends on:** 3
  - **Evidence:** vitest ec components → 32 passed; `test_races_g2_frontend_isolation.py` → 1 failed, 4 passed (line 46 only).

- [x] **10** — Operational link for continue chips (D8)
  - **Do:** In [`ecOperationalLink.ts`](../frontend/src/lib/ecOperationalLink.ts) add to `READINESS_BY_FOLLOW_UP`:
    ```ts
    show_hardening_policy: 'Review hardening policy',
    check_current_version: 'Confirm current version',
    ```
    (`EcActionReadinessPanel` matches with `row.action.toLowerCase().includes(normalizedHighlight)`, so the short form correctly matches the row `Confirm current version (cisco.get_version)` — verified.)
    Add a **second, separate** exported map for evidence scrolling — do not overload `readinessLabelForActionChip`:
    ```ts
    export function evidenceIdForChip(chip?: EcFollowUpChip | null): string | null
    ```
    returning `show_hardening_policy → 'ev-s5-policy'`, `check_current_version → 'ev-s5-version'`, `check_maintenance_window → 'ev-s5-window'`, else `null`. Wire its result into `EcSourceEvidencePanel`'s `highlightEvidenceId` from `EcInvestigationWorkspace.tsx`, and remove the `isActionChip(chip)` guard at line 166 so continue chips can also produce a readiness label.
  - **Verify:** `cd frontend && npm run test -- src/lib/ecOperationalLink.test.ts src/components/ec/` — asserts `evidenceIdForChip` mapping and that after a `show_hardening_policy` click the DOM has `[data-ec-evidence-highlight="true"]`
  - **Depends on:** 9
  - **Evidence:** `ecOperationalLink.test.ts` → 4 passed; highlight test in `flagshipWorkspace.test.tsx` PASS.

- [x] **11** — De-duplicate action headings (D9)
  - **Do:** Two headings currently render the identical literal `Recommended actions`. **Both change:**
    - [`EcFollowUpBar.tsx`](../frontend/src/components/ec/EcFollowUpBar.tsx) line 39 → `Take action`
    - [`EcInvestigationQuality.tsx`](../frontend/src/components/ec/EcInvestigationQuality.tsx) line 85 (inside `EcActionReadinessPanel`) → `Action readiness`
    (Rev 1 said "keep `EcActionReadinessPanel` as 'Action readiness'" — it does **not** currently say that; it must be changed.)
  - **Verify:** `cd frontend && npm run test -- src/components/ec/` — a workspace mock renders exactly one `Take action` and exactly one `Action readiness`, and zero `Recommended actions`
  - **Depends on:** 9
  - **Evidence:** vitest heading de-dupe test PASS (`Take action` + `Action readiness`, zero `Recommended actions`).

- [x] **12** — S2/S4 policy evidence surfacing (D10, cross-scenario)
  - **Do:** Verified chip IDs: S2 `show_ai_security_policy` ([`fixtures/s2/pack.py:35`](../backend/app/demo/fixtures/s2/pack.py), applied at line 115); S4 `show_advisory` and `show_hardening_guidance` ([`fixtures/s4/pack.py:31,35`](../backend/app/demo/fixtures/s4/pack.py), applied at lines 79 and 142). Confirm each branch appends a `source_evidence` item with a **distinct** `evidence_id`, and clears the matching entry from `missing_evidence` (mirror the S5 filter pattern from item 6). Add whichever is absent. **No new backend fields** — the Layer-1 panel from item 3 already reads `source_evidence`.
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
      app/tests/test_s2_ai_application_security.py app/tests/test_ec_s4_siem_first.py -q
    ```
    → 0 failed, with added assertions that each of the three chips yields a distinct `evidence_id` in `source_evidence` and leaves no matching `missing_evidence` entry
  - **Depends on:** 3, 6
  - **Evidence:** `pytest test_s2 + test_ec_s4_siem_first` → 13 passed; policy chip assertions added.

- [x] **13** — S5 backend contract tests (Governing invariant)
  - **Do:** Extend [`test_s5_cisco_hardening_remediation.py`](../backend/app/tests/test_s5_cisco_hardening_remediation.py) (do **not** create a new backend test file — only `test_ec_*` names are in `EC_ALLOWED_PREFIXES`). Add:
    1. `test_s5_evidence_surfaces_agree` — loop the four evidence items (version / policy / change ticket / maintenance window) over the full follow-up sequence from `test_s5_state_machine_14_to_15` and assert the **Governing invariant**: nothing in `missing_evidence` is simultaneously `OBTAINED` in `ec_evidence_state` or `ec_action_readiness`.
    2. After `show_hardening_policy`: `source_evidence` contains an item whose `preview_rows` include the rule string; before it, no policy item and policy not in `confirmed`.
    3. After `generate_closure_summary`: `ec_investigation_outcome["closure_summary"]` is non-empty.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s5_cisco_hardening_remediation.py -q` → 0 failed
  - **Depends on:** 5, 6, 7
  - **Evidence:** `pytest test_s5_cisco_hardening_remediation.py -q` → 8 passed (incl. `test_s5_evidence_surfaces_agree`, policy gate, HIL).

- [ ] **14** — Browser walk audit extension
  - **Do:** Extend [`scripts/ec_browser_walk_audit.mjs`](../scripts/ec_browser_walk_audit.mjs): after S5 initial, click “Show hardening policy”, assert Layer 1 contains the substring `version 14 must be upgraded to version 15`; record `scenarios.S5.policy_visible_after_chip` in `ec-walk-report.json`.
  - **Verify:** `node scripts/ec_browser_walk_audit.mjs` (Docker stack up) → `report.scenarios.S5.policy_visible_after_chip === true`. **If the stack is unavailable**, record Evidence as `SKIP: stack down` **and** paste the item-13 pytest output as the substitute contract proof. A skip here does not excuse any pytest/vitest gate.
  - **Depends on:** 3, 9, 10
  - **Evidence:** _(fill when done)_

- [ ] **15** — Invariant check (pre-PR)
  - **Do:** Run `/invariant-check` against the full branch diff (`git diff origin/master...HEAD`); fix any FAIL; paste the 7-group verdict block into Evidence
  - **Verify:** all 7 groups PASS; EC purity confirmed (no live MCP/LLM call in `backend/app/demo/`); forbidden-path diff command (Commit hygiene section) → empty output
  - **Depends on:** 1–14, 19, 20, 21
  - **Evidence:** _(fill when done)_

- [ ] **16** — Live-path isolation gate (**no-new-failures**, not zero-failures)
  - **Do:** Run the isolation tests unchanged. Compare against the item-0 baseline.
  - **Verify:**
    ```bash
    cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
      app/tests/test_live_path_untouched_by_ec.py \
      app/tests/test_races_g2_frontend_isolation.py -q
    ```
    **Pass criterion:** result is exactly `2 failed, 11 passed`, and the two failing node IDs / lines are identical to the item-0 baseline (`test_races_freeze_files_unchanged_since_baseline` line 142; `test_g2_layer1_workspace_does_not_interpolate_internal_ids` line 46). **A third failure, or a different failing node, is a FAIL — fix your change, never the test.** Bumping `RACES_BASELINE_SHA` is a Hard STOP.
  - **Depends on:** 15
  - **Evidence:** _(fill when done — paste both baseline and current output)_

- [ ] **17** — Frontend build + EC vitest sweep
  - **Do:** none beyond running the gate
  - **Verify:** `cd frontend && npm run test -- src/components/ec/ src/lib/ecOperationalLink.test.ts && npm run build`
  - **Depends on:** 15
  - **Evidence:** _(fill when done)_

- [ ] **18** — Push branch and open PR — **STOP; do not merge**
  - **Do:** Push `feat/ec-experience-center-defect-remediation`; open a PR against `master` using the PR body template with every gate's output pasted; verify all 9 PR conditions; then **stop and hand to the owner**. The executing agent must not merge, must not `gh pr merge`, and must not mark the plan Done.
  - **Verify:** `gh pr view --json url,state` returns an open PR; PR body contains all pasted gate outputs and the `EC_DEFECT_REMEDIATION_STATUS` table filled in; `sha256sum architecture.md` unchanged. Final line of Evidence must read `AWAITING OWNER MERGE APPROVAL`.
  - **Depends on:** 16, 17
  - **Evidence:** _(fill when done)_

## Invariant check matrix (run at item 15 and before each commit)

| # | Group | EC-specific expectation |
|---|-------|-------------------------|
| 1 | LLM↔MCP | No new `call_tool` in diff; EC does not call production MCP |
| 2 | SPL | No change to validator or execution gate; EC `candidate_spl` stays null/non-executable |
| 3 | EC purity | `live_llm_called=false`; fixtures only; `production_side_effect=false` on actions |
| 4 | Secrets | No credentials in fixtures/tests; email drafts stay redacted |
| 5 | State | No `pipeline.py` diff at all (file is forbidden) |
| 6 | Flags | No new env flags |
| 7 | Tests | No deleted/weakened assertions; no `RACES_BASELINE_SHA` bump; new tests prove defect fixes |

## Verification gaps (pre-implementation)

- Item 14 requires a local Docker stack; documented skip path is defined in the item.
- Items 0 and 16 depend on the **Pre-existing failure baseline** section being accurate. It was measured on `master` at plan revision 2. If the baseline has drifted when item 0 runs, record the new baseline in item 0 Evidence and use that; do not "fix" the drift inside this plan.

## Drift log

| Date | Note |
|------|------|
| 2026-08-18 | Plan created from EC audit (R-17 / S5 + cross-flagship). S5 policy: honest gating locked. |
| 2026-08-18 | **Rev 3.1 — measured traps in items 19–21.** Item 20: `production_validator_read_only` is on `ec_provenance` (not top-level); fixture badge reads `spl_validation.warnings` **or** `source_evidence[].warnings` (`demo_fixture_not_live_data` never on source_evidence). Item 21: Verify walks `_INITIAL` + `_FOLLOW_UPS` via `journey_for()` (53 journeys); bans whole `Replaying` token; `_LLM_ACTIVITY` — replace `captured Foundation-sec` only, leave B2 `Final synthesis disabled…` untouched. Checklist count = **22 items** (0–18 + 19–21). |
| 2026-08-18 | **Rev 3 — architecture fidelity audit.** Incorporated [`docs/evals/ec_architecture_fidelity_audit_2026-08-18.md`](../docs/evals/ec_architecture_fidelity_audit_2026-08-18.md). **In branch:** A1→item 19 (Cisco HIL stage), B3→item 20 (credibility strip), C1→item 21 (journey copy relocation). **Deferred:** A2 llm/outcome order, B1 missing phases, B2 synthesis-disabled messaging. Purity PASS — no work. Overlap explicit: items 2–3/6/8 unchanged owners. Commits C3/C4/C5 renumbered to C3–C6. |
| 2026-08-18 | **Rev 2 — plan review.** Corrected item 6: rev 1 told the executor to make the version readiness row `RECOMMENDED` on turn 0, which contradicts the locked user decision and the unconditional `ev-s5-initial-version` / `cisco_version=OBTAINED` in `pack.py:200–202`. The real defect is `missing_evidence` disagreeing; added the Governing invariant. Removed the rev-1 "pick one" fork. Documented two **pre-existing red tests** and changed item 16 to a no-new-failures gate (rev 1's "0 failed" was unpassable on `master`). Corrected D9/item 11 — `EcActionReadinessPanel` renders `Recommended actions`, not `Action readiness`. Added index-alignment warning for `S5_INITIAL_TITLES`. Pinned provenance/source_type enums. Verified S2/S4 chip IDs. Noted S4 has no `generate_closure_summary`. Merge conditions: repo has no CI → local gates are the only evidence; item 18 stops at PR; `--merge` not `--squash`; moved operator smoke to post-merge. Item 1 folded into commit C1. Unified the forbidden-path diff command. |

## Related

- Prior EC foundation: [`2026-08-16_2310_races-experience-center.md`](2026-08-16_2310_races-experience-center.md) (DONE)
- UX shell: [`2026-08-17_races-investigation-execution-ux.md`](2026-08-17_races-investigation-execution-ux.md) (COMPLETE)
- Loop runner: [`LOOP_RUNNER_ec-experience-center-defect-remediation.md`](LOOP_RUNNER_ec-experience-center-defect-remediation.md)
- Handoff review: [`review.md`](../review.md)
- Fidelity audit: [`docs/evals/ec_architecture_fidelity_audit_2026-08-18.md`](../docs/evals/ec_architecture_fidelity_audit_2026-08-18.md)
