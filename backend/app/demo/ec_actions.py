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
        "agilus_patch_submit",
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
    extra_payload = dict(extra or {})
    if kind == "email_send":
        from app.demo import ec_email

        extra_payload = ec_email.hydrate_draft(extra_payload)
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
        "extra": extra_payload,
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


def restore_action_if_needed(action_id: str, snapshot: dict[str, Any] | None) -> None:
    """Re-register an action from the client envelope after process reload or store loss."""
    with _lock:
        if action_id in _actions:
            return
    if not isinstance(snapshot, dict) or str(snapshot.get("action_id") or "") != action_id:
        return
    kind = str(snapshot.get("kind") or "")
    if kind not in _ALLOWED_KINDS:
        return
    extra = _extra_from_public_record(snapshot)
    record = {
        "action_id": action_id,
        "kind": kind,
        "label": str(snapshot.get("label") or kind),
        "state": str(snapshot.get("state") or "APPROVAL_REQUIRED"),
        "provenance": str(snapshot.get("provenance") or "simulated_phase10_action"),
        "production_side_effect": False,
        "session_id": snapshot.get("session_id"),
        "scenario_id": snapshot.get("scenario_id"),
        "receipt": snapshot.get("receipt") if isinstance(snapshot.get("receipt"), dict) else None,
        "verify_result": snapshot.get("verify_result") if isinstance(snapshot.get("verify_result"), dict) else None,
        "extra": extra,
    }
    with _lock:
        _actions[action_id] = record


def approve_action(action_id: str, snapshot: dict[str, Any] | None = None) -> EcActionRecord:
    restore_action_if_needed(action_id, snapshot)
    return _transition(action_id, from_states={"APPROVAL_REQUIRED", "PREPARED"}, to_state="APPROVED")


def execute_action(
    action_id: str,
    draft: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
) -> EcActionRecord:
    restore_action_if_needed(action_id, snapshot)
    with _lock:
        record = _require(action_id)
        kind = str(record["kind"])
        if kind == "email_send" and record["state"] == "EXECUTED":
            return _to_model(record)
        if record["state"] != "APPROVED":
            raise ValueError(f"ec_action_not_executable:{record['state']}")
        extra = dict(record.get("extra") or {})
        if draft:
            extra = _merge_draft(kind, extra, draft)
            record["extra"] = extra
        if kind == "email_send":
            idempotency_key = str(extra.get("idempotency_key") or action_id)
        elif kind in {"firewall_block", "firewall_remove_whitelist"}:
            pass
        elif kind == "agilus_patch_submit":
            pass
        else:
            record["state"] = "EXECUTED"
            record["production_side_effect"] = False
            record["receipt"] = _simulated_receipt(kind, extra)
            return _to_model(record)
    if kind == "email_send":
        from app.demo import ec_email

        receipt = ec_email.deliver(action_id=action_id, extra=extra, idempotency_key=idempotency_key)
        with _lock:
            record = _require(action_id)
            record["production_side_effect"] = False
            record["receipt"] = receipt.as_dict()
            if receipt.status == "SUCCESS":
                record["state"] = "EXECUTED"
                if receipt.external_side_effect:
                    record["provenance"] = "ec_allowlisted_email"
            else:
                record["state"] = "FAILED"
            return _to_model(record)
    if kind == "agilus_patch_submit":
        job_id = str(extra.get("agilus_job_id") or "AGILUS-JOB-8842")
        patch_id = str(extra.get("patch_id") or "EG-VPN-12.3.5-EMERG")
        targets = list(extra.get("targets") or [])
        ticket = extra.get("ticket") if isinstance(extra.get("ticket"), dict) else {}
        ticket_id = str(ticket.get("id") or ticket.get("ticket_id") or "CHG-ZD-AGILUS-001")
        with _lock:
            record = _require(action_id)
            record["production_side_effect"] = False
            record["state"] = "AWAITING_EXTERNAL_RESPONSE"
            record["provenance"] = "simulated_phase10_action"
            record["receipt"] = {
                "status": "SUBMITTED",
                "production_side_effect": False,
                "provenance": "simulated_agilus_mcp",
                "agilus_job_id": job_id,
                "patch_id": patch_id,
                "targets": targets,
                "ticket_id": ticket_id,
                "summary": (
                    f"Agilus patch job {job_id} submitted for {', '.join(targets) or 'target gateways'}. "
                    f"Change ticket {ticket_id} created. Awaiting Agilus completion callback."
                ),
            }
            return _to_model(record)
    from app.demo import ec_soar

    receipt = ec_soar.submit_block(extra)
    with _lock:
        record = _require(action_id)
        record["production_side_effect"] = False
        record["receipt"] = receipt.as_dict()
        record["state"] = "EXECUTED" if receipt.status == "SUCCESS" else "FAILED"
        return _to_model(record)


