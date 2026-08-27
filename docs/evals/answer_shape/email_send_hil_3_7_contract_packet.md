# 3.7 — separate HIL-authorized email send proof (governance note)

**STATUS: APPLIED UNDER THE USER'S REQUEST TO EXECUTE THE EXISTING CANONICAL PLAN.**

## CONTRACT

EMAIL DRAFT ≠ EMAIL SEND.

Lifecycle authority remains:

REQUESTED → PENDING_CONDITION → ELIGIBLE → APPROVED → EXECUTED

with ELIGIBLE → APPROVED requiring explicit send HIL. No Phase-10 connector/executor was
introduced. `email_send_eligible(state)` is fail-closed and returns False for:

1. Draft generated without HIL
2. PENDING_CONDITION
3. Predicate satisfied / ELIGIBLE without approval
4. Remediation plan Approve (even when the remediation package lists capability `email_send`)
5. Missing recipient resolution / role-only ids / unavailable connector
6. LLM-shaped draft payloads (no lifecycle transition; production builder stays deterministic)

## PROTECTED FILES

None. No `pipeline.py`, `schemas/responses.py`, ChatPanel, MCP gate, or RACES freeze
baseline mutation. Proof is `email_send_eligible` + negative tests + harness ABSENT pin.

## POSITIVE / NEGATIVE

Positive: ELIGIBLE draft may exist with `send_authorized=false` / `sent=false`.
Negative: `CV.MULTI.01A` send ABSENT; harness rejects send claims; unit suite in
`test_email_send_hil_3_7.py`.
