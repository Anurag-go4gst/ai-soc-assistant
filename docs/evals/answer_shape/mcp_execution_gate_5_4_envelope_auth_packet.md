# 5.4 — envelope-bound mock MCP exact-call AUTH protected change packet

**STATUS: APPLIED UNDER THE USER'S REQUEST TO EXECUTE THE EXISTING CANONICAL PLAN.**

## CURRENT CONTRACT

Plan 8 AUTH0 `build_splunk_call_grant` / `call_grant_from_validation` / `call_grant_from_tool_call` bind tool, server, normalized SPL / canonical arguments, RBAC, and HIL into a fingerprint. Mock MCP material calls share that path but were not yet bound to `ApprovedInvestigationEnvelope.envelope_version`, so a stale or pre-approval grant could not be invalidated by envelope version alone.

## PROPOSED CONTRACT

Extend AUTH0 fingerprints with optional `envelope_version` (int ≥ 1 when present). `evaluate_mcp_execution` accepts additive `approved_investigation_envelope` and threads its version into every grant mint path (SPL search, saved search, read-only). Changing `envelope_version` invalidates the prior grant via existing `grants_match`. Missing/stale envelope grants fail closed. No new env flag names. Mock still does not become live evidence. Connector pre-Approve hard-block remains item 5.5.

## EXACT PROTECTED FILES

- `backend/app/orchestration/mcp_execution_gate.py`: accept `approved_investigation_envelope`, extract `envelope_version`, pass into AUTH0 grant builders on all material paths.

Non-freeze companion (same commit): `backend/app/orchestration/splunk_call_authorization.py` adds `envelope_version` to the fingerprint payload.

The RACES freeze baseline advances by exact SHA-256 content pin for `mcp_execution_gate.py`. No ChatPanel / pipeline / responses / SPL validator edits in this item.

## WHY J7 / LIVE MCP REMAIN TRUE

Envelope binding only invalidates mismatched grants; it does not enable live Splunk, write authority, remediation ELIGIBLE, or `live_mcp_proven`. Default COE stays `MCP_GLOBAL_EXECUTION_ENABLED=false`.

## POSITIVE TEST

Grant minted with `envelope_version=1` matches itself; gate pending confirmation under mock+envelope stores `call_grant.envelope_version=1`.

## NEGATIVE TEST

`envelope_version=1` vs `2` fingerprints differ; missing vs present differ; confirm with pending v1 grant under envelope v2 → exact-call invalidated, no execution.

## ROLLBACK

Remove `envelope_version` from grant fingerprint and gate parameter; restore prior protected-blob pin for `mcp_execution_gate.py`.
