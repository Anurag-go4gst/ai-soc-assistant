# 1.4 — Final RQC contract packet (requested conditional actions)

## CURRENT CONTRACT (pre-change)

`ResolvedQueryContract` (`resolved_query.py`, contract_version `2026-08-12`) carried understanding fields only — **no** `requested_conditional_actions`, `recipient_roles`, governed `predicate_id`, or lifecycle states.

## PROPOSED CONTRACT (shipped in 1.4)

- `CONTRACT_VERSION = 2026-08-26`
- `RequestedConditionalAction` with `action_kind` ∈ {`remediation`,`email_draft`}, `lifecycle_state` ∈ REQUESTED→EXECUTED, optional `predicate_id`, `recipient_roles[]`
- `ResolvedQueryContract.requested_conditional_actions: list[RequestedConditionalAction]`
- `ResolvedQueryContract.requested_outputs: list[str]`
- Builder `_extract_requested_conditional_actions` — deterministic preservation only; **no** eligibility/write/send authority; **not** ResourcePlan steps
- Wire exposure via `schemas/responses.py`: **not required for 1.4** (RQC owns fields first)

## WHY J7 / authority unchanged

Extraction only records REQUESTED/PENDING_CONDITION intent. No remediation CTA, no email send, no MCP grant.