def record_fixture_execution(action_id: str, *, summary: str) -> EcActionRecord:
    """EC fixture connected-action receipt when live transport is unmapped/unconfigured."""
    with _lock:
        record = _require(action_id)
        if record["state"] not in {"APPROVED", "FAILED", "EXECUTED"}:
            raise ValueError(f"ec_action_not_fixture_executable:{record['state']}")
        record["state"] = "EXECUTED"
        record["production_side_effect"] = False
        record["receipt"] = {
            "status": "SUCCESS",
            "execution_mode": "ec_fixture_connected",
            "production_side_effect": False,
            "external_side_effect": False,
            "summary": summary,
            "provenance": "experience_center_fixture",
        }
        return _to_model(record)


def verify_action(action_id: str, snapshot: dict[str, Any] | None = None) -> EcActionRecord:
    restore_action_if_needed(action_id, snapshot)
    with _lock:
        record = _require(action_id)
        if record["state"] != "EXECUTED":
            raise ValueError(f"ec_action_not_verifiable:{record['state']}")
        record["state"] = "VERIFIED"
        record["production_side_effect"] = False
        extra = dict(record.get("extra") or {})
        verify_payload = extra.get("verify_payload") if isinstance(extra.get("verify_payload"), dict) else {}
        record["verify_result"] = {
            "verified": True,
            "production_side_effect": False,
            "provenance": "simulated_phase10_action",
            "summary": f"Simulated verification for {record['kind']} succeeded.",
            **verify_payload,
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


def _simulated_receipt(kind: str, extra: dict[str, Any]) -> dict[str, Any]:
    ticket = extra.get("ticket") if isinstance(extra.get("ticket"), dict) else {}
    if kind.startswith("ticket"):
        ticket_id = ticket.get("ticket_id") or ticket.get("id") or "EC-SIM"
        ticket_record = {**ticket, "ticket_id": ticket_id, "id": ticket_id}
        return {
            "status": "SUCCESS",
            "production_side_effect": False,
            "provenance": "simulated_phase10_action",
            "summary": f"Incident ticket {ticket_id} created and linked to this investigation.",
            "ticket": ticket_record,
        }
    return {
        "status": "SUCCESS",
        "production_side_effect": False,
        "provenance": "simulated_phase10_action",
        "summary": f"Simulated {kind} recorded. No production side effect.",
        **({k: v for k, v in extra.items() if k not in {"source_interactive_action_id", "verify_payload", "soar"}}),
    }


def _merge_draft(kind: str, extra: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    merged = dict(extra)
    if kind == "email_send":
        email = dict(merged.get("email") or {}) if isinstance(merged.get("email"), dict) else {}
        for key in ("to", "subject", "body"):
            if draft.get(key):
                email[key] = str(draft[key])
        merged["email"] = email
        if "@" in str(email.get("to") or ""):
            merged.pop("logical_recipient", None)
            merged["logical_recipient"] = extra.get("logical_recipient")
        from app.demo import ec_email

        return ec_email.hydrate_draft(merged)
    if kind.startswith("ticket") and isinstance(merged.get("ticket"), dict):
        ticket = dict(merged["ticket"])
        ticket.update({key: value for key, value in draft.items() if value is not None})
        merged["ticket"] = ticket
        return merged
    if kind.startswith("firewall"):
        soar = dict(merged.get("soar") or {}) if isinstance(merged.get("soar"), dict) else {}
        soar.update({key: value for key, value in draft.items() if value is not None})
        merged["soar"] = soar
        if soar.get("indicator"):
            merged["indicator"] = soar["indicator"]
        return merged
    return merged


def _extra_from_public_record(record: dict[str, Any]) -> dict[str, Any]:
    kind = str(record.get("kind") or "")
    draft = record.get("draft") if isinstance(record.get("draft"), dict) else {}
    if kind == "email_send" or kind == "email_reply":
        from app.demo import ec_email

        email = {
            "to": str(draft.get("to") or ""),
            "subject": str(draft.get("subject") or ""),
            "body": str(draft.get("body") or ""),
        }
        logical = str(draft.get("logical_recipient") or email.get("to") or "")
        return ec_email.hydrate_draft({"logical_recipient": logical, "email": email})
    if kind.startswith("firewall"):
        indicator = str(draft.get("indicator") or "")
        return {
            "indicator": indicator,
            "requested_action": str(draft.get("action") or "block"),
            "auto_block": False,
            "soar": {
                "playbook": str(draft.get("playbook") or "ip_block"),
                "indicator": indicator,
                "action": str(draft.get("action") or "block"),
                "reason": str(draft.get("reason") or ""),
            },
            "verify_payload": {
                "rule_present": True,
                "indicator": indicator,
                "simulated": True,
            },
        }
    if kind.startswith("ticket"):
        ticket = dict(draft) if draft else {}
        return {"ticket": ticket}
    return {}


def _draft_from_extra(kind: str, extra: dict[str, Any]) -> dict[str, Any] | None:
    if kind == "email_send":
        email = extra.get("email") if isinstance(extra.get("email"), dict) else {}
        return {
            "to": str(email.get("to") or ""),
            "subject": str(email.get("subject") or ""),
            "body": str(email.get("body") or ""),
            "logical_recipient": str(extra.get("logical_recipient") or ""),
        }
    if kind.startswith("ticket"):
        ticket = extra.get("ticket") if isinstance(extra.get("ticket"), dict) else extra
        return dict(ticket) if isinstance(ticket, dict) else None
    if kind.startswith("firewall"):
        soar = extra.get("soar") if isinstance(extra.get("soar"), dict) else {}
        return {
            "playbook": str(soar.get("playbook") or "ip_block"),
            "indicator": str(soar.get("indicator") or extra.get("indicator") or ""),
            "action": str(soar.get("action") or extra.get("requested_action") or "block"),
            "reason": str(soar.get("reason") or extra.get("reason") or ""),
        }
    if kind == "agilus_patch_submit":
        ticket = extra.get("ticket") if isinstance(extra.get("ticket"), dict) else {}
        return {
            "patch_id": str(extra.get("patch_id") or ""),
            "targets": list(extra.get("targets") or []),
            "agilus_job_id": str(extra.get("agilus_job_id") or ""),
            "ticket_id": str(ticket.get("id") or ticket.get("ticket_id") or ""),
        }
    return None


def _to_model(record: dict[str, Any]) -> EcActionRecord:
    extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
    return EcActionRecord(
        action_id=str(record["action_id"]),
        kind=str(record["kind"]),
        label=str(record["label"]),
        state=str(record["state"]),
        provenance=str(record.get("provenance") or "simulated_phase10_action"),
        production_side_effect=False,
        receipt=record.get("receipt") if isinstance(record.get("receipt"), dict) else None,
        verify_result=record.get("verify_result") if isinstance(record.get("verify_result"), dict) else None,
        draft=_draft_from_extra(str(record["kind"]), extra),
    )
