"""P11 — real connectors execute, missing ones stay honest, and neither leaks into /chat."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.actions import email_adapter
from app.actions.email_adapter import RecordingEmailTransport, allowlisted, send_remediation_email
from app.actions.remediation_execution import (
    ADAPTERS,
    STATUS_FAILED,
    STATUS_SKIPPED_MANUAL,
    STATUS_SUCCESS,
    STATUS_UNAVAILABLE,
    execute_approved_remediation,
    idempotency_key_for,
)
from app.chat.capability_snapshot import production_registered_action_kinds
from app.chat import canonical_execution_idempotency
from app.chat.contracts.remediation_plan import ApprovedRemediationEnvelope, RemediationStep
from app.chat.pipeline import _apply_remediation_lifecycle
from app.chat.remediation_runtime import handle_remediation_review
from app.config import settings
from app.schemas.requests import ChatRequest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _step(
    capability_id: str,
    *,
    mode: str = "execute",
    availability: str = "available",
) -> RemediationStep:
    return RemediationStep(
        step_id=f"rem.01.{capability_id}",
        capability_id=capability_id,
        description=f"Perform {capability_id}.",
        execution_mode=mode,  # type: ignore[arg-type]
        availability=availability,  # type: ignore[arg-type]
        verification="Confirm the post-action state.",
        unavailable_reason=None if mode == "execute" else "capability_not_registered",
        action_arguments={"recipient": "soc@example.com"} if capability_id == "email_send" else {},
    )


def _envelope(*steps: RemediationStep, version: int = 1) -> ApprovedRemediationEnvelope:
    return ApprovedRemediationEnvelope(
        envelope_version=version,
        remediation_objective="Notify the owning team and contain the host.",
        approved_steps=list(steps),
        plan_fingerprint="fingerprint-a",
    )


@pytest.fixture()
def _recording(monkeypatch: pytest.MonkeyPatch) -> RecordingEmailTransport:
    transport = RecordingEmailTransport()
    email_adapter.set_transport_for_tests(transport)
    monkeypatch.setattr(settings, "ai_soc_action_email_enabled", True)
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_ALLOWLIST", "soc@example.com")
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_FROM", "ai-soc@example.com")
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_SMTP_HOST", "smtp.example.com")
    canonical_execution_idempotency.use_in_memory_store_for_tests(True)
    yield transport
    canonical_execution_idempotency.clear_in_memory_store_for_tests()
    canonical_execution_idempotency.use_in_memory_store_for_tests(False)
    email_adapter.set_transport_for_tests(None)


# ---------------------------------------------------------------- honest unavailability


def test_missing_agilius_connector_is_unavailable_not_success() -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(_step("agilus_submit_patch"))
    )
    receipt = result.receipts[0]
    assert receipt.status == STATUS_UNAVAILABLE
    assert receipt.reason == "capability_has_no_registered_adapter"
    assert receipt.external_side_effect is False
    assert result.executed_any is False


def test_manual_step_is_skipped_with_a_reason_not_executed() -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(
            _step("firewall_block", mode="manual_or_alternate", availability="unavailable")
        )
    )
    receipt = result.receipts[0]
    assert receipt.status == STATUS_SKIPPED_MANUAL
    assert receipt.reason == "capability_not_registered"


def test_every_step_yields_a_receipt() -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(
            _step("agilus_submit_patch"),
            _step("firewall_block", mode="manual_or_alternate", availability="unavailable"),
        )
    )
    assert len(result.receipts) == 2


# ---------------------------------------------------------------- approval binding


def test_superseded_plan_fingerprint_refuses_the_whole_envelope(
    _recording: RecordingEmailTransport,
) -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(_step("email_send")),
        current_plan_fingerprint="fingerprint-b",
        context={"recipient": "soc@example.com"},
    )
    assert result.refused_reason == "approved_plan_superseded"
    assert result.receipts == []
    assert _recording.sent == []


def test_idempotency_key_changes_with_envelope_version() -> None:
    step = _step("email_send")
    first = idempotency_key_for(_envelope(step, version=1), step)
    second = idempotency_key_for(_envelope(step, version=2), step)
    assert first != second


# ---------------------------------------------------------------- execution + verification


def test_allowlisted_email_executes_and_verifies(_recording: RecordingEmailTransport) -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(_step("email_send")),
        current_plan_fingerprint="fingerprint-a",
        context={"recipient": "soc@example.com"},
    )
    receipt = result.receipts[0]
    assert receipt.status == STATUS_SUCCESS
    assert receipt.verification_status == "provider_accepted"
    assert receipt.idempotency_key
    assert len(_recording.sent) == 1
    assert _recording.sent[0]["To"] == "soc@example.com"


def test_duplicate_approval_replays_receipt_without_a_second_send(
    _recording: RecordingEmailTransport,
) -> None:
    envelope = _envelope(_step("email_send"))
    first = execute_approved_remediation(approved_envelope=envelope)
    second = execute_approved_remediation(approved_envelope=envelope)
    assert first.receipts[0].status == STATUS_SUCCESS
    assert second.receipts[0].status == STATUS_SUCCESS
    assert second.receipts[0].replayed is True
    assert len(_recording.sent) == 1


def test_action_rbac_denies_viewer_before_connector_call(
    _recording: RecordingEmailTransport,
) -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(_step("email_send")),
        context={"rbac_role": "viewer"},
    )
    assert result.refused_reason == "rbac_denied:viewer"
    assert result.receipts == []
    assert _recording.sent == []


def test_production_snapshot_reports_email_only_with_bound_recipient(
    _recording: RecordingEmailTransport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert email_adapter.default_recipient() == "soc@example.com"
    assert production_registered_action_kinds()["email_send"] is True
    monkeypatch.setenv(
        "AI_SOC_ACTION_EMAIL_ALLOWLIST",
        "soc@example.com,second@example.com",
    )
    assert email_adapter.default_recipient() is None
    assert production_registered_action_kinds()["email_send"] is False


def test_production_chat_approval_executes_exact_envelope_and_returns_verification(
    _recording: RecordingEmailTransport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)
    created = handle_remediation_review(
        {
            "investigation_outcome": {
                "investigation_status": "completed",
                "disposition": "suspicious",
                "action_eligibility": {
                    "allowed_actions": ["email_send"],
                    "unavailable_actions": [],
                },
            },
            "capability_snapshot": {
                "rows": [
                    {
                        "capability_id": "action:email_send",
                        "capability_need": "recommended",
                        "availability": "available",
                    }
                ]
            },
        },
        action="create",
    )
    result = _apply_remediation_lifecycle(
        {
            **created,
            "request": ChatRequest(
                message="Approve remediation",
                remediation_review_action="approve",
            ),
        }
    )
    receipt = result["remediation_execution"]["receipts"][0]
    assert receipt["status"] == STATUS_SUCCESS
    assert receipt["verification_status"] == "provider_accepted"
    assert result["remediation_approval"]["execution_result"] == result["remediation_execution"]
    assert len(_recording.sent) == 1


def test_non_allowlisted_recipient_is_refused(_recording: RecordingEmailTransport) -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(_step("email_send")),
        current_plan_fingerprint="fingerprint-a",
        context={"recipient": "attacker@evil.example"},
    )
    receipt = result.receipts[0]
    assert receipt.status != STATUS_SUCCESS
    assert receipt.reason == "exact_call_arguments_mismatch"
    assert _recording.sent == []


def test_connector_flag_off_refuses_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_action_email_enabled", False)
    receipt = send_remediation_email(
        to="soc@example.com", subject="s", body="b", idempotency_key="k"
    )
    assert receipt.status == "FAILED"
    assert receipt.reason == "action_email_connector_disabled"
    assert receipt.external_side_effect is False


def test_empty_allowlist_allows_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_SOC_ACTION_EMAIL_ALLOWLIST", raising=False)
    monkeypatch.delenv("AI_SOC_EC_EMAIL_ALLOWLIST", raising=False)
    monkeypatch.delenv("AI_SOC_ACTION_EMAIL_ALLOWLIST_DOMAINS", raising=False)
    monkeypatch.delenv("AI_SOC_EC_EMAIL_ALLOWLIST_DOMAINS", raising=False)
    assert allowlisted("anyone@example.com") is False


def test_receipt_never_carries_credentials(_recording: RecordingEmailTransport) -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(_step("email_send")),
        context={"recipient": "soc@example.com"},
    )
    serialized = str(result.as_dict()).lower()
    for marker in ("password", "smtp_password", "secret", "api_key"):
        assert marker not in serialized


# ---------------------------------------------------------------- separation of concerns


def test_production_action_layer_does_not_import_experience_center() -> None:
    completed = subprocess.run(
        ["grep", "-rn", "from app.demo", str(_BACKEND_ROOT / "app" / "actions")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.stdout.strip() == "", completed.stdout


def test_chat_and_planner_do_not_import_ec_email_or_soar() -> None:
    completed = subprocess.run(
        [
            "grep",
            "-rnE",
            r"from app\.demo(\.| import).*(ec_email|ec_soar)",
            str(_BACKEND_ROOT / "app" / "chat"),
            str(_BACKEND_ROOT / "app" / "planner"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.stdout.strip() == "", completed.stdout


def test_investigation_plan_delta_cannot_reach_the_action_gate() -> None:
    """A read-only investigation revision must not be able to execute a write."""
    source = (_BACKEND_ROOT / "app" / "chat" / "investigation_plan_delta.py").read_text(
        encoding="utf-8"
    )
    assert "remediation_execution" not in source
    assert "email_adapter" not in source
    assert "execute_approved_remediation" not in source


def test_adapter_registry_holds_only_registered_capabilities() -> None:
    assert set(ADAPTERS) == {"email_send"}


# ---------------------------------------------------------------- attack / negative matrix


def test_exact_call_email_a_cannot_authorize_email_b(
    _recording: RecordingEmailTransport,
) -> None:
    from app.actions.remediation_execution import authorize_exact_action

    step_a = _step("email_send")
    envelope = _envelope(step_a)
    ok, reason, _fp = authorize_exact_action(
        envelope=envelope,
        step=step_a,
        requested_capability_id="email_send",
        requested_arguments={"recipient": "other@example.com"},
    )
    assert ok is False
    assert reason == "exact_call_arguments_mismatch"
    result = execute_approved_remediation(
        approved_envelope=envelope,
        context={"recipient": "other@example.com"},
    )
    assert result.receipts[0].status == STATUS_FAILED
    assert result.receipts[0].reason == "exact_call_arguments_mismatch"
    assert _recording.sent == []


def test_exact_call_email_cannot_authorize_firewall_block(
    _recording: RecordingEmailTransport,
) -> None:
    from app.actions.remediation_execution import authorize_exact_action

    step = _step("email_send")
    envelope = _envelope(step)
    ok, reason, _fp = authorize_exact_action(
        envelope=envelope,
        step=step,
        requested_capability_id="firewall_block",
        requested_arguments=dict(step.action_arguments),
    )
    assert ok is False
    assert reason == "exact_call_capability_mismatch"
    assert _recording.sent == []


def test_payload_subject_body_mutation_invalidates_exact_call_fingerprint(
    _recording: RecordingEmailTransport,
) -> None:
    from app.actions.remediation_execution import (
        authorize_exact_action,
        exact_call_payload_fingerprint,
        _execute_email,
    )

    step = _step("email_send")
    envelope = _envelope(step)
    original = exact_call_payload_fingerprint(envelope=envelope, step=step)
    mutated_step = step.model_copy(update={"description": "Send a different body entirely."})
    mutated = exact_call_payload_fingerprint(envelope=envelope, step=mutated_step)
    assert original != mutated
    ok, reason, _fp = authorize_exact_action(
        envelope=envelope,
        step=step,
        requested_capability_id="email_send",
        requested_arguments=dict(step.action_arguments),
        expected_fingerprint=mutated,
    )
    assert ok is False
    assert reason == "exact_call_grant_invalidated"
    receipt = _execute_email(
        step,
        envelope=envelope,
        context={"expected_exact_call_fingerprint": mutated},
    )
    assert receipt.status == STATUS_FAILED
    assert receipt.reason == "exact_call_grant_invalidated"
    assert _recording.sent == []


def test_connector_parameter_injection_is_rejected(
    _recording: RecordingEmailTransport,
) -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(_step("email_send")),
        context={"cc": "attacker@evil.example", "smtp_host": "evil.example"},
    )
    assert result.receipts[0].status == STATUS_FAILED
    assert "exact_call_context_injection" in str(result.receipts[0].reason)
    assert _recording.sent == []


def test_disable_connector_after_approval_blocks_write(
    _recording: RecordingEmailTransport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = _envelope(_step("email_send"))
    monkeypatch.setattr(settings, "ai_soc_action_email_enabled", False)
    result = execute_approved_remediation(approved_envelope=envelope)
    assert result.receipts[0].status == STATUS_FAILED
    assert result.receipts[0].reason == "action_email_connector_disabled"
    assert result.receipts[0].external_side_effect is False
    assert _recording.sent == []


def test_email_flag_off_keeps_snapshot_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_action_email_enabled", False)
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_ALLOWLIST", "soc@example.com")
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_FROM", "ai-soc@example.com")
    monkeypatch.setenv("AI_SOC_ACTION_EMAIL_SMTP_HOST", "smtp.example.com")
    assert production_registered_action_kinds()["email_send"] is False


def test_cancelled_envelope_is_not_reexecuted_via_stale_pin(
    _recording: RecordingEmailTransport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_remediation_planner_enabled", True)
    created = handle_remediation_review(
        {
            "investigation_outcome": {
                "investigation_status": "completed",
                "disposition": "suspicious",
                "action_eligibility": {
                    "allowed_actions": ["email_send"],
                    "unavailable_actions": [],
                },
            },
            "capability_snapshot": {
                "rows": [
                    {
                        "capability_id": "action:email_send",
                        "capability_need": "recommended",
                        "availability": "available",
                    }
                ]
            },
        },
        action="create",
    )
    cancelled = handle_remediation_review(created, action="cancel")
    assert cancelled["remediation_approval"]["status"] == "cancelled"
    # Cancel does not mint an envelope; pipeline approve path is the only executor.
    assert cancelled.get("approved_remediation_envelope") is None
    assert _recording.sent == []


def test_fingerprint_canonicalization_is_order_stable() -> None:
    from app.actions.remediation_execution import exact_call_payload_fingerprint

    step = RemediationStep(
        step_id="rem.01.email_send",
        capability_id="email_send",
        description="Notify soc.",
        execution_mode="execute",
        availability="available",
        verification="Confirm receipt.",
        action_arguments={"recipient": "soc@example.com", "note": "a"},
    )
    # Rebuild with reversed key insertion order — fingerprint must match.
    step_reordered = RemediationStep(
        step_id="rem.01.email_send",
        capability_id="email_send",
        description="Notify soc.",
        execution_mode="execute",
        availability="available",
        verification="Confirm receipt.",
        action_arguments={"note": "a", "recipient": "soc@example.com"},
    )
    envelope = _envelope(step)
    assert exact_call_payload_fingerprint(
        envelope=envelope, step=step
    ) == exact_call_payload_fingerprint(envelope=envelope, step=step_reordered)
