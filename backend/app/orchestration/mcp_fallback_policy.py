"""Deterministic MCP fallback policy -- fallback by CAPABILITY, never "try
another tool" or LLM tool-hopping.

A same-capability alternative is only ever considered when local policy has
already, explicitly established semantic equivalence
(`CAPABILITY_FALLBACK_CANDIDATES`) -- currently empty for every capability,
which is the correct and intentional state: no local policy has established
that `splunk_run_saved_search` is an equivalent substitute for
`splunk_run_query` (or any other pairing), so no fallback occurs today. This
module exists so that IF such an equivalence is ever deliberately
established, the wiring already enforces every required boundary (§16-18):
same capability only, verified-executable-in-the-effective-catalog only,
never for auth/rbac/hil/policy/schema failures, never reusing the failed
call's AUTH0 grant, and never treating zero results as a failure at all.
"""

from __future__ import annotations

from typing import Any

from app.connectors.mcp.effective_catalog import EffectiveCatalogResult
from app.connectors.mcp.mcp_failure_taxonomy import is_fallback_eligible

# Deliberately empty. A capability may only appear here after an explicit,
# reviewed local-policy decision that a specific alternative tool is a safe,
# semantically-equivalent substitute -- see module docstring. Do not add
# entries speculatively.
CAPABILITY_FALLBACK_CANDIDATES: dict[str, tuple[str, ...]] = {}


def resolve_fallback_tool(
    *,
    capability: str,
    failed_tool_name: str,
    failure_kind: str,
    effective_catalog: EffectiveCatalogResult | None,
) -> tuple[str | None, str]:
    """Returns (fallback_tool_name_or_None, reason). Never mutates or
    reuses the failed call's AUTH0 grant -- callers must build a brand new
    grant for whatever tool this returns, exactly as they would for any
    fresh selection."""
    if not is_fallback_eligible(failure_kind):
        return None, "fallback_not_eligible_for_failure_kind"
    candidates = CAPABILITY_FALLBACK_CANDIDATES.get(capability, ())
    if not candidates:
        return None, "no_established_fallback_equivalence"
    if effective_catalog is None:
        return None, "no_effective_catalog_to_verify_fallback"
    for candidate in candidates:
        if candidate == failed_tool_name:
            continue
        if effective_catalog.is_executable(candidate):
            return candidate, "fallback_candidate_selected"
    return None, "no_verified_fallback_candidate"


def zero_results_is_not_a_failure(result: dict[str, Any]) -> bool:
    """Documents and enforces the invariant at the one place a caller might
    be tempted to special-case it: a successful call with `row_count == 0`
    (or an empty `rows` list) is a legitimate evidence outcome, not a
    trigger for fallback. Returns True (i.e. "this is fine, not a failure")
    whenever `status` indicates success, regardless of row count."""
    status = str(result.get("status") or "").strip().lower()
    return status in {"ok", "completed", "success", "executed"}
