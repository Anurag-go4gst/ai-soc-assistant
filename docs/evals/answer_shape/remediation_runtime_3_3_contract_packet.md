# 3.3 — B4 dual-eligibility contract packet

## CURRENT CONTRACT

`remediation_offer_cta_eligible()` combines two concepts: evidence-backed remediation-plan eligibility and whether the UI should ask “Create a remediation plan?”. Final-RQC conditional actions remain PENDING forever; no existing deterministic predicate evaluator advances them. A pre-requested remediation sets `remediation_offer_required=false`, which correctly suppresses the redundant ask but also leaves no plan surface.

## PROPOSED CONTRACT

Within the existing Phase 10 `remediation_runtime.py` seam:

1. split `remediation_plan_eligible()` (completed + suspicious + investigation-shaped + policy/J7) from `remediation_offer_cta_eligible()` (plan eligible + `remediation_offer_required`);
2. normalize predicate-bearing REQUESTED actions to PENDING_CONDITION;
3. advance PENDING_CONDITION to ELIGIBLE only through a closed deterministic predicate evaluator;
4. for `account_compromise_confirmed`, require all of: completed+suspicious outcome, non-empty outcome evidence refs, exact `account_compromise_confirmed` in accepted EvidenceState, a matching obtained EvidenceState item with `scope.predicate_id`, strict boolean `scope.predicate_value=true`, evidence refs intersecting the outcome, and FinalEvidenceGate collected-environment claim permission;
5. when remediation was already requested and plan eligibility holds, build the existing validated remediation plan directly and present Approve/Edit/Cancel — never re-ask “Create plan?”.

No action is approved or executed by this change. Email draft/send remain separate later items.

## WHY J7 REMAINS TRUE

`remediation_plan_eligible()` retains the exact 3.1 gates and adds an explicit non-empty outcome evidence-ref check: feature enabled, InvestigationOutcome V2 applicability, completed status, suspicious disposition, evidence refs, and non-knowledge Final RQC. Incomplete/inconclusive/SOP remain negative. The user predicate is not required merely to present a remediation plan and cannot substitute for J7.

## POSITIVE TEST

CV.MULTI.01B-shaped completed+suspicious outcome plus exact accepted `account_compromise_confirmed` EvidenceState and collected-environment FinalEvidenceGate advances remediation/email actions to ELIGIBLE. The pre-requested remediation directly presents an awaiting-approval validated plan with no approved envelope or execution.

## NEGATIVE TEST

Suspicious alone, an obtained-key list without a matching true evidence-bound assertion, an exact item without FinalEvidenceGate permission, or mock/simulated evidence leaves both actions PENDING_CONDITION. CV.MULTI.01A remains plan-absent. No compromise-confirmed prose claim is synthesized.

## ROLLBACK

Revert the predicate resolver, `remediation_plan_eligible()` split, and direct pre-requested-plan branch. Restore `remediation_offer_cta_eligible()` as the sole offer gate. No schema, flag, registry, planner, or connector migration is involved.
