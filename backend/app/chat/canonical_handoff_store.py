"""Durable canonical handoff persistence and idempotent ResourcePlan commits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.chat.canonical_handoff_models import CanonicalHandoffRecord, HandoffStatus
from app.chat.canonical_handoff_repository import (
    HandoffPersistenceError,
    clear_in_memory_store_for_tests,
    load_handoff_record,
    save_handoff_record,
    use_in_memory_store_for_tests,
)
from app.chat.contracts.canonical_planning_input import CONTRACT_VERSION
from app.config import settings


def _handoff_ttl() -> timedelta:
    minutes = max(5, int(getattr(settings, "ai_soc_handoff_store_ttl_minutes", 60)))
    return timedelta(minutes=minutes)


def save_handoff(record: CanonicalHandoffRecord, *, refresh_ttl: bool = True) -> CanonicalHandoffRecord:
    now = datetime.now(UTC)
    updated = record.model_copy(
        update={
            "updated_at": now,
            "expires_at": now + _handoff_ttl() if refresh_ttl else record.expires_at,
        }
    )
    return save_handoff_record(updated, refresh_ttl=False)


def get_handoff(handoff_id: str, handoff_version: int) -> CanonicalHandoffRecord | None:
    record = load_handoff_record(handoff_id, handoff_version)
    if record is None:
        return None
    if record.is_expired():
        delete_handoff(handoff_id, handoff_version)
        return None
    return record


def get_latest_handoff(handoff_id: str) -> CanonicalHandoffRecord | None:
    for version in range(100, 0, -1):
        record = get_handoff(handoff_id, version)
        if record is not None:
            return record
    return None


def delete_handoff(handoff_id: str, handoff_version: int) -> None:
    record = get_handoff(handoff_id, handoff_version)
    if record is None:
        return
    save_handoff(record.model_copy(update={"status": "expired"}), refresh_ttl=False)


def get_committed_resource_plan(handoff_id: str, handoff_version: int) -> tuple[str, dict, dict] | None:
    record = get_handoff(handoff_id, handoff_version)
    if record is None:
        return None
    if record.normalized_status() != "plan_committed":
        return None
    if not record.committed_resource_plan_id or not record.committed_resource_plan:
        return None
    return (
        record.committed_resource_plan_id,
        dict(record.committed_resource_plan),
        dict(record.committed_evidence_plan or {}),
    )


def commit_resource_plan(
    *,
    handoff_id: str,
    handoff_version: int,
    resource_plan_id: str,
    resource_plan: dict,
    evidence_plan: dict,
) -> CanonicalHandoffRecord:
    existing = get_committed_resource_plan(handoff_id, handoff_version)
    if existing is not None:
        record = get_handoff(handoff_id, handoff_version)
        if record is not None:
            return record
    record = get_handoff(handoff_id, handoff_version)
    if record is None:
        record = CanonicalHandoffRecord(handoff_id=handoff_id, handoff_version=handoff_version)
    updated = record.model_copy(
        update={
            "status": "plan_committed",
            "committed_resource_plan_id": resource_plan_id,
            "committed_resource_plan": resource_plan,
            "committed_evidence_plan": evidence_plan,
        }
    )
    return save_handoff(updated)


def save_clarification_handoff(
    *,
    handoff_id: str,
    handoff_version: int,
    canonical_planning_input: dict,
    gap_resolution: dict | None,
    unresolved_fields: list[str],
    clarification_reason: str,
    trace_id: str | None = None,
    session_id: str | None = None,
    original_query: str | None = None,
    original_skill: str | None = None,
    original_use_case_id: str | None = None,
    original_answer_goal: str | None = None,
    initial_tier: str | None = None,
    resolved_tier: str | None = None,
) -> CanonicalHandoffRecord:
    record = get_handoff(handoff_id, handoff_version)
    if record is None:
        record = CanonicalHandoffRecord(handoff_id=handoff_id, handoff_version=handoff_version)
    updated = record.model_copy(
        update={
            "status": "awaiting_clarification",
            "canonical_planning_input": canonical_planning_input,
            "gap_resolution": gap_resolution,
            "unresolved_fields": list(unresolved_fields),
            "clarification_reason": clarification_reason,
            "trace_id": trace_id,
            "session_id": session_id,
            "original_query": original_query,
            "original_skill": original_skill,
            "original_use_case_id": original_use_case_id,
            "original_answer_goal": original_answer_goal,
            "initial_tier": initial_tier,
            "resolved_tier": resolved_tier,
        }
    )
    return save_handoff(updated)


def record_duplicate_call_hash(handoff_id: str, handoff_version: int, call_hash: str) -> bool:
    record = get_handoff(handoff_id, handoff_version)
    if record is None:
        record = CanonicalHandoffRecord(handoff_id=handoff_id, handoff_version=handoff_version)
    hashes = list(record.duplicate_call_hashes)
    limit = max(1, int(getattr(settings, "ai_soc_guided_max_duplicate_tool_calls", 1)))
    if hashes.count(call_hash) >= limit:
        return True
    hashes.append(call_hash)
    save_handoff(record.model_copy(update={"duplicate_call_hashes": hashes}))
    return False


def clear_all_handoffs_for_tests() -> None:
    clear_in_memory_store_for_tests()


def contract_version() -> str:
    return CONTRACT_VERSION


__all__ = [
    "CanonicalHandoffRecord",
    "HandoffPersistenceError",
    "HandoffStatus",
    "clear_all_handoffs_for_tests",
    "commit_resource_plan",
    "contract_version",
    "delete_handoff",
    "get_committed_resource_plan",
    "get_handoff",
    "get_latest_handoff",
    "record_duplicate_call_hash",
    "save_clarification_handoff",
    "save_handoff",
    "use_in_memory_store_for_tests",
]
