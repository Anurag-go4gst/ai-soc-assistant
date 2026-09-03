"""Canonical LLM interaction records for debug traces.

One record per actual model invocation. Compact summaries belong on the
reviewer export; exact redacted request/response bodies belong on forensic
``llm_call`` events. This module does not call a model and does not change
turn-budget hop counts.
"""

from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from threading import Lock, local
from typing import Any
from uuid import uuid4

from app.connectors.telemetry.log_context import current_trace_id
from app.connectors.telemetry.redaction import (
    redact_secrets_keep_text,
    secret_substrings_were_masked,
)

SCHEMA_VERSION = "llm_interaction_v1"

SYNTHESIS_ROLES = frozenset(
    {
        "review_only_spl_synthesis",
        "governed_composer",
        "analyst_summary_llm_assist",
    }
)
SPL_ADVISORY_ROLES = frozenset(
    {
        "spl_advisory_generator",
        "spl_plan_compiler",
        "spl_t2_producer",
        "spl_advisory",
    }
)
SPL_REPAIR_ROLES = frozenset({"spl_repair", "utility_llm_spl_repair"})

_collector: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "ai_soc_llm_interactions",
    default=None,
)
# Sidecar hops run in a thread-pool with copy_context(). ContextVar writes in
# that copy do not propagate back to the /chat worker, so forensic records also
# stash by the request trace_id (which *is* copied into the worker).
_TRACE_BUCKETS: dict[str, list[dict[str, Any]]] = {}
_INFLIGHT_TRACES: set[str] = set()
_TRACE_BUCKET_LOCK = Lock()
_THREAD_TRACE = local()


def _active_trace_id(trace_id: str | None = None) -> str | None:
    for candidate in (trace_id, current_trace_id(), getattr(_THREAD_TRACE, "trace_id", None)):
        tid = str(candidate or "").strip()
        if tid and tid != "-":
            return tid
    return None


def _resolve_stash_trace_id() -> str | None:
    tid = _active_trace_id()
    if tid is not None:
        return tid
    with _TRACE_BUCKET_LOCK:
        if len(_INFLIGHT_TRACES) == 1:
            return next(iter(_INFLIGHT_TRACES))
    return None


def bind_llm_interaction_turn(trace_id: str | None) -> None:
    """Register the live /chat turn so worker-thread captures can stash."""
    tid = _active_trace_id(trace_id)
    if tid is None:
        return
    _THREAD_TRACE.trace_id = tid
    with _TRACE_BUCKET_LOCK:
        _INFLIGHT_TRACES.add(tid)
        _TRACE_BUCKETS.setdefault(tid, [])


def _stash_for_trace(record: dict[str, Any]) -> None:
    tid = _resolve_stash_trace_id()
    if tid is None:
        return
    with _TRACE_BUCKET_LOCK:
        _TRACE_BUCKETS.setdefault(tid, []).append(record)


def reset_llm_interactions(*, trace_id: str | None = None) -> None:
    _collector.set(None)
    with _TRACE_BUCKET_LOCK:
        if trace_id is None:
            _TRACE_BUCKETS.clear()
            _INFLIGHT_TRACES.clear()
            return
        tid = _active_trace_id(trace_id)
        if tid is not None:
            _TRACE_BUCKETS.pop(tid, None)
            _INFLIGHT_TRACES.discard(tid)


