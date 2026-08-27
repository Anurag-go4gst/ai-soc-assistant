# 5.5 — mock MCP only after ApprovedInvestigationEnvelope

**STATUS: APPLIED UNDER THE USER'S REQUEST TO EXECUTE THE EXISTING CANONICAL PLAN.**

## CURRENT CONTRACT

Material MCP could be requested whenever `mcp_allowed` and flags permitted. Investigation
HIL (Approve → run → envelope) did not hard-block the gate when the require flag was set.

## PROPOSED CONTRACT

`evaluate_mcp_execution(..., require_approved_investigation_envelope=True)` fails closed
with `investigation_envelope_required` when no valid `envelope_version` is present — before
connector call. Pipeline investigation path passes the approved envelope and sets require
when `investigation_approval` or `approved_investigation_envelope` is present. Successful
mock executions stamp `mode=mock`, `execution=simulated`, and `envelope_version`.

## EXACT PROTECTED FILES

- `backend/app/orchestration/mcp_execution_gate.py`
- `backend/app/chat/pipeline.py`

RACES content pins advanced in the same commit.

## WHY J7 / LIVE MCP REMAIN TRUE

Hard-block only; does not enable live Splunk or write authority.

## POSITIVE / NEGATIVE

Positive: envelope v3 pending confirmation carries grant.envelope_version=3.
Negative: require=True without envelope → no connector call.
