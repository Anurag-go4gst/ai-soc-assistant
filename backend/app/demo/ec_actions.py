"""In-memory Experience Center Phase 10 simulation. Never calls the production action lane."""

from __future__ import annotations

from threading import Lock
from typing import Any
from uuid import uuid4

from app.demo.ec_response import EcActionRecord

_ALLOWED_KINDS = frozenset(
    {
        "email_send",
        "email_reply",
        "ticket_create",
        "ticket_fetch",
        "ticket_update",
        "firewall_block",
        "firewall_remove_whitelist",
        "firewall_verify_rule",
        "cisco_get_version",
        "cisco_upgrade",
        "iam_disable",
        "edr_isolate",
        "notify",
    }
)

_STATES = (
    "PREPARED",
    "APPROVAL_REQUIRED",
    "APPROVED",
    "EXECUTED",
    "VERIFIED",
    "FAILED",
    "AWAITING_EXTERNAL_RESPONSE",
)

_lock = Lock()
_actions: dict[str, dict[str, Any]] = {}


def clear_all_for_tests() -> None:
    with _lock:
        _actions.clear()


def prepare_action(
    *,
    kind: str,
    label: str,
    session_id: str | None,
    scenario_id: str,
    extra: dict[str, Any] | None = None,
) -> EcActionRecord:
    if kind not in _ALLOWED_KINDS:
        raise ValueError(f"unsupported_ec_action_kind:{kind}")
    action_id = f"ec-act-{uuid4().hex[:12]}"
    record = {
        "action_id": action_id,
        "kind": kind,
        "label": label,
        "state": "APPROVAL_REQUIRED",
        "provenance": "simulated_phase10_action",
        "production_side_effect": False,
        "session_id": session_id,
        "scenario_id": scenario_id,
        "receipt": None,
        "verify_result": None,
        "extra": dict(extra or {}),
    }
    with _lock:
        _actions[action_id] = record
    return _to_model(record)


def get_action(action_id: str) -> EcActionRecord | None:
    with _lock:
        record = _actions.get(action_id)
        return _to_model(record) if record else None


def list_actions_for_session(session_id: str | None, scenario_id: str) -> list[EcActionRecord]:
    with _lock:
        rows = [
            record
            for record in _actions.values()
            if record.get("scenario_id") == scenario_id
            and (not session_id or record.get("session_id") == session_id)
        ]
    return [_to_model(record) for record in rows]


def approve_action(action_id: str) -> EcActionRecord:
    return _transition(action_id, from_states={"APPROVAL_REQUIRED", "PREPARED"}, to_state="APPROVED")


def execute_action(action_id: str) -> EcActionRecord:
    with _lock:
        record = _require(action_id)
        if record["state"] not in {"APPROVED", "APPROVAL_REQUIRED"}:
            raise ValueError(f"ec_action_not_executable:{record['state']}")
        if record["state"] == "APPROVAL_REQUIRED":
            record["state"] = "APPROVED"
        record["state"] = "EXECUTED"
        record["production_side_effect"] = False
        record["receipt"] = {
            "status": "SUCCESS",
            "production_side_effect": False,
            "provenance": "simulated_phase10_action",
            "summary": f"Simulated {record['kind']} completed with no production side effect.",
        }
        return _to_model(record)


def verify_action(action_id: str) -> EcActionRecord:
    with _lock:
        record = _require(action_id)
        if record["state"] != "EXECUTED":
            raise ValueError(f"ec_action_not_verifiable:{record['state']}")
        record["state"] = "VERIFIED"
        record["production_side_effect"] = False
        record["verify_result"] = {
            "verified": True,
            "production_side_effect": False,
            "provenance": "simulated_phase10_action",
            "summary": f"Simulated verification for {record['kind']} succeeded.",
        }
        return _to_model(record)


def seed_from_interactive_actions(
    *,
    interactive_actions: list[Any],
    session_id: str | None,
    scenario_id: str,
) -> list[EcActionRecord]:
    seeded: list[EcActionRecord] = []
    for item in interactive_actions:
        if not isinstance(item, dict):
            continue
        kind = "ticket_create" if "ticket" in str(item.get("id") or "").lower() else "notify"
        if kind not in _ALLOWED_KINDS:
            kind = "notify"
        seeded.append(
            prepare_action(
                kind=kind,
                label=str(item.get("label") or item.get("id") or kind),
                session_id=session_id,
                scenario_id=scenario_id,
                extra={"source_interactive_action_id": item.get("id")},
            )
        )
    return seeded


def _require(action_id: str) -> dict[str, Any]:
    record = _actions.get(action_id)
    if record is None:
        raise KeyError(action_id)
    return record


def _transition(action_id: str, *, from_states: set[str], to_state: str) -> EcActionRecord:
    if to_state not in _STATES:
        raise ValueError(f"invalid_ec_action_state:{to_state}")
    with _lock:
        record = _require(action_id)
        if record["state"] not in from_states:
            raise ValueError(f"ec_action_illegal_transition:{record['state']}->{to_state}")
        record["state"] = to_state
        record["production_side_effect"] = False
        return _to_model(record)


def _to_model(record: dict[str, Any]) -> EcActionRecord:
    return EcActionRecord(
        action_id=str(record["action_id"]),
        kind=str(record["kind"]),
        label=str(record["label"]),
        state=str(record["state"]),
        provenance="simulated_phase10_action",
        production_side_effect=False,
        receipt=record.get("receipt") if isinstance(record.get("receipt"), dict) else None,
        verify_result=record.get("verify_result") if isinstance(record.get("verify_result"), dict) else None,
    )
