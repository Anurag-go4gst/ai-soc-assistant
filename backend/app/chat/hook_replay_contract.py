"""Typed allowlisted replay envelope for per-step hook idempotency (Workstream D I1)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HOOK_REPLAY_CONTRACT_VERSION = "2026-07-28"

HookName = Literal[
    "mcp_spl_search",
    "mcp_saved_search",
    "mcp_read_only",
    "guided_safe_catalog_execute",
]

_FORBIDDEN_ENVELOPE_KEYS = frozenset(
    {
        "password",
        "token",
        "api_key",
        "apikey",
        "bearer_token",
        "access_token",
        "auth_token",
        "secret",
        "credential",
        "connector",
        "dsn",
        "session_secret",
        "raw_result",
        "splunk_result_envelope",
        "results_preview",
    }
)

_SECRET_KEY_PATTERN = re.compile(
    r"(password|passwd|token|api[_-]?key|secret|credential|bearer|authorization|dsn)",
    re.IGNORECASE,
)

_ALLOWED_RESULT_SUMMARY_KEYS = frozenset(
    {
        "status",
        "execution_intent",
        "selected_mcp_server",
        "selected_mcp_tool",
        "tool_selection_status",
        "tool_selection_reason",
        "result_count",
        "block_reason",
        "duration_ms",
        "evidence_source",
        "execution_status_label",
        "outcome_uncertain",
        "human_review_required",
        "human_review_reason",
        "human_review_type",
        "collected_delta",
    }
)


class HookReplayEnvelope(BaseModel):
    """Allowlisted identity for hook-level replay — never arbitrary state patches."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["2026-07-28"] = HOOK_REPLAY_CONTRACT_VERSION
    hook_name: HookName
    resource_plan_id: str
    handoff_id: str | None = None
    handoff_version: int | None = None
    step_id: str
    operation_identity: str
    input_fingerprint: str

    @field_validator("resource_plan_id", "step_id", "operation_identity", "input_fingerprint")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("hook_replay_field_required")
        return cleaned

    @model_validator(mode="after")
    def _reject_forbidden_identity(self) -> HookReplayEnvelope:
        for field_name in ("resource_plan_id", "handoff_id", "step_id", "operation_identity"):
            raw = getattr(self, field_name)
            if isinstance(raw, str) and _SECRET_KEY_PATTERN.search(raw):
                raise ValueError(f"hook_replay_forbidden_field:{field_name}")
        return self


def build_input_fingerprint(*, allowlisted: dict[str, Any]) -> str:
    """Deterministic sha256 over sorted JSON of allowlisted scalar fields only."""
    normalized: dict[str, Any] = {}
    for key in sorted(allowlisted):
        value = allowlisted[key]
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            normalized[key] = value
        elif isinstance(value, (list, tuple)):
            normalized[key] = [str(item) for item in value]
        else:
            normalized[key] = str(value)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_mcp_execution_fingerprint(
    *,
    selected_mcp_tool: str,
    selected_mcp_server: str,
    normalized_spl: str | None,
    execution_intent: str,
    earliest: str | None = None,
    latest: str | None = None,
    saved_search_name: str | None = None,
) -> str:
    return build_input_fingerprint(
        allowlisted={
            "hook": "mcp_execution",
            "selected_mcp_tool": selected_mcp_tool,
            "selected_mcp_server": selected_mcp_server,
            "normalized_spl": normalized_spl,
            "execution_intent": execution_intent,
            "earliest": earliest,
            "latest": latest,
            "saved_search_name": saved_search_name,
        }
    )


def build_safe_catalog_fingerprint(
    *,
    template_id: str | None,
    normalized_spl: str | None,
    selected_mcp_tool: str | None,
) -> str:
    return build_input_fingerprint(
        allowlisted={
            "hook": "guided_safe_catalog_execute",
            "template_id": template_id,
            "normalized_spl": normalized_spl,
            "selected_mcp_tool": selected_mcp_tool,
        }
    )


def build_hook_operation_identity(envelope: HookReplayEnvelope) -> str:
    return f"{envelope.hook_name}:{envelope.input_fingerprint}"


