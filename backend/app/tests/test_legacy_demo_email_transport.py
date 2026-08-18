"""Legacy demo email uses the same ec_actions/ec_email transport as Workstream A."""

from __future__ import annotations

from app.demo import ec_actions, ec_email
from app.demo.ec_email import CONFIGURATION_REQUIRED, FakeEmailTransport


def setup_function() -> None:
    ec_actions.clear_all_for_tests()
    ec_email.clear_all_for_tests()


def test_prepare_legacy_email_action_accepts_extra(monkeypatch) -> None:
    fake = FakeEmailTransport()
    ec_email.set_transport_for_tests(fake)
    monkeypatch.setenv("AI_SOC_EC_EMAIL_SOC_LEAD", "lead@example.test")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_ALLOWLIST", "lead@example.test")
    prepared = ec_actions.prepare_action(
        kind="email_send",
        label="Coordinate CERT-In reporting stakeholders",
        session_id="legacy-cert",
        scenario_id="cert_in_ot_reporting_obligation",
        extra={
            "logical_recipient": "SOC_LEAD",
            "email": {
                "to": "SOC_LEAD",
                "subject": "CERT-In coordination",
                "body": "Synthetic legacy demo body",
            },
            "idempotency_key": "legacy-coord-cert_in_ot_reporting_obligation-legacy-cert",
        },
    )
    approved = ec_actions.approve_action(prepared.action_id)
    executed = ec_actions.execute_action(approved.action_id)
    assert executed.state == "EXECUTED"
    assert executed.receipt["status"] == "SUCCESS"
    assert executed.receipt["execution_mode"] == "fake_test_transport"
    assert len(fake.sent) == 1


def test_legacy_email_unconfigured_returns_configuration_required(monkeypatch) -> None:
    monkeypatch.setenv("AI_SOC_EC_EMAIL_TRANSPORT", "smtp")
    monkeypatch.delenv("AI_SOC_EC_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.setenv("AI_SOC_EC_EMAIL_SOC_LEAD", "lead@example.test")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_ALLOWLIST", "lead@example.test")
    ec_email.set_transport_for_tests(None)
    prepared = ec_actions.prepare_action(
        kind="email_send",
        label="Coordinate CERT-In reporting stakeholders",
        session_id="legacy-cert",
        scenario_id="cert_in_ot_reporting_obligation",
        extra={
            "logical_recipient": "SOC_LEAD",
            "email": {"to": "SOC_LEAD", "subject": "x", "body": "y"},
            "idempotency_key": "legacy-coord-cert",
        },
    )
    executed = ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id)
    assert executed.state == "FAILED"
    assert executed.receipt["status"] == CONFIGURATION_REQUIRED