def snapshot_llm_interactions(*, trace_id: str | None = None) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def _add(item: dict[str, Any]) -> None:
        key = str(item.get("interaction_id") or f"anon-{len(order)}")
        if key not in merged:
            order.append(key)
        merged[key] = item

    for item in list(_collector.get() or []):
        if isinstance(item, dict):
            _add(item)
    tid = _active_trace_id(trace_id)
    if tid is not None:
        with _TRACE_BUCKET_LOCK:
            stored = list(_TRACE_BUCKETS.get(tid) or [])
        for item in stored:
            if isinstance(item, dict):
                _add(item)
    return [merged[key] for key in order]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def build_llm_interaction_record(
    *,
    role: str,
    stage: str | None = None,
    provider_label: str | None = None,
    model: str | None = None,
    endpoint_label: str | None = None,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    response_schema: Any = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tool_choice: Any = None,
    raw_text: str | None = None,
    parsed_payload: Any = None,
    finish_reason: str | None = None,
    usage: dict[str, Any] | None = None,
    transport_status: str | None = None,
    parse_status: str | None = None,
    schema_status: str | None = None,
    quality_status: str | None = None,
    fidelity_status: str | None = None,
    grounding_status: str | None = None,
    reject_reasons: list[str] | None = None,
    accepted: bool = False,
    contributed_to_final_output: bool = False,
    fallback_selected: bool | None = None,
    fallback_reason: str | None = None,
    latency_ms: int | None = None,
    interaction_id: str | None = None,
) -> dict[str, Any]:
    """Build one canonical interaction after secret redaction, then hash."""
    raw_system = system_prompt if isinstance(system_prompt, str) else None
    raw_user = user_prompt if isinstance(user_prompt, str) else None
    raw_response = raw_text if isinstance(raw_text, str) else None
    redacted_system = redact_secrets_keep_text(raw_system) if raw_system is not None else None
    redacted_user = redact_secrets_keep_text(raw_user) if raw_user is not None else None
    redacted_messages = redact_secrets_keep_text(messages) if messages is not None else None
    redacted_response = redact_secrets_keep_text(raw_response) if raw_response is not None else None
    redacted_parsed = redact_secrets_keep_text(parsed_payload) if parsed_payload is not None else None
    prompt_material = {
        "system_prompt": redacted_system,
        "user_prompt": redacted_user,
        "messages": redacted_messages,
        "response_schema": response_schema,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tool_choice": tool_choice,
    }
    prompt_hash = _hash_text(_stable_json(prompt_material))
    response_hash = _hash_text(redacted_response or "")
    reasons = [str(item) for item in (reject_reasons or []) if str(item).strip()]
    record = {
        "schema_version": SCHEMA_VERSION,
        "interaction_id": interaction_id or uuid4().hex,
        "role": str(role),
        "stage": stage or _stage_for_role(role),
        "provider_label": provider_label,
        "model": model,
        "endpoint_label": endpoint_label,
        "request": {
            "system_prompt": redacted_system,
            "user_prompt": redacted_user,
            "messages": redacted_messages,
            "response_schema": response_schema,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tool_choice": tool_choice,
            "prompt_hash": prompt_hash,
        },
        "response": {
            "raw_text": redacted_response,
            "parsed_payload": redacted_parsed,
            "finish_reason": finish_reason,
            "usage": dict(usage) if isinstance(usage, dict) else {},
            "response_hash": response_hash,
        },
        "validation": {
            "transport_status": transport_status,
            "parse_status": parse_status,
            "schema_status": schema_status,
            "quality_status": quality_status,
            "fidelity_status": fidelity_status,
            "grounding_status": grounding_status,
            "reject_reasons": reasons,
        },
        "disposition": {
            "accepted": bool(accepted),
            "contributed_to_final_output": bool(contributed_to_final_output),
            "fallback_selected": fallback_selected,
            "fallback_reason": fallback_reason,
        },
        "latency_ms": latency_ms,
        "prompt_redaction_applied": secret_substrings_were_masked(raw_system, redacted_system)
        or secret_substrings_were_masked(raw_user, redacted_user),
        "response_redaction_applied": secret_substrings_were_masked(raw_response, redacted_response),
        "prompt_hash": prompt_hash,
        "response_hash": response_hash,
    }
    return redact_secrets_keep_text(record)


def capture_llm_interaction(**kwargs: Any) -> dict[str, Any]:
    """Append a canonical record to the request-scoped collector."""
    record = build_llm_interaction_record(**kwargs)
    bucket = _collector.get()
    if bucket is None:
        bucket = []
        _collector.set(bucket)
    bucket.append(record)
    _stash_for_trace(record)
    return record


def annotate_last_llm_interaction(role: str, **updates: Any) -> dict[str, Any] | None:
    """Attach later validation/disposition to the last captured call of ``role``.

    The model invocation already happened; this only records downstream quality
    or fidelity outcomes on that same canonical record.
    """
    bucket = list(_collector.get() or [])
    tid = _resolve_stash_trace_id()
    if tid is not None:
        with _TRACE_BUCKET_LOCK:
            stored = list(_TRACE_BUCKETS.get(tid) or [])
        seen = {id(item) for item in bucket}
        for item in stored:
            if id(item) not in seen:
                bucket.append(item)
    for item in reversed(bucket):
        if str(item.get("role") or "") != role:
            continue
        validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
        item["validation"] = validation
        for key in (
            "transport_status",
            "parse_status",
            "schema_status",
            "quality_status",
            "fidelity_status",
            "grounding_status",
        ):
            if key in updates and updates[key] is not None:
                validation[key] = updates[key]
        if updates.get("reject_reasons") is not None:
            validation["reject_reasons"] = [str(item_reason) for item_reason in updates["reject_reasons"] if str(item_reason).strip()]
        disposition = item.get("disposition") if isinstance(item.get("disposition"), dict) else {}
        item["disposition"] = disposition
        for key in ("accepted", "contributed_to_final_output", "fallback_selected", "fallback_reason"):
            if key in updates and updates[key] is not None:
                disposition[key] = updates[key]
        return item
    return None