def envelope_from_stored_result(stored: dict[str, Any] | None) -> HookReplayEnvelope | None:
    if not isinstance(stored, dict):
        return None
    raw = stored.get("hook_replay_envelope")
    if not isinstance(raw, dict):
        return None
    return HookReplayEnvelope.model_validate(raw)


def stored_envelope_matches(current: HookReplayEnvelope, stored: dict[str, Any] | None) -> bool:
    prior = envelope_from_stored_result(stored)
    if prior is None:
        return False
    return prior.model_dump() == current.model_dump()


def reject_forbidden_replay_fields(payload: dict[str, Any]) -> None:
    """Raise ValueError when replay payload carries non-allowlisted secret-like keys."""
    for key in payload:
        lowered = str(key).lower()
        if lowered in _FORBIDDEN_ENVELOPE_KEYS or _SECRET_KEY_PATTERN.search(lowered):
            raise ValueError(f"hook_replay_forbidden_key:{key}")


def sanitize_hook_result_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    summary: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if lowered in _FORBIDDEN_ENVELOPE_KEYS or _SECRET_KEY_PATTERN.search(lowered):
            continue
        if key in _ALLOWED_RESULT_SUMMARY_KEYS:
            summary[key] = value
    return summary


def build_stored_hook_payload(
    envelope: HookReplayEnvelope,
    *,
    execution: dict[str, Any] | None = None,
    human_review: dict[str, Any] | None = None,
    hop_patch: dict[str, Any] | None = None,
    connector_invoked: bool = False,
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    if isinstance(execution, dict):
        summary.update(sanitize_hook_result_summary(execution))
    if isinstance(human_review, dict):
        summary["human_review_required"] = bool(human_review.get("required"))
        summary["human_review_reason"] = human_review.get("reason")
        summary["human_review_type"] = human_review.get("review_type")
    reject_forbidden_replay_fields(summary)
    stored: dict[str, Any] = {
        "hook_replay_envelope": envelope.model_dump(),
        "result_summary": summary,
        "connector_invoked": connector_invoked,
    }
    if isinstance(execution, dict):
        stored["execution"] = sanitize_hook_result_summary(execution)
    if isinstance(human_review, dict):
        stored["human_review"] = {
            "required": bool(human_review.get("required")),
            "review_type": human_review.get("review_type"),
            "reason": human_review.get("reason"),
            "reviewer_role": human_review.get("reviewer_role"),
            "allowed_actions": list(human_review.get("allowed_actions") or []),
            "safe_message_for_user": human_review.get("safe_message_for_user"),
        }
    if isinstance(hop_patch, dict):
        stored["hop_patch"] = sanitize_hook_result_summary(hop_patch)
    return stored


def rehydrate_mcp_execution_pair(
    stored: dict[str, Any],
    *,
    selection: dict[str, Any],
    fallback_execution: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Restore execution/review from stored hook payload without elevating governance."""
    execution_raw = stored.get("execution")
    review_raw = stored.get("human_review")
    if not isinstance(execution_raw, dict):
        execution_raw = sanitize_hook_result_summary(fallback_execution or {})
    execution = {
        **selection,
        **sanitize_hook_result_summary(execution_raw),
        "execution_eligible": False,
    }
    if isinstance(review_raw, dict):
        review = {
            "required": bool(review_raw.get("required")),
            "review_type": review_raw.get("review_type") or "none",
            "reason": review_raw.get("reason") or "policy_checks_passed",
            "reviewer_role": review_raw.get("reviewer_role") or "analyst",
            "allowed_actions": list(review_raw.get("allowed_actions") or []),
            "safe_message_for_user": review_raw.get("safe_message_for_user") or "",
        }
    else:
        from app.orchestration.human_review import no_human_review

        review = no_human_review()
    if review.get("required"):
        execution["status"] = "requires_human_review"
    return execution, review


def rehydrate_safe_catalog_hop(stored: dict[str, Any]) -> dict[str, Any]:
    hop_patch = stored.get("hop_patch")
    if isinstance(hop_patch, dict):
        return sanitize_hook_result_summary(hop_patch)
    return sanitize_hook_result_summary(stored.get("result_summary") or {})
