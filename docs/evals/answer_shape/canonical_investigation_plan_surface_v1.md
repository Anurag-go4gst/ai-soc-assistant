# 2.2 — Canonical investigation plan surface

**Decision:** Analyst-visible investigation plan = **`investigation_approval` / InvestigationPlanApprovalCard** path (Approve/Edit/Cancel → wire `run`/`edit`/`cancel` → `ApprovedInvestigationEnvelope`).

**`workflow_plan`:** remains inert planning/diagnostic metadata (`execution_enabled=false`, steps `not_started`). Keep collapsed/diagnostic — **not** a second analyst plan card for state A.

## Evidence (file:line)

| Surface | Location |
|---|---|
| Wire Approve→`run` | `frontend/src/components/InvestigationPlanApprovalCard.tsx` (~104) |
| UI vocabulary test | `frontend/src/components/InvestigationPlanApprovalCard.test.tsx` — Approve/Edit/Cancel, never Run |
| Envelope contract | `backend/app/chat/contracts/investigation_envelope.py` + `test_p4_investigation_envelope.py` |
| Dual-card prohibition | State A fixtures must not render both workflow_plan card and investigation approval as peer plan authorities |

## Dual plan cards in state A

**Target:** one canonical plan. Existing P4/P7 tests already pin Approve/Edit/Cancel vocabulary. No change required in 2.2 beyond this written decision.
