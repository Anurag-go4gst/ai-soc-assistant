"""P11 — real connectors execute, missing ones stay honest, and neither leaks into /chat."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.actions import email_adapter
from app.actions.email_adapter import RecordingEmailTransport, allowlisted, send_remediation_email
from app.actions.remediation_execution import (
    ADAPTERS,
    STATUS_SKIPPED_MANUAL,
    STATUS_SUCCESS,
    STATUS_UNAVAILABLE,
    execute_approved_remediation,
    idempotency_key_for,
)
from app.chat.contracts.remediation_plan import ApprovedRemediationEnvelope, RemediationStep
from app.config import settings

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
    yield transport
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
    assert receipt.verification_status == "verified"
    assert receipt.idempotency_key
    assert len(_recording.sent) == 1
    assert _recording.sent[0]["To"] == "soc@example.com"


def test_non_allowlisted_recipient_is_refused(_recording: RecordingEmailTransport) -> None:
    result = execute_approved_remediation(
        approved_envelope=_envelope(_step("email_send")),
        current_plan_fingerprint="fingerprint-a",
        context={"recipient": "attacker@evil.example"},
    )
    receipt = result.receipts[0]
    assert receipt.status != STATUS_SUCCESS
    assert receipt.reason == "recipient_not_allowlisted"
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