def hydrate_llm_interaction(record: dict[str, Any]) -> dict[str, Any]:
    """Lift nested ``forensic.request/response`` onto the canonical record."""
    source = dict(record) if isinstance(record, dict) else {}
    forensic = source.get("forensic") if isinstance(source.get("forensic"), dict) else {}
    if forensic.get("request") and not source.get("request"):
        source["request"] = forensic.get("request")
    if forensic.get("response") and not source.get("response"):
        source["response"] = forensic.get("response")
    if forensic.get("validation") and not source.get("validation"):
        source["validation"] = forensic.get("validation")
    if forensic.get("disposition") and not source.get("disposition"):
        source["disposition"] = forensic.get("disposition")
    for key in ("prompt_hash", "response_hash", "prompt_redaction_applied", "response_redaction_applied"):
        if source.get(key) is None and forensic.get(key) is not None:
            source[key] = forensic.get(key)
    return source


def compact_llm_interaction(record: dict[str, Any]) -> dict[str, Any]:
    """Reviewer-safe summary: no prompt/response bodies."""
    source = hydrate_llm_interaction(_as_dict(record))
    validation = _as_dict(source.get("validation"))
    disposition = _as_dict(source.get("disposition"))
    reasons = validation.get("reject_reasons") if isinstance(validation.get("reject_reasons"), list) else []
    interaction_id = str(source.get("interaction_id") or "")
    return {
        "interaction_id": interaction_id,
        "role": source.get("role"),
        "stage": source.get("stage"),
        "provider_label": source.get("provider_label"),
        "model": source.get("model"),
        "status": _status_from_record(source),
        "latency_ms": source.get("latency_ms"),
        "accepted": bool(disposition.get("accepted")),
        "contributed_to_final_output": bool(disposition.get("contributed_to_final_output")),
        "reject_reason": reasons[0] if reasons else disposition.get("fallback_reason"),
        "reject_reasons": reasons,
        "fallback_selected": disposition.get("fallback_selected"),
        "fallback_reason": disposition.get("fallback_reason"),
        "prompt_hash": source.get("prompt_hash"),
        "response_hash": source.get("response_hash"),
        "forensic_ref": f"timeline:llm_call:{interaction_id}" if interaction_id else None,
    }


def compact_llm_call_index(records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [compact_llm_interaction(item) for item in records or [] if isinstance(item, dict)]


def forensic_llm_call_event(record: dict[str, Any]) -> dict[str, Any]:
    """Fields for ``telemetry.record_llm_call`` — secrets already redacted."""
    source = _as_dict(record)
    compact = compact_llm_interaction(source)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "llm_interaction",
        "interaction_id": source.get("interaction_id"),
        "role": source.get("role"),
        "stage": source.get("stage"),
        "provider_label": source.get("provider_label"),
        "model": source.get("model"),
        "outcome": compact.get("status"),
        "latency_ms": source.get("latency_ms"),
        "prompt_hash": source.get("prompt_hash"),
        "response_hash": source.get("response_hash"),
        "accepted": compact.get("accepted"),
        "contributed_to_final_output": compact.get("contributed_to_final_output"),
        "reject_reason": compact.get("reject_reason"),
        "forensic": {
            "request": source.get("request"),
            "response": source.get("response"),
            "validation": source.get("validation"),
            "disposition": source.get("disposition"),
            "prompt_redaction_applied": source.get("prompt_redaction_applied"),
            "response_redaction_applied": source.get("response_redaction_applied"),
        },
    }


