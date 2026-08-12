# A2.5 — MITRE DRAFT→runtime promotion decision

**Decision:** `DEFERRED_SEPARATE_GOVERNED_PROMOTION`  
**Date:** 2026-08-12  
**Plan:** `plans/2026-08-12_1230_production-readiness-understanding-phase-contract.md`

## Summary

The MITRE DRAFT (`docs/input/mitre_enrichment/question_105_for_mitre_enrichment.DRAFT.json`) remains the **authoring/curation source**. The committed runtime map (`backend/app/coverage/question_runtime_map_v1.json`) remains the **currently deployed governed state**. Plan 5 does **not** promote the 11-row delta.

The divergence is **known unpromoted governance drift**, not a builder-idempotency defect. A future promotion requires a separately scoped MITRE governance review of exact analyst-visible/runtime effects. Normal map regeneration must not silently consume the DRAFT delta — the drift ledger (`docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json`) and `test_question_runtime_map_draft_drift.py` enforce this.

## 11-row drift (unchanged)

| Question ref | DRAFT candidate | Runtime map candidate |
|--------------|-----------------|----------------------|
| q0.q021 | T1071 | [] |
| q0.q028 | T1071 | [] |
| q0.q040 | T1071 | [] |
| q0.q046 | T1110 | [] |
| q0.q047 | T1110 | [] |
| q0.q050 | T1059.001 | [] |
| q0.q060 | T1110 | [] |
| q0.q062 | T1110 | [] |
| q0.q063 | T1059.001 | [] |
| q0.q083 | T1059.001 | [] |
| q0.q089 | T1110 | [] |

**Provenance:** commit `7ee7a34` added candidate anchors to the DRAFT; `56b48d9` promoted an earlier DRAFT snapshot; promoter not re-run.

## Rationale for deferral

- Promoting would widen analyst-visible MITRE candidates on 11 of 105 questions.
- `scripts/promote_mitre_registry_to_runtime.py` also writes protected `backend/app/use_cases/catalog.json`.
- Builder A2 reproduces the promoted state byte-identically; containment tests pin suppression.
- Phase B architecture work does not require promoting these rows.

## Re-open trigger

A dedicated MITRE governance review scoped to promotion impact, with protected-manifest re-capture and analyst-visible outcome measurement.
