# 3.1 — remediation runtime contract packet

## CURRENT CONTRACT

`remediation_offer_cta_eligible()` currently requires all of:

1. `AI_SOC_REMEDIATION_PLANNER_ENABLED=true`;
2. an InvestigationOutcome V2-shaped payload (`investigation_status` present);
3. `remediation_offer_required=true`;
4. `investigation_status=completed`;
5. `disposition=suspicious`;
6. selected skill is not `knowledge_recall`;
7. `context_sufficiency.answer_mode` is not `knowledge_only_answer`.

Item 6 is the defect: route/skill identity vetoes a valid multi-goal investigation even when Final RQC and the evidence-bound outcome say the product lifecycle is an investigation. The skill is packaging metadata, not remediation business authority.

## PROPOSED CONTRACT

Keep items 1–5 and 7 unchanged. Replace the selected-skill veto with the existing shared `investigation_outcome_applicable()` contract check over Final RQC, intent classification, query understanding, evidence plan, and context sufficiency. Do not create a second investigation classifier or a second eligibility gate.

No conditional action lifecycle transition is added in 3.1. Final-RQC `requested_conditional_actions` remain unchanged; predicate-unmet email remains `PENDING_CONDITION`.

## WHY J7 REMAINS TRUE

- Incomplete, blocked, or inconclusive outcomes still fail before product applicability is considered.
- Evidence refs alone still do not grant remediation; deterministic `disposition=suspicious` is required.
- Pure SOP/knowledge Final RQCs fail the shared applicability contract, and `knowledge_only_answer` remains an explicit negative gate.
- A completed+suspicious outcome can reach the remediation lane only when Final RQC is investigation-shaped and `remediation_offer_required=true`.
- Neither the LLM nor selected skill can establish evidence truth, predicate truth, approval, or execution.

## POSITIVE TEST

Multi-goal state with investigation-shaped Final RQC, a legacy `knowledge_recall` route label, completed+suspicious evidence-backed outcome, and `remediation_offer_required=true` is eligible for the governed remediation offer. Its requested `email_draft` remains `PENDING_CONDITION`.

## NEGATIVE TEST

Pure SOP Final RQC with `policy_citation`, no live capabilities, and knowledge-only answer mode receives no remediation offer even if a malformed caller supplies a completed+suspicious-shaped outcome. Multi-goal insufficient/inconclusive evidence also receives no CTA while requested actions remain preserved.

## ROLLBACK

Revert the `investigation_outcome_applicable()` call and restore the former selected-skill veto plus its tests. No schema, flag, planner, predicate, or connector migration is involved.