def merge_llm_call_summaries(
    budget_records: list[dict[str, Any]] | None,
    interactions: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Union budget rows with canonical interactions; interactions win on role+id."""
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in compact_llm_call_index(interactions):
        key = (str(item.get("role") or ""), str(item.get("interaction_id") or item.get("prompt_hash") or ""))
        seen.add(key)
        merged.append(item)
    for raw in budget_records or []:
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "")
        key = (role, str(raw.get("interaction_id") or raw.get("prompt_hash") or ""))
        if key in seen and key[1]:
            continue
        if any(str(existing.get("role") or "") == role and existing.get("latency_ms") == raw.get("latency_ms") for existing in merged):
            continue
        merged.append(
            {
                "interaction_id": raw.get("interaction_id"),
                "role": role or None,
                "stage": raw.get("stage") or _stage_for_role(role),
                "provider_label": raw.get("provider_label"),
                "model": raw.get("model"),
                "status": raw.get("outcome") or raw.get("status"),
                "latency_ms": raw.get("latency_ms"),
                "accepted": str(raw.get("outcome") or "") == "completed" and not raw.get("dropped"),
                "contributed_to_final_output": False,
                "reject_reason": raw.get("skipped_reason") or raw.get("reject_reason"),
                "prompt_hash": raw.get("prompt_hash"),
                "response_hash": raw.get("response_hash"),
                "forensic_ref": None,
                "legacy_budget_record": True,
            }
        )
    return merged


def count_interactions_by_role(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    items = [item for item in records or [] if isinstance(item, dict)]
    def _role(item: dict[str, Any]) -> str:
        return str(item.get("role") or "")

    def _attempted(item: dict[str, Any]) -> bool:
        status = str(item.get("status") or item.get("outcome") or "")
        if status in {"skipped", "not_called"}:
            return False
        validation = _as_dict(item.get("validation"))
        transport = str(validation.get("transport_status") or "")
        if transport in {"skipped", "not_called"}:
            return False
        if status or transport or item.get("latency_ms") is not None:
            return True
        response = _as_dict(item.get("response"))
        return bool(item.get("schema_version") == SCHEMA_VERSION or response.get("raw_text") is not None)

    def _completed(item: dict[str, Any]) -> bool:
        status = str(item.get("status") or item.get("outcome") or "")
        if status == "completed":
            return True
        validation = _as_dict(item.get("validation"))
        if str(validation.get("transport_status") or "") == "completed":
            return True
        response = _as_dict(item.get("response"))
        return bool(response.get("raw_text"))

    def _accepted(item: dict[str, Any]) -> bool:
        disposition = item.get("disposition") if isinstance(item.get("disposition"), dict) else {}
        return bool(item.get("accepted") or disposition.get("accepted"))

    sidecar = [item for item in items if _role(item) not in SYNTHESIS_ROLES]
    synthesis = [item for item in items if _role(item) in SYNTHESIS_ROLES]
    advisory = [item for item in items if _role(item) in SPL_ADVISORY_ROLES]
    repair = [item for item in items if _role(item) in SPL_REPAIR_ROLES]
    accepted_roles = sorted({_role(item) for item in items if _accepted(item) and _role(item)})
    dropped_roles = sorted(
        {_role(item) for item in items if _attempted(item) and not _accepted(item) and _role(item)}
    )
    return {
        "total_attempts": len([item for item in items if _attempted(item)]),
        "llm_sidecar_attempt_count": len([item for item in sidecar if _attempted(item)]),
        "llm_sidecar_completed_count": len([item for item in sidecar if _completed(item)]),
        "llm_synthesis_attempt_count": len([item for item in synthesis if _attempted(item)]),
        "llm_synthesis_completed_count": len([item for item in synthesis if _completed(item)]),
        "spl_advisory_attempt_count": len([item for item in advisory if _attempted(item)]),
        "llm_repair_attempt_count": len([item for item in repair if _attempted(item)]),
        "accepted_llm_roles": accepted_roles,
        "dropped_llm_roles": dropped_roles,
        "llm_used_in_final_answer": any(
            bool(
                item.get("contributed_to_final_output")
                or _as_dict(item.get("disposition")).get("contributed_to_final_output")
            )
            for item in items
        ),
    }


def _stage_for_role(role: str) -> str:
    if role in SYNTHESIS_ROLES:
        return "synthesis"
    if role in SPL_ADVISORY_ROLES:
        return "spl_authoring"
    if role in SPL_REPAIR_ROLES:
        return "spl_repair"
    return "sidecar"


def _status_from_record(record: dict[str, Any]) -> str:
    validation = _as_dict(record.get("validation"))
    transport = str(validation.get("transport_status") or "")
    if transport in {"timed_out", "timeout"}:
        return "timed_out"
    if transport in {"failed", "error", "blocked"}:
        return "failed"
    if record.get("response") and _as_dict(record.get("response")).get("raw_text"):
        return "completed"
    if transport:
        return transport
    return "completed" if record.get("latency_ms") is not None else "unknown"
