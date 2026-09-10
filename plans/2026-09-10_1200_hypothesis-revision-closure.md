---
name: hypothesis-revision-closure
overview: "Assess InvestigationPlan hypotheses against admitted SourceEvidence on the existing PlanDelta/evidence-reasoning seam; no second planner, no new public outcome enum."
status: active
date: 2026-09-10
canonical_plan: plans/2026-09-10_1200_hypothesis-revision-closure.md
---

# Evidence-driven hypothesis revision closure

## Objective

Hypotheses are preserved today but not revised as SourceEvidence arrives. Extend the existing PlanDelta evidence-reasoning seam with a bounded DET-validated assessment so at least one controlled case shows genuine evidence-driven hypothesis evolution. Do not reopen T1–T4, routing, InvestigationPlan generation architecture, Resource Planner topology, P11, MCP authority, or `architecture.md`.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Dependency order

`1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9`

## Checklist

- [x] **1** — Bounded assessment contract + stable IDs
  - **Do:** Add `app/chat/hypothesis_assessment.py`: stable `hN` identity from plan order, internal assessments `supported|unconfirmed|weakened`, DET that supports only admitted environment SourceEvidence IDs. Public lists stay supported/unconfirmed.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_hypothesis_assessment.py -q`
  - **Depends on:** none
  - **Evidence:** `pytest app/tests/test_hypothesis_assessment.py -q` → 14 passed (included in the 67-pass focused batch).

- [x] **2** — PlanDelta owns READ#1 assessment
  - **Do:** Include `current_hypotheses` in the PlanDelta prompt; extract `hypothesis_assessments` from the same JSON before `PlanDeltaProposal` validation; store on pipeline state.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_governed_reasoning_context.py app/tests/test_p7_bounded_plan_delta.py -q`
  - **Depends on:** 1
  - **Evidence:** `test_governed_reasoning_context.py` + `test_p7_bounded_plan_delta.py` green in the 67-pass batch; prompt now includes `current_hypotheses`.

- [x] **3** — Re-assess at outcome when PlanDelta does not run
  - **Do:** `refresh_hypothesis_assessments` in `graph_node_context_finalize`; `_classify_hypotheses` consumes DET-validated assessments; weakened stays unconfirmed publicly.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_analyst_evidence_projection.py app/tests/test_investigation_outcome.py app/tests/test_hypothesis_assessment.py -q`
  - **Depends on:** 1, 2
  - **Evidence:** analyst projection + investigation_outcome + hypothesis_assessment tests green (67-pass batch). Substring-support tests still pass when no assessment package is present.

- [x] **4** — Synthesis narrates evolution
  - **Do:** Deterministic draft + narration prompt read `provenance.hypothesis_assessment.evolution_summary` (no internal IDs required).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_hypothesis_assessment.py -k synthesis -q`
  - **Depends on:** 3
  - **Evidence:** `pytest app/tests/test_hypothesis_assessment.py -k synthesis -q` → 1 passed, 13 deselected.

- [x] **5** — Generic floor + data_category parity
  - **Do:** Prefer RQC competing hypotheses over boilerplate skeleton lines. Merge canonical categories implied by `evidence_needed` into `data_categories`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_hypothesis_revision_parity.py -q`
  - **Depends on:** none
  - **Evidence:** `test_hypothesis_revision_parity.py` green in the 67-pass batch (X10-shaped network+change parity + unrelated auth case).

- [x] **6** — Controlled MCP revision + negatives + generalization
  - **Do:** Extend admin-tool revision test with a trace table; unit negatives (support/weaken/neutral/no-evidence/RAG/user-claim/tool-failure); five generic sequences; no-revision-needed control.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_hypothesis_revision.py app/tests/test_hypothesis_assessment.py app/tests/test_hypothesis_revision_parity.py -q`
  - **Depends on:** 1, 2, 3, 5
  - **Evidence:** `test_controlled_hypothesis_revision.py` + lifecycle suite 65 passed in 56.74s; unit negatives/generalization in `test_hypothesis_assessment.py`.

- [x] **7** — Focused regression
  - **Do:** Run controlled lifecycle, PlanDelta, InvestigationOutcome, T4 investigation authority, and frontend unit tests already covering these packages.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_soc_lifecycle_acceptance.py app/tests/test_p7_bounded_plan_delta.py app/tests/test_t4_out_of_registry_investigation_authority.py app/tests/test_investigation_outcome.py -q`
  - **Depends on:** 6
  - **Evidence:** lifecycle + T4 investigation authority + compound/plan tests 65 passed; additional p8/p13/taxonomy/plan-delta 77 passed; frontend `npm test` → 129 passed / 29 files.

- [x] **8** — architecture.md unchanged
  - **Do:** Confirm `architecture.md` is unmodified.
  - **Verify:** `git diff -- architecture.md`
  - **Depends on:** 1
  - **Evidence:** `git diff -- architecture.md` empty.

- [x] **9** — Re-audit checklist
  - **Do:** Re-walk every item against its Verify field.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-09-10_1200_hypothesis-revision-closure.md`
  - **Depends on:** 1, 2, 3, 4, 5, 6, 7, 8
  - **Evidence:** audit-plan-discipline.sh → 9 checked, 0 unchecked, 0 gap(s).

## Verification gaps (flag before coding)

Phase 15 full governance/parity/RACES/frontend and Phase 16 clean restart are measured after the focused suite is green; they are not blocking items 1–6.

## Drift log

- START_SHA: `881232d1`
- CURRENT_REASONING_OWNER: `plan_delta_reasoner` owns READ#1 (same JSON as the next-read proposal). `evidence_reasoner` now owns standalone re-assessment when PlanDelta does not run (finalize after READ#2).
- WHY_REVISION_WAS_PREVIOUSLY_LOST: PlanDelta prompt had admitted SourceEvidence but no hypotheses; `_classify_hypotheses` only substring-copied plan text into supported when a finding contained it; no state channel between READ #1 and READ #2.
- Phase 15 full governance/parity/RACES/known-5/SPL-10/unseen-10 and Phase 16 clean restart were **not** run in this loop (focused suite + frontend unit tests only).
- Do not expand public InvestigationOutcome with a `weakened` enum.
- Do not retune `REVISION_QUERY` / `LIFECYCLE_QUERY`.
