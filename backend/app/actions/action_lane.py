"""Item 6.1 — action lane: LLM-proposed actions as data, never auto-executed.

An `ActionProposal` references an `action_tool` registry row only — never a
raw prompt, RAG chunk, or arbitrary string. The deterministic validator here
checks the tool exists and is dispatchable, that the payload's keys are a
subset of the tool's declared `input_contract.required_fields` (so a payload
can only carry CanonicalFacts-derived fields the tool actually declares, not
arbitrary internals), and that every required field is present. Nothing here
executes anything: `propose_action` records a pending proposal, `approve_action`
dispatches through the adapter (gated action executor), `deny_action` records
a denial. All three write a full audit record into the trace spine.

Live-turn proposal generation is additionally gated by the existing capability
disclosure (`app.actions.capability_policy.action_capability_for`): if the
current tier's `unavailable_actions` still lists a tool's underlying action
name, no live proposal is generated for it, even though the validator/adapter/
endpoint machinery below is fully built and directly testable. This keeps the
Tier-1 "Prepare" capability disclosure authoritative — building this lane
ahead of a tier change does not silently contradict it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.actions.itsm_adapter import ItsmAdapter, MockItsmAdapter
from app.planner.resource_registry import load_resource_registry

ActionStatus = Literal["pending_approval", "approved", "denied", "executed", "rejected"]


class ActionProposal(BaseModel):
    action_id: str
    tool_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    proposed_at: str
    status: ActionStatus = "pending_approval"
    reject_reason: str | None = None
    approver: str | None = None
    resolved_at: str | None = None
    outcome: dict[str, Any] | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_action_proposal(tool_id: str, payload: dict[str, Any]) -> tuple[bool, str | None]:
    """Deterministic validator: tool exists + dispatchable, payload keys are
    exactly the tool's declared `input_contract.args` (registry convention
    shared with mcp_tool/http_api rows), all present and non-empty."""
    descriptor = load_resource_registry().by_id(tool_id)
    if descriptor is None:
        return False, "unknown_action_tool"
    if descriptor.kind != "action_tool":
        return False, "not_an_action_tool"
    if descriptor.availability == "blocked":
        return False, "action_tool_blocked"
    contract = descriptor.input_contract or {}
    args = list(contract.get("args") or [])
    if not args:
        return False, "action_tool_missing_contract"
    allowed_fields = set(args)
    payload_keys = set(payload.keys())
    unexpected = payload_keys - allowed_fields
    if unexpected:
        return False, f"payload_keys_not_in_contract:{sorted(unexpected)}"
    missing = [field for field in args if field not in payload or not payload.get(field)]
    if missing:
        return False, f"missing_required_fields:{sorted(missing)}"
    return True, None


class ActionLaneStore:
    """In-process pending-action store. Mock-adapter posture only — a real
    connector (future plan item) would back this with durable persistence;
    scoping this to in-memory keeps the mock lane bounded and testable."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._actions: dict[str, ActionProposal] = {}

    def get(self, action_id: str) -> ActionProposal | None:
        with self._lock:
            return self._actions.get(action_id)

    def put(self, proposal: ActionProposal) -> None:
        with self._lock:
            self._actions[proposal.action_id] = proposal

    def clear(self) -> None:
        with self._lock:
            self._actions.clear()


_STORE = ActionLaneStore()


def get_action_lane_store() -> ActionLaneStore:
    return _STORE


def _record_audit(action: ActionProposal, *, event: str) -> None:
    try:
        from app.connectors.telemetry import get_telemetry_connector

        get_telemetry_connector().record_step(
            action.trace_id or action.action_id,
            "action_lane_audit",
            event,
            action_id=action.action_id,
            tool_id=action.tool_id,
            payload_hash=_payload_hash(action.payload),
            approver=action.approver,
            outcome=action.outcome,
        )
    except Exception:  # noqa: BLE001 - audit trail must never break the action flow
        pass


def propose_action(
    *,
    tool_id: str,
    payload: dict[str, Any],
    trace_id: str | None = None,
) -> ActionProposal:
    """Records a pending-approval proposal. Never executes anything."""
    action_id = f"act_{uuid.uuid4().hex[:12]}"
    valid, reason = validate_action_proposal(tool_id, payload)
    proposal = ActionProposal(
        action_id=action_id,
        tool_id=tool_id,
        payload=payload,
        trace_id=trace_id,
        proposed_at=_now(),
        status="pending_approval" if valid else "rejected",
        reject_reason=reason,
    )
    _STORE.put(proposal)
    _record_audit(proposal, event="proposed" if valid else "rejected_at_proposal")
    return proposal


def approve_action(
    action_id: str,
    *,
    approver: str,
    adapter: ItsmAdapter | None = None,
) -> ActionProposal | None:
    """Gated action executor: dispatches the mock adapter for a pending,
    previously-validated proposal. Returns None if the action_id is unknown."""
    proposal = _STORE.get(action_id)
    if proposal is None:
        return None
    if proposal.status != "pending_approval":
        return proposal
    outcome = (adapter or MockItsmAdapter()).create_ticket(proposal.payload)
    resolved = proposal.model_copy(
        update={
            "status": "executed",
            "approver": approver,
            "resolved_at": _now(),
            "outcome": outcome,
        }
    )
    _STORE.put(resolved)
    _record_audit(resolved, event="approved_and_executed")
    return resolved


def deny_action(action_id: str, *, approver: str) -> ActionProposal | None:
    """Records a denial. Never executes anything."""
    proposal = _STORE.get(action_id)
    if proposal is None:
        return None
    if proposal.status != "pending_approval":
        return proposal
    resolved = proposal.model_copy(
        update={"status": "denied", "approver": approver, "resolved_at": _now()}
    )
    _STORE.put(resolved)
    _record_audit(resolved, event="denied")
    return resolved
