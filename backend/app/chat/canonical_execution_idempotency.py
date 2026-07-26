"""Durable execution idempotency for committed ResourcePlan steps (plan item 20)."""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Literal

import asyncpg
from pydantic import BaseModel, Field

from app.chat.canonical_db import canonical_db_disabled, run_in_canonical_unit_of_work, run_on_canonical_loop
from app.config import settings
from app.connectors.telemetry.redaction import minimize

_LOGGER = logging.getLogger("ai_soc.execution_idempotency")

ExecutionStepStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed_retryable",
    "failed_terminal",
    "execution_uncertain",
]

OperationReplayContract = Literal[
    "read_only_retryable",
    "side_effecting_with_stable_idempotency",
    "side_effecting_without_stable_idempotency",
]

DEFAULT_LEASE_SECONDS = 120

READ_ONLY_PURPOSES = frozenset({"mcp_discovery", "safe_catalog_query"})
POSSIBLY_SIDE_EFFECTING_PURPOSES = frozenset({"mcp_execution"})
READ_ONLY_MCP_TOOLS = frozenset(
    {
        "splunk_get_info",
        "splunk_get_indexes",
        "splunk_get_metadata",
        "splunk_get_knowledge_objects",
        "splunk_get_user_info",
        "splunk_run_query",
        "run_splunk_query",
    }
)

_TEST_STORE: dict[str, dict[str, Any]] = {}
_USE_TEST_STORE = False
_KEY_LOCKS: dict[str, threading.Lock] = {}
_LOCK_GUARD = threading.Lock()


class ExecutionIdempotencyError(Exception):
    """Execution idempotency record could not be acquired or persisted."""

    def __init__(self, reason: str, *, detail: str | None = None) -> None:
        self.reason = reason
        self.detail = detail or reason
        super().__init__(self.reason)


class AcquireOutcome(str, Enum):
    EXECUTE = "execute"
    REPLAY = "replay"
    IN_PROGRESS = "in_progress"
    REQUIRES_RECONCILIATION = "requires_reconciliation"


class ExecutionIdempotencyRecord(BaseModel):
    resource_plan_id: str
    step_id: str
    idempotency_key: str
    handoff_id: str | None = None
    handoff_version: int | None = None
    status: ExecutionStepStatus
    result: dict[str, Any] = Field(default_factory=dict)
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    operation: str | None = None
    operation_contract: OperationReplayContract = "side_effecting_without_stable_idempotency"
    downstream_idempotency_key: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class AcquireStepResult:
    outcome: AcquireOutcome
    record: ExecutionIdempotencyRecord | None = None
    stored_result: dict[str, Any] | None = None


def use_in_memory_store_for_tests(enabled: bool = True) -> None:
    global _USE_TEST_STORE
    _USE_TEST_STORE = enabled
    if enabled:
        _TEST_STORE.clear()


def clear_in_memory_store_for_tests() -> None:
    _TEST_STORE.clear()


def in_memory_execution_idempotency_enabled() -> bool:
    return _USE_TEST_STORE


def is_side_effecting_purpose(purpose: str) -> bool:
    contract = operation_contract_for_purpose(str(purpose or ""))
    return contract != "read_only_retryable"


def operation_contract_for_purpose(purpose: str) -> OperationReplayContract:
    purpose = str(purpose or "")
    if purpose in READ_ONLY_PURPOSES:
        return "read_only_retryable"
    if purpose in POSSIBLY_SIDE_EFFECTING_PURPOSES:
        return "side_effecting_without_stable_idempotency"
    return "read_only_retryable"


def operation_contract_for_mcp_tool(tool_name: str | None) -> OperationReplayContract:
    safe_name = str(tool_name or "").strip()
    if safe_name in READ_ONLY_MCP_TOOLS:
        return "read_only_retryable"
    return "side_effecting_without_stable_idempotency"


def normalize_operation_contract(raw: str | None, *, default: OperationReplayContract) -> OperationReplayContract:
    value = str(raw or "").strip()
    allowed = {
        "read_only_retryable",
        "side_effecting_with_stable_idempotency",
        "side_effecting_without_stable_idempotency",
    }
    return value if value in allowed else default  # type: ignore[return-value]


