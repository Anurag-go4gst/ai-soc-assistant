"""Plan 8 AUTH0 — Splunk/MCP authorization bound to the exact governed call.

Not an authorization service. Extends the existing MCP/HIL confirmation payload
so a material change to normalized SPL, tool, server, time, source, identity,
operators, limits, timeout, or a consumed/expired grant invalidates the pending
approval. LLM output cannot mint a grant.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.config import settings
from app.connectors.mcp.mcp_endpoint import normalize_mcp_endpoint_url

SCHEMA_VERSION = "splunk_call_grant_v1"
GRANT_TTL_SECONDS = 900


def build_splunk_call_grant(
    *,
    trace_id: str,
    identity: str | None = None,
    selected_mcp_server: str | None = None,
    selected_mcp_tool: str | None = None,
    normalized_spl: str | None = None,
    earliest: str | None = None,
    latest: str | None = None,
    indexes: list[str] | tuple[str, ...] | None = None,
    operators: list[str] | tuple[str, ...] | None = None,
    max_result_limit: int | None = None,
    timeout_ms: int | None = None,
    execution_intent: str | None = None,
    read_write_mode: str | None = None,
    hil_required: bool = True,
    rbac_role: str | None = None,
    mcp_endpoint: str | None = None,
    now: float | None = None,
    ttl_seconds: int = GRANT_TTL_SECONDS,
    tool_arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spl = str(normalized_spl or "")
    # Canonical execution material for non-SPL calls (saved search, read-only
    # metadata): sorted-key JSON of the exact bound arguments, hashed the same
    # way normalized_spl is. Absent for spl_search (empty string, stable
    # component — preserves every existing fingerprint (in)equality).
    canonical_args = json.dumps(tool_arguments, sort_keys=True, default=str) if tool_arguments else ""
    canonical_arguments_hash = hashlib.sha256(canonical_args.encode("utf-8")).hexdigest() if canonical_args else ""
    issued = float(now if now is not None else time.time())
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "trace_id": str(trace_id or ""),
        "identity": str(identity or rbac_role or ""),
        "selected_mcp_server": str(selected_mcp_server or ""),
        "selected_mcp_tool": str(selected_mcp_tool or ""),
        "normalized_spl": spl,
        "normalized_spl_sha256": hashlib.sha256(spl.encode("utf-8")).hexdigest() if spl else "",
        "canonical_arguments_hash": canonical_arguments_hash,
        "earliest": str(earliest or _extract_token(spl, "earliest")),
        "latest": str(latest or _extract_token(spl, "latest")),
        "indexes": list(indexes) if indexes is not None else _extract_indexes(spl),
        "operators": list(operators) if operators is not None else _extract_operators(spl),
        "max_result_limit": max_result_limit,
        "timeout_ms": timeout_ms if timeout_ms is not None else int(settings.mcp_search_job_timeout_ms),
        "execution_intent": str(execution_intent or "spl_search"),
        "read_write_mode": str(read_write_mode or "read"),
        "hil_required": bool(hil_required),
        "rbac_role": str(rbac_role or ""),
        "mcp_endpoint": str(
            mcp_endpoint
            if mcp_endpoint is not None
            else normalize_mcp_endpoint_url(settings.splunk_mcp_base_url)
        ),
        "one_run": True,
        "issued_at": issued,
        "expires_at": issued + int(ttl_seconds),
        "llm_granted": False,
    }
    canonical = "|".join(
        [
            payload["trace_id"],
            payload["identity"],
            payload["selected_mcp_server"],
            payload["selected_mcp_tool"],
            payload["normalized_spl_sha256"],
            payload["canonical_arguments_hash"],
            payload["earliest"],
            payload["latest"],
            ",".join(str(item) for item in payload["indexes"]),
            ",".join(str(item) for item in payload["operators"]),
            str(payload["max_result_limit"] or ""),
            str(payload["timeout_ms"] or ""),
            payload["execution_intent"],
            payload["read_write_mode"],
            "1" if payload["hil_required"] else "0",
            payload["rbac_role"],
            payload["mcp_endpoint"],
        ]
    )
    payload["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def call_grant_from_validation(
    *,
    trace_id: str,
    selection: dict[str, Any],
    spl_validation: dict[str, Any],
    rbac_role: str | None = None,
    identity: str | None = None,
    hil_required: bool = True,
    execution_intent: str = "spl_search",
    now: float | None = None,
) -> dict[str, Any]:
    spl = str(spl_validation.get("normalized_spl") or "")
    return build_splunk_call_grant(
        trace_id=trace_id,
        identity=identity,
        selected_mcp_server=str(selection.get("selected_mcp_server") or ""),
        selected_mcp_tool=str(selection.get("selected_mcp_tool") or ""),
        normalized_spl=spl,
        max_result_limit=int(settings.spl_max_result_limit),
        execution_intent=execution_intent,
        read_write_mode="read" if execution_intent in {"spl_search", "saved_search_execution"} else "write",
        hil_required=hil_required,
        rbac_role=rbac_role,
        mcp_endpoint=normalize_mcp_endpoint_url(settings.splunk_mcp_base_url),
        now=now,
    )


def call_grant_from_tool_call(
    *,
    trace_id: str,
    selection: dict[str, Any],
    tool_arguments: dict[str, Any],
    rbac_role: str | None = None,
    identity: str | None = None,
    hil_required: bool = True,
    execution_intent: str,
    read_write_mode: str = "read",
    now: float | None = None,
) -> dict[str, Any]:
    """Exact-call AUTH0 grant for non-SPL MCP tool calls (saved search,
    read-only metadata/identity tools).

    Same authorization type and invalidation semantics as
    `call_grant_from_validation` — binds tool/server/identity/trace like the
    SPL path, but the exact-call material is a canonicalized-argument hash
    instead of normalized_spl (there is no SPL for these tools). A mutation
    to tool, server, identity, or any bound argument invalidates the grant
    via the same `grants_match` fingerprint comparison used for
    `splunk_run_query`.
    """
    return build_splunk_call_grant(
        trace_id=trace_id,
        identity=identity,
        selected_mcp_server=str(selection.get("selected_mcp_server") or ""),
        selected_mcp_tool=str(selection.get("selected_mcp_tool") or ""),
        tool_arguments=tool_arguments,
        max_result_limit=int(settings.spl_max_result_limit),
        execution_intent=execution_intent,
        read_write_mode=read_write_mode,
        hil_required=hil_required,
        rbac_role=rbac_role,
        mcp_endpoint=normalize_mcp_endpoint_url(settings.splunk_mcp_base_url),
        now=now,
    )


def grants_match(pending: dict[str, Any] | None, current: dict[str, Any], *, now: float | None = None) -> bool:
    if not isinstance(pending, dict):
        return True
    if pending.get("consumed") is True:
        return False
    prior = pending.get("call_grant") if isinstance(pending.get("call_grant"), dict) else pending
    if prior.get("consumed") is True or prior.get("llm_granted") is True:
        return False
    expires_at = prior.get("expires_at")
    if expires_at is not None:
        clock = float(now if now is not None else time.time())
        try:
            if clock > float(expires_at):
                return False
        except (TypeError, ValueError):
            return False
    prior_fp = str(prior.get("fingerprint") or "")
    if not prior_fp:
        prior_spl = str(pending.get("normalized_spl") or prior.get("normalized_spl") or "")
        current_spl = str(current.get("normalized_spl") or "")
        if prior_spl and current_spl:
            return prior_spl == current_spl
        return True
    return prior_fp == str(current.get("fingerprint") or "")


def _extract_token(spl: str, name: str) -> str:
    marker = f"{name}="
    lowered = spl.lower()
    start = lowered.find(marker)
    if start < 0:
        return ""
    rest = spl[start + len(marker) :]
    return rest.split()[0].split("|")[0].strip()


def _extract_indexes(spl: str) -> list[str]:
    found: list[str] = []
    lowered = spl.lower()
    cursor = 0
    while True:
        start = lowered.find("index=", cursor)
        if start < 0:
            break
        rest = spl[start + 6 :]
        token = rest.split()[0].split("|")[0].strip()
        if token and token not in found:
            found.append(token)
        cursor = start + 6
    return found


def _extract_operators(spl: str) -> list[str]:
    operators: list[str] = []
    for part in spl.split("|"):
        token = part.strip().split()[0].lower() if part.strip() else ""
        if token and token not in operators:
            operators.append(token)
    return operators
