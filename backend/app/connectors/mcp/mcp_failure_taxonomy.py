"""Canonical MCP failure kinds. Deterministic classification only -- never
free-form LLM judgment decides what kind of failure occurred or whether it
is fallback-eligible."""

from __future__ import annotations

DISCOVERY_UNVERIFIED = "DISCOVERY_UNVERIFIED"
DISCOVERY_FAILED = "DISCOVERY_FAILED"
DISCOVERY_STALE = "DISCOVERY_STALE"
TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
AUTH_FAILURE = "AUTH_FAILURE"
TLS_FAILURE = "TLS_FAILURE"
RBAC_FAILURE = "RBAC_FAILURE"
HIL_REJECTED = "HIL_REJECTED"
POLICY_REJECTED = "POLICY_REJECTED"
AUTH0_INVALID = "AUTH0_INVALID"
AUTH0_EXPIRED = "AUTH0_EXPIRED"
AUTH0_CONSUMED = "AUTH0_CONSUMED"
MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
TRANSIENT_TRANSPORT_FAILURE = "TRANSIENT_TRANSPORT_FAILURE"
ZERO_RESULTS = "ZERO_RESULTS"
UNSAFE_TOOL = "UNSAFE_TOOL"

ALL_FAILURE_KINDS = frozenset(
    {
        DISCOVERY_UNVERIFIED,
        DISCOVERY_FAILED,
        DISCOVERY_STALE,
        TOOL_NOT_FOUND,
        TOOL_UNAVAILABLE,
        SCHEMA_MISMATCH,
        AUTH_FAILURE,
        TLS_FAILURE,
        RBAC_FAILURE,
        HIL_REJECTED,
        POLICY_REJECTED,
        AUTH0_INVALID,
        AUTH0_EXPIRED,
        AUTH0_CONSUMED,
        MALFORMED_RESPONSE,
        TRANSIENT_TRANSPORT_FAILURE,
        ZERO_RESULTS,
        UNSAFE_TOOL,
    }
)

# Only genuinely operational failures may ever be considered for a
# same-capability fallback. Authorization/policy/schema/safety failures and
# ZERO_RESULTS (a legitimate evidence outcome, not a failure) STOP --
# fail closed, never retried with a different tool.
FALLBACK_ELIGIBLE_FAILURE_KINDS = frozenset({TOOL_NOT_FOUND, TOOL_UNAVAILABLE, TRANSIENT_TRANSPORT_FAILURE})

NEVER_FALLBACK_FAILURE_KINDS = ALL_FAILURE_KINDS - FALLBACK_ELIGIBLE_FAILURE_KINDS


def is_fallback_eligible(failure_kind: str) -> bool:
    return failure_kind in FALLBACK_ELIGIBLE_FAILURE_KINDS
