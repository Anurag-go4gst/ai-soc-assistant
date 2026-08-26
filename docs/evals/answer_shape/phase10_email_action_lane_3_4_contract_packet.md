# 3.4 — Phase 10 email action-lane contract packet

## CURRENT CONTRACT

The deterministic conditional-action resolver is called by the Phase 10 remediation seam after `InvestigationOutcome`, but the pipeline returns before that seam whenever the optional remediation planner flag is disabled. This incorrectly couples email-draft predicate resolution to remediation-plan availability. ResourcePlan composition itself emits read-only investigation/evidence resources and has no email action step.

## PROPOSED CONTRACT

Always enter the existing Phase 10 lifecycle seam after `InvestigationOutcome` so Final-RQC conditional actions can be normalized and evaluated deterministically. Keep explicit remediation review behind `AI_SOC_REMEDIATION_PLANNER_ENABLED`. An eligible `email_draft` remains an `email_draft` action on Final RQC; it does not become `email_send`, an action proposal, a remediation execution, or a ResourcePlan step. Draft prose, recipient resolution, and send authorization remain later items 3.5–3.7.

## WHY J7 REMAINS TRUE

The change does not relax remediation-plan eligibility. With the remediation planner disabled, `remediation_plan_eligible()` remains false and no remediation approval surface is attached. The only newly independent behavior is deterministic resolution of an already-preserved Final-RQC conditional action.

## POSITIVE TEST

A CV.MULTI.01B-shaped completed, suspicious, evidence-backed outcome with the exact accepted `account_compromise_confirmed` assertion advances the requested `email_draft` to `ELIGIBLE` through the Phase 10 seam even when remediation planning is disabled. No email send, approval envelope, or execution is produced.

## NEGATIVE TEST

The same request without the exact predicate evidence remains `PENDING_CONDITION`. A composed hybrid ResourcePlan contains no `email_draft`, `email_send`, or `action:*` resource step.

## ROLLBACK

Restore the early remediation-feature return in `_apply_remediation_lifecycle()` and remove the 3.4 regression tests. No schema, registry, connector, provider, or deployment migration is involved.
