# Phase 1.1 — Final RQC multi-goal / conditional language audit

**Date:** 2026-08-26  
**Worktree:** `ws/post-p10-answer-tool-convergence`  
**Query:** primary SSH/admin design-case (eval bank only)

## Files audited

| File | Lines |
|---|---|
| `backend/app/chat/contracts/resolved_query.py` | 105 |
| `backend/app/chat/resolved_query_builder.py` | 426 |

## What Final RQC structurally carries today

From `ResolvedQueryContract` (`resolved_query.py:44-76`):

| Field | Present | Notes |
|---|---|---|
| `normalized_goal` | YES | single string goal |
| `intent_family` | YES | |
| `answer_goal` | YES | closed `AnswerGoal` literal — **no** remediation/email_draft goal |
| `evidence_requirements` | YES | list[str] |
| `entities` | YES | dict — no typed recipient_roles |
| `provenance` | YES | **must not** be used to smuggle requested actions |
| `requested_actions` / `requested_conditional_actions` | **NO** | absent |
| `communication_intent` / `email_draft` | **NO** | absent |
| `recipient_roles` | **NO** | absent |
| governed `predicate_id` / predicate mechanism | **NO** | **ABSENT** on RQC |
| lifecycle states REQUESTED→…→EXECUTED | **NO** | absent |

`build_resolved_query_contract` entry: `resolved_query.py:99` / builder module — no extraction of conditional remediation/email/roles/predicates (grep: zero matches for those terms in both files).

## Present vs lost (design-case)

| Intent | Survives into Final RQC today? |
|---|---|
| Investigate SSH/admin compromise | Partially via `normalized_goal` / intent_family only |
| Conditional remediation | **LOST** (no structural field) |
| Conditional email_draft | **LOST** |
| recipient_roles (`firewall_team`, `identity_team`) | **LOST** |
| Governed compromise predicate | **LOST** — mechanism **ABSENT** |

## Structural gap confirmation

**Final RQC is the structural gap** for requested conditional actions / recipient roles / requested outputs / governed predicates. Do not smuggle into provenance, `workflow_plan`, or unrelated metadata. Do not jump first to `schemas/responses.py`.

## Predicate mechanism

**ABSENT** on Final RQC. Minimum extension required in later 1.4 (governed `predicate_id` on requested conditional actions), not a second condition engine.

## 1.2 — ResourcePlan read-only investigation attestation

Audited `backend/app/planner/resource_plan.py` (`PlanStep` / `ResourcePlan`) and planner/graph references.

- No `email_draft` / `email_send` / `recipient_roles` / governed conditional-action fields on ResourcePlan step contracts.
- Planner "conditional" language refers to **graph/scheduler edges**, not user-conditional remediation/email actions.
- SPL specialist hard-validates `execution_eligible=False`.

**Attestation:** ResourcePlan **must remain read-only investigation only**. Remediation/email/recipient_roles/predicates belong on Final RQC → Phase 10 after InvestigationOutcome. Any current placement of those as ResourcePlan steps would be a defect to remove (none found as typed step kinds in this audit).

### RQC-owned gap list (for 1.4+)

1. `requested_conditional_actions[]` with action kind + lifecycle state
2. governed `predicate_id` per action
3. `recipient_roles[]` (role identifiers only)
4. `requested_outputs[]` if not implied by actions