def operation_contract_for_step(step: dict[str, Any]) -> OperationReplayContract:
    """Classify a ResourcePlan step by explicit operation/tool contract.

    Purpose is only a fallback. Unknown MCP execution tools default to no automatic
    stale-lease replay because their external side-effect posture is not proven.
    """
    explicit = normalize_operation_contract(
        step.get("operation_contract"),
        default="side_effecting_without_stable_idempotency",
    )
    if step.get("operation_contract"):
        return explicit
    purpose = str(step.get("purpose") or "")
    if purpose != "mcp_execution":
        return operation_contract_for_purpose(purpose)
    tool_name = str(step.get("selected_mcp_tool") or "")
    if not tool_name:
        resource_id = str(step.get("resource_id") or "")
        prefix = "mcp_tool:"
        tool_name = resource_id[len(prefix) :] if resource_id.startswith(prefix) else resource_id
    return operation_contract_for_mcp_tool(tool_name)


def build_idempotency_key(
    *,
    resource_plan_id: str,
    handoff_id: str | None,
    handoff_version: int | None,
    step_id: str,
    operation: str,
) -> str:
    version_token = "" if handoff_version is None else str(handoff_version)
    return "|".join(
        [
            str(resource_plan_id or ""),
            str(handoff_id or ""),
            version_token,
            str(step_id or ""),
            str(operation or ""),
        ]
    )


def build_downstream_idempotency_key(
    *,
    resource_plan_id: str,
    handoff_id: str | None,
    handoff_version: int | None,
    step_id: str,
    operation: str,
) -> str:
    canonical_identity = build_idempotency_key(
        resource_plan_id=resource_plan_id,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        step_id=step_id,
        operation=operation,
    )
    digest = hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()
    return f"canonical-op:{digest}"


def _lease_seconds() -> int:
    return max(30, int(getattr(settings, "ai_soc_execution_lease_seconds", DEFAULT_LEASE_SECONDS)))


def _key_lock(idempotency_key: str) -> threading.Lock:
    with _LOCK_GUARD:
        if idempotency_key not in _KEY_LOCKS:
            _KEY_LOCKS[idempotency_key] = threading.Lock()
        return _KEY_LOCKS[idempotency_key]


def _sanitize_result(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return minimize(payload) if isinstance(payload, dict) else {}


def _record_from_row(row: dict[str, Any]) -> ExecutionIdempotencyRecord:
    status = str(row.get("status") or "pending")
    if status == "started":
        status = "pending"
    result_raw = row.get("result")
    if isinstance(result_raw, str):
        result_raw = json.loads(result_raw)
    return ExecutionIdempotencyRecord(
        resource_plan_id=str(row.get("resource_plan_id") or ""),
        step_id=str(row.get("step_id") or ""),
        idempotency_key=str(row.get("idempotency_key") or ""),
        handoff_id=row.get("handoff_id"),
        handoff_version=row.get("handoff_version"),
        status=status,  # type: ignore[arg-type]
        result=dict(result_raw) if isinstance(result_raw, dict) else {},
        lease_owner=row.get("lease_owner"),
        lease_expires_at=row.get("lease_expires_at"),
        operation=row.get("operation"),
        operation_contract=normalize_operation_contract(
            row.get("operation_contract"),
            default="side_effecting_without_stable_idempotency",
        ),
        downstream_idempotency_key=row.get("downstream_idempotency_key"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _lease_expired(record: ExecutionIdempotencyRecord, *, now: datetime | None = None) -> bool:
    if record.lease_expires_at is None:
        return True
    current = now or datetime.now(UTC)
    expires = record.lease_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires <= current


def _resolve_acquire(
    record: ExecutionIdempotencyRecord,
    *,
    operation_contract: OperationReplayContract,
    now: datetime | None = None,
) -> AcquireStepResult:
    if record.status == "completed":
        return AcquireStepResult(
            outcome=AcquireOutcome.REPLAY,
            record=record,
            stored_result=dict(record.result),
        )
    if record.status == "running":
        if not _lease_expired(record, now=now):
            return AcquireStepResult(outcome=AcquireOutcome.IN_PROGRESS, record=record)
        if operation_contract == "read_only_retryable":
            return AcquireStepResult(outcome=AcquireOutcome.EXECUTE, record=record)
        if operation_contract == "side_effecting_with_stable_idempotency" and record.downstream_idempotency_key:
            return AcquireStepResult(outcome=AcquireOutcome.EXECUTE, record=record)
        return AcquireStepResult(
            outcome=AcquireOutcome.REQUIRES_RECONCILIATION,
            record=record,
            stored_result=_uncertain_result(record, reason="execution_outcome_uncertain"),
        )
    if record.status == "execution_uncertain":
        return AcquireStepResult(
            outcome=AcquireOutcome.REQUIRES_RECONCILIATION,
            record=record,
            stored_result=_uncertain_result(record, reason="execution_outcome_uncertain"),
        )
    if record.status == "failed_terminal":
        return AcquireStepResult(
            outcome=AcquireOutcome.REPLAY,
            record=record,
            stored_result=dict(record.result),
        )
    if record.status == "failed_retryable" and operation_contract == "side_effecting_without_stable_idempotency":
        return AcquireStepResult(
            outcome=AcquireOutcome.REQUIRES_RECONCILIATION,
            record=record,
            stored_result=_uncertain_result(record, reason="execution_outcome_uncertain"),
        )
    return AcquireStepResult(outcome=AcquireOutcome.EXECUTE, record=record)


def _uncertain_result(record: ExecutionIdempotencyRecord, *, reason: str) -> dict[str, Any]:
    return {
        **dict(record.result or {}),
        "reason": reason,
        "idempotency_key": record.idempotency_key,
        "resource_plan_id": record.resource_plan_id,
        "step_id": record.step_id,
        "operation": record.operation,
        "operation_contract": record.operation_contract,
        "downstream_idempotency_key": record.downstream_idempotency_key,
    }


async def acquire_step_for_execution(
    conn: asyncpg.Connection,
    *,
    resource_plan_id: str,
    step_id: str,
    operation: str,
    handoff_id: str | None,
    handoff_version: int | None,
    lease_owner: str | None = None,
    side_effecting: bool = True,
    operation_contract: OperationReplayContract | None = None,
) -> AcquireStepResult:
    contract = operation_contract or (
        "side_effecting_without_stable_idempotency" if side_effecting else "read_only_retryable"
    )
    idempotency_key = build_idempotency_key(
        resource_plan_id=resource_plan_id,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        step_id=step_id,
        operation=operation,
    )
    owner = lease_owner or str(uuid.uuid4())
    now = datetime.now(UTC)
    lease_until = now + timedelta(seconds=_lease_seconds())
    downstream_key = (
        build_downstream_idempotency_key(
            resource_plan_id=resource_plan_id,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            step_id=step_id,
            operation=operation,
        )
        if contract == "side_effecting_with_stable_idempotency"
        else None
    )

    inserted = await conn.fetchrow(
        """
        INSERT INTO canonical_execution_idempotency (
            resource_plan_id, step_id, idempotency_key, handoff_id, handoff_version,
            status, result, lease_owner, lease_expires_at, operation, operation_contract,
            downstream_idempotency_key, created_at, updated_at
        ) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13,$13)
        ON CONFLICT (idempotency_key) DO NOTHING
        RETURNING *
        """,
        resource_plan_id,
        step_id,
        idempotency_key,
        handoff_id,
        handoff_version,
        "pending",
        json.dumps({}),
        None,
        None,
        operation,
        contract,
        downstream_key,
        now,
    )
    if inserted is not None:
        record = _record_from_row(dict(inserted))
        resolved = _resolve_acquire(record, operation_contract=contract, now=now)
    else:
        row = await conn.fetchrow(
            """
            SELECT * FROM canonical_execution_idempotency
            WHERE idempotency_key = $1
            FOR UPDATE
            """,
            idempotency_key,
        )
        if row is None:
            raise RuntimeError(f"idempotency_row_missing_after_conflict:{idempotency_key}")
        record = _record_from_row(dict(row))
        if downstream_key and not record.downstream_idempotency_key:
            record = record.model_copy(update={"downstream_idempotency_key": downstream_key})
        resolved = _resolve_acquire(record, operation_contract=contract, now=now)

    if resolved.outcome == AcquireOutcome.EXECUTE:
        await conn.execute(
            """
            UPDATE canonical_execution_idempotency
            SET status = 'running', lease_owner = $2, lease_expires_at = $3,
                operation = $4, operation_contract = $5, downstream_idempotency_key = $6,
                updated_at = $7
            WHERE idempotency_key = $1
            """,
            idempotency_key,
            owner,
            lease_until,
            operation,
            contract,
            record.downstream_idempotency_key or downstream_key,
            now,
        )
        record = record.model_copy(
            update={
                "status": "running",
                "lease_owner": owner,
                "lease_expires_at": lease_until,
                "operation": operation,
                "operation_contract": contract,
                "downstream_idempotency_key": record.downstream_idempotency_key or downstream_key,
                "updated_at": now,
            }
        )
        resolved = AcquireStepResult(outcome=AcquireOutcome.EXECUTE, record=record)

    return resolved


async def complete_step_execution(
    conn: asyncpg.Connection,
    *,
    idempotency_key: str,
    result: dict[str, Any],
) -> ExecutionIdempotencyRecord:
    now = datetime.now(UTC)
    sanitized = _sanitize_result(result)
    row = await conn.fetchrow(
        """
        UPDATE canonical_execution_idempotency
        SET status = 'completed', result = $2::jsonb, lease_owner = NULL, lease_expires_at = NULL, updated_at = $3
        WHERE idempotency_key = $1
        RETURNING *
        """,
        idempotency_key,
        json.dumps(sanitized),
        now,
    )
    if row is None:
        raise ExecutionIdempotencyError("execution_idempotency_complete_missing", detail=idempotency_key)
    return _record_from_row(dict(row))


async def fail_step_execution(
    conn: asyncpg.Connection,
    *,
    idempotency_key: str,
    result: dict[str, Any],
    retryable: bool,
    uncertain: bool = False,
) -> ExecutionIdempotencyRecord:
    now = datetime.now(UTC)
    status: ExecutionStepStatus = "execution_uncertain" if uncertain else ("failed_retryable" if retryable else "failed_terminal")
    sanitized = _sanitize_result(result)
    row = await conn.fetchrow(
        """
        UPDATE canonical_execution_idempotency
        SET status = $2, result = $3::jsonb, lease_owner = NULL, lease_expires_at = NULL, updated_at = $4
        WHERE idempotency_key = $1
        RETURNING *
        """,
        idempotency_key,
        status,
        json.dumps(sanitized),
        now,
    )
    if row is None:
        raise ExecutionIdempotencyError("execution_idempotency_fail_missing", detail=idempotency_key)
    return _record_from_row(dict(row))


def _memory_acquire(
    *,
    resource_plan_id: str,
    step_id: str,
    operation: str,
    handoff_id: str | None,
    handoff_version: int | None,
    lease_owner: str | None,
    side_effecting: bool,
    operation_contract: OperationReplayContract | None = None,
) -> AcquireStepResult:
    contract = operation_contract or (
        "side_effecting_without_stable_idempotency" if side_effecting else "read_only_retryable"
    )
    idempotency_key = build_idempotency_key(
        resource_plan_id=resource_plan_id,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        step_id=step_id,
        operation=operation,
    )
    lock = _key_lock(idempotency_key)
    lock.acquire()
    try:
        now = datetime.now(UTC)
        owner = lease_owner or str(uuid.uuid4())
        lease_until = now + timedelta(seconds=_lease_seconds())
        downstream_key = (
            build_downstream_idempotency_key(
                resource_plan_id=resource_plan_id,
                handoff_id=handoff_id,
                handoff_version=handoff_version,
                step_id=step_id,
                operation=operation,
            )
            if contract == "side_effecting_with_stable_idempotency"
            else None
        )
        raw = _TEST_STORE.get(idempotency_key)
        if raw is None:
            record = ExecutionIdempotencyRecord(
                resource_plan_id=resource_plan_id,
                step_id=step_id,
                idempotency_key=idempotency_key,
                handoff_id=handoff_id,
                handoff_version=handoff_version,
                status="pending",
                operation=operation,
                operation_contract=contract,
                downstream_idempotency_key=downstream_key,
                created_at=now,
                updated_at=now,
            )
            resolved = AcquireStepResult(outcome=AcquireOutcome.EXECUTE, record=record)
        else:
            record = ExecutionIdempotencyRecord.model_validate(raw)
            if downstream_key and not record.downstream_idempotency_key:
                record = record.model_copy(update={"downstream_idempotency_key": downstream_key})
            resolved = _resolve_acquire(record, operation_contract=contract, now=now)

        if resolved.outcome == AcquireOutcome.EXECUTE:
            record = record.model_copy(
                update={
                    "status": "running",
                    "lease_owner": owner,
                    "lease_expires_at": lease_until,
                    "operation": operation,
                    "operation_contract": contract,
                    "downstream_idempotency_key": record.downstream_idempotency_key or downstream_key,
                    "updated_at": now,
                }
            )
            _TEST_STORE[idempotency_key] = record.model_dump(mode="json")
            return AcquireStepResult(outcome=AcquireOutcome.EXECUTE, record=record)

        return resolved
    finally:
        lock.release()


def _memory_complete(*, idempotency_key: str, result: dict[str, Any]) -> ExecutionIdempotencyRecord:
    lock = _key_lock(idempotency_key)
    lock.acquire()
    try:
        raw = _TEST_STORE.get(idempotency_key)
        if raw is None:
            raise ExecutionIdempotencyError("execution_idempotency_complete_missing", detail=idempotency_key)
        now = datetime.now(UTC)
        record = ExecutionIdempotencyRecord.model_validate(raw).model_copy(
            update={
                "status": "completed",
                "result": _sanitize_result(result),
                "lease_owner": None,
                "lease_expires_at": None,
                "updated_at": now,
            }
        )
        _TEST_STORE[idempotency_key] = record.model_dump(mode="json")
        return record
    finally:
        lock.release()


def _memory_fail(
    *,
    idempotency_key: str,
    result: dict[str, Any],
    retryable: bool,
    uncertain: bool = False,
) -> ExecutionIdempotencyRecord:
    lock = _key_lock(idempotency_key)
    lock.acquire()
    try:
        raw = _TEST_STORE.get(idempotency_key)
        if raw is None:
            raise ExecutionIdempotencyError("execution_idempotency_fail_missing", detail=idempotency_key)
        now = datetime.now(UTC)
        status: ExecutionStepStatus = "execution_uncertain" if uncertain else ("failed_retryable" if retryable else "failed_terminal")
        record = ExecutionIdempotencyRecord.model_validate(raw).model_copy(
            update={
                "status": status,
                "result": _sanitize_result(result),
                "lease_owner": None,
                "lease_expires_at": None,
                "updated_at": now,
            }
        )
        _TEST_STORE[idempotency_key] = record.model_dump(mode="json")
        return record
    finally:
        lock.release()


def _memory_inspect(idempotency_key: str) -> ExecutionIdempotencyRecord | None:
    raw = _TEST_STORE.get(idempotency_key)
    if raw is None:
        return None
    return ExecutionIdempotencyRecord.model_validate(raw)


def inspect_execution_step(
    *,
    resource_plan_id: str,
    step_id: str,
    operation: str,
    handoff_id: str | None = None,
    handoff_version: int | None = None,
) -> ExecutionIdempotencyRecord | None:
    idempotency_key = build_idempotency_key(
        resource_plan_id=resource_plan_id,
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        step_id=step_id,
        operation=operation,
    )
    if _USE_TEST_STORE:
        return _memory_inspect(idempotency_key)
    if canonical_db_disabled():
        return None

    async def _inspect(conn: asyncpg.Connection | None) -> ExecutionIdempotencyRecord | None:
        if conn is None:
            return None
        row = await conn.fetchrow(
            "SELECT * FROM canonical_execution_idempotency WHERE idempotency_key = $1",
            idempotency_key,
        )
        return _record_from_row(dict(row)) if row else None

    return run_in_canonical_unit_of_work(_inspect)


def acquire_execution_step(
    *,
    resource_plan_id: str,
    step_id: str,
    operation: str,
    handoff_id: str | None = None,
    handoff_version: int | None = None,
    lease_owner: str | None = None,
    side_effecting: bool = True,
    operation_contract: OperationReplayContract | None = None,
    conn: asyncpg.Connection | None = None,
) -> AcquireStepResult:
    if _USE_TEST_STORE:
        return _memory_acquire(
            resource_plan_id=resource_plan_id,
            step_id=step_id,
            operation=operation,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            lease_owner=lease_owner,
            side_effecting=side_effecting,
            operation_contract=operation_contract,
        )
    if canonical_db_disabled():
        raise ExecutionIdempotencyError("execution_idempotency_db_unavailable")

    async def _acquire(active_conn: asyncpg.Connection | None) -> AcquireStepResult:
        target = conn or active_conn
        if target is None:
            raise ExecutionIdempotencyError("execution_idempotency_db_unavailable")
        return await acquire_step_for_execution(
            target,
            resource_plan_id=resource_plan_id,
            step_id=step_id,
            operation=operation,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            lease_owner=lease_owner,
            side_effecting=side_effecting,
            operation_contract=operation_contract,
        )

    if conn is not None:
        return run_on_canonical_loop(
            acquire_step_for_execution(
                conn,
                resource_plan_id=resource_plan_id,
                step_id=step_id,
                operation=operation,
                handoff_id=handoff_id,
                handoff_version=handoff_version,
                lease_owner=lease_owner,
                side_effecting=side_effecting,
                operation_contract=operation_contract,
            )
        )
    return run_in_canonical_unit_of_work(_acquire)


def complete_execution_step(
    *,
    idempotency_key: str,
    result: dict[str, Any],
    conn: asyncpg.Connection | None = None,
) -> ExecutionIdempotencyRecord:
    if _USE_TEST_STORE:
        return _memory_complete(idempotency_key=idempotency_key, result=result)
    if canonical_db_disabled():
        raise ExecutionIdempotencyError("execution_idempotency_db_unavailable")

    async def _complete(active_conn: asyncpg.Connection | None) -> ExecutionIdempotencyRecord:
        target = conn or active_conn
        if target is None:
            raise ExecutionIdempotencyError("execution_idempotency_db_unavailable")
        return await complete_step_execution(target, idempotency_key=idempotency_key, result=result)

    if conn is not None:
        return run_on_canonical_loop(complete_step_execution(conn, idempotency_key=idempotency_key, result=result))
    return run_in_canonical_unit_of_work(_complete)


def fail_execution_step(
    *,
    idempotency_key: str,
    result: dict[str, Any],
    retryable: bool,
    uncertain: bool = False,
    conn: asyncpg.Connection | None = None,
) -> ExecutionIdempotencyRecord:
    if _USE_TEST_STORE:
        return _memory_fail(idempotency_key=idempotency_key, result=result, retryable=retryable, uncertain=uncertain)
    if canonical_db_disabled():
        raise ExecutionIdempotencyError("execution_idempotency_db_unavailable")

    async def _fail(active_conn: asyncpg.Connection | None) -> ExecutionIdempotencyRecord:
        target = conn or active_conn
        if target is None:
            raise ExecutionIdempotencyError("execution_idempotency_db_unavailable")
        return await fail_step_execution(
            target,
            idempotency_key=idempotency_key,
            result=result,
            retryable=retryable,
            uncertain=uncertain,
        )

    if conn is not None:
        return run_on_canonical_loop(
            fail_step_execution(conn, idempotency_key=idempotency_key, result=result, retryable=retryable, uncertain=uncertain)
        )
    return run_in_canonical_unit_of_work(_fail)


def _execute_with_optional_downstream_key(
    execute: Callable[..., dict[str, Any]],
    downstream_key: str | None,
    *,
    require_key_support: bool,
) -> dict[str, Any]:
    if downstream_key is None:
        return execute()
    signature = inspect.signature(execute)
    accepts_kw = "downstream_idempotency_key" in signature.parameters
    accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    if accepts_kw or accepts_kwargs:
        return execute(downstream_idempotency_key=downstream_key)
    if require_key_support:
        raise ExecutionIdempotencyError("downstream_idempotency_key_not_supported")
    return execute()


def run_idempotent_execution_step(
    *,
    resource_plan_id: str,
    step_id: str,
    operation: str,
    handoff_id: str | None,
    handoff_version: int | None,
    side_effecting: bool,
    lease_owner: str | None,
    execute: Callable[..., dict[str, Any]],
    operation_contract: OperationReplayContract | None = None,
    telemetry_state: dict[str, Any] | None = None,
) -> tuple[AcquireOutcome, dict[str, Any]]:
    """Acquire lease, run ``execute`` once, persist terminal status in one UoW."""
    from app.chat.planning_telemetry import emit_execution_step_event

    contract = operation_contract or (
        "side_effecting_without_stable_idempotency" if side_effecting else "read_only_retryable"
    )

    def _emit_step(event: str, *, status: str = "completed", error_category: str | None = None, replay: bool = False) -> None:
        if telemetry_state is None:
            return
        emit_execution_step_event(
            telemetry_state,
            event=event,
            resource_plan_id=resource_plan_id,
            step_id=step_id,
            operation=operation,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            status=status,
            error_category=error_category,
            replay=replay,
        )

    if _USE_TEST_STORE:
        acquired = _memory_acquire(
            resource_plan_id=resource_plan_id,
            step_id=step_id,
            operation=operation,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            lease_owner=lease_owner,
            side_effecting=side_effecting,
            operation_contract=contract,
        )
        if acquired.outcome == AcquireOutcome.REPLAY:
            _emit_step("execution_step.completed", status="completed", replay=True)
            return acquired.outcome, dict(acquired.stored_result or {})
        if acquired.outcome == AcquireOutcome.IN_PROGRESS:
            return acquired.outcome, {"reason": "execution_step_in_progress"}
        if acquired.outcome == AcquireOutcome.REQUIRES_RECONCILIATION:
            return acquired.outcome, dict(acquired.stored_result or {})
        key = acquired.record.idempotency_key if acquired.record else build_idempotency_key(
            resource_plan_id=resource_plan_id,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            step_id=step_id,
            operation=operation,
        )
        _emit_step("execution_step.started", status="running")
        try:
            result = _execute_with_optional_downstream_key(
                execute,
                acquired.record.downstream_idempotency_key if acquired.record else None,
                require_key_support=contract == "side_effecting_with_stable_idempotency",
            )
            _memory_complete(idempotency_key=key, result=result)
            _emit_step("execution_step.completed", status="completed")
            return AcquireOutcome.EXECUTE, result
        except Exception as exc:
            _memory_fail(
                idempotency_key=key,
                result={"error": str(exc)},
                retryable=not side_effecting,
                uncertain=side_effecting and contract == "side_effecting_without_stable_idempotency",
            )
            _emit_step("execution_step.failed", status="failed", error_category="execution_error")
            raise

    async def _run(conn: asyncpg.Connection | None) -> tuple[AcquireOutcome, dict[str, Any]]:
        if conn is None:
            raise ExecutionIdempotencyError("execution_idempotency_db_unavailable")
        acquired = await acquire_step_for_execution(
            conn,
            resource_plan_id=resource_plan_id,
            step_id=step_id,
            operation=operation,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            lease_owner=lease_owner,
            side_effecting=side_effecting,
            operation_contract=contract,
        )
        if acquired.outcome == AcquireOutcome.REPLAY:
            _emit_step("execution_step.completed", status="completed", replay=True)
            return acquired.outcome, dict(acquired.stored_result or {})
        if acquired.outcome == AcquireOutcome.IN_PROGRESS:
            return acquired.outcome, {"reason": "execution_step_in_progress"}
        if acquired.outcome == AcquireOutcome.REQUIRES_RECONCILIATION:
            return acquired.outcome, dict(acquired.stored_result or {})
        key = acquired.record.idempotency_key if acquired.record else build_idempotency_key(
            resource_plan_id=resource_plan_id,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            step_id=step_id,
            operation=operation,
        )
        _emit_step("execution_step.started", status="running")
        try:
            result = _execute_with_optional_downstream_key(
                execute,
                acquired.record.downstream_idempotency_key if acquired.record else None,
                require_key_support=contract == "side_effecting_with_stable_idempotency",
            )
            await complete_step_execution(conn, idempotency_key=key, result=result)
            _emit_step("execution_step.completed", status="completed")
            return AcquireOutcome.EXECUTE, result
        except Exception as exc:
            await fail_step_execution(
                conn,
                idempotency_key=key,
                result={"error": str(exc)},
                retryable=not side_effecting,
                uncertain=side_effecting and contract == "side_effecting_without_stable_idempotency",
            )
            _emit_step("execution_step.failed", status="failed", error_category="execution_error")
            raise

    return run_in_canonical_unit_of_work(_run)


def plan_step_operation_identity(step: dict[str, Any]) -> str:
    purpose = str(step.get("purpose") or "unknown")
    resource_id = str(step.get("resource_id") or "")
    return f"{purpose}:{resource_id}" if resource_id else purpose


def provenance_from_state(state: dict[str, Any]) -> tuple[str | None, int | None, str | None]:
    plan = state.get("evidence_plan")
    if not isinstance(plan, dict):
        return None, None, None
    resource_plan = plan.get("resource_plan")
    if not isinstance(resource_plan, dict):
        return None, None, None
    provenance = resource_plan.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    resource_plan_id = provenance.get("resource_plan_id")
    handoff_id = provenance.get("handoff_id") or state.get("handoff_id")
    handoff_version = provenance.get("handoff_version") or state.get("handoff_version")
    return (
        str(resource_plan_id) if resource_plan_id else None,
        int(handoff_version) if handoff_version is not None else None,
        str(handoff_id) if handoff_id else None,
    )


def apply_idempotent_hop_to_state(state: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    """Merge a replayed idempotency payload into pipeline state when present."""
    if not stored:
        return state
    hop_patch = stored.get("hop_patch")
    if isinstance(hop_patch, dict):
        return {**state, **hop_patch}
    return state


def apply_execution_uncertainty_to_state(state: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    """Surface manual reconciliation without asserting external success or failure."""
    reconciliation = {
        "required": True,
        "reason": "execution_outcome_uncertain",
        "detail": "A prior side-effecting execution lease expired before a terminal result was persisted.",
        "idempotency": dict(stored or {}),
    }
    review = {
        "required": True,
        "review_type": "manual_reconciliation",
        "reason": "execution_outcome_uncertain",
        "reviewer_role": "soc_lead",
        "allowed_actions": ["reconcile_external_tool_state", "record_manual_outcome", "escalate_to_platform_admin"],
        "safe_message_for_user": "Execution outcome is uncertain; manually reconcile before retrying.",
    }
    execution = {
        **(state.get("execution") if isinstance(state.get("execution"), dict) else {}),
        "status": "requires_human_review",
        "block_reason": "execution_outcome_uncertain",
        "outcome_uncertain": True,
    }
    trace = dict(state.get("plan_dispatch_trace") or {})
    trace["dispatch_source"] = "execution_reconciliation"
    trace["dispatch_schedule"] = []
    trace["reconciliation"] = reconciliation
    return {
        **state,
        "execution": execution,
        "execution_reconciliation": reconciliation,
        "human_review": review,
        "plan_dispatch_trace": trace,
    }


def guard_plan_dispatch_idempotency(state: dict[str, Any]) -> dict[str, Any] | None:
    """Return a failure state when a side-effecting step is already running elsewhere."""
    from app.chat.canonical_mode import build_canonical_failure_state
    from app.planner.executor import walk_plan_steps

    resource_plan_id, handoff_version, handoff_id = provenance_from_state(state)
    if not resource_plan_id:
        return None
    walk = walk_plan_steps(state)
    if walk is None:
        return None
    now = datetime.now(UTC)
    for step in walk.steps_in_order:
        step_id = str(step.get("step_id") or "")
        contract = operation_contract_for_step(step)
        if step_id in walk.blocked_step_ids or contract == "read_only_retryable":
            continue
        operation = plan_step_operation_identity(step)
        record = inspect_execution_step(
            resource_plan_id=resource_plan_id,
            step_id=step_id,
            operation=operation,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
        )
        if record is None:
            continue
        if record.status == "running" and not _lease_expired(record, now=now):
            return build_canonical_failure_state(
                state,
                outcome="execution_failed",
                reason="execution_step_in_progress",
                detail=step_id,
            )
        if record.status == "execution_uncertain" or (
            record.status == "running"
            and _lease_expired(record, now=now)
            and contract == "side_effecting_without_stable_idempotency"
        ):
            return apply_execution_uncertainty_to_state(
                state,
                _uncertain_result(record, reason="execution_outcome_uncertain"),
            )
    return None
