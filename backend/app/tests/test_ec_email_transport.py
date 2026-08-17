"""EC allowlisted email transport — fake in pytest, never production /api/actions."""

from __future__ import annotations

from app.demo import ec_actions, ec_email
from app.demo.ec_email import CONFIGURATION_REQUIRED, FakeEmailTransport


def setup_function() -> None:
    ec_actions.clear_all_for_tests()
    ec_email.clear_all_for_tests()


def _prepare_email(**extra):
    return ec_actions.prepare_action(
        kind="email_send",
        label="Email firewall/security team",
        session_id="ec-mail",
        scenario_id="s3_firewall_team_coordination",
        extra=extra,
    )


def test_allowlist_reject_does_not_call_transport(monkeypatch) -> None:
    fake = FakeEmailTransport()
    ec_email.set_transport_for_tests(fake)
    monkeypatch.setenv("AI_SOC_EC_EMAIL_FIREWALL_TEAM", "fw@example.test")
    monkeypatch.delenv("AI_SOC_EC_EMAIL_ALLOWLIST", raising=False)
    monkeypatch.delenv("AI_SOC_EC_EMAIL_ALLOWLIST_DOMAINS", raising=False)
    prepared = _prepare_email(
        logical_recipient="FIREWALL_TEAM",
        email={"to": "FIREWALL_TEAM", "subject": "test", "body": "synthetic"},
        idempotency_key="mail-1",
    )
    executed = ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id)
    assert executed.state == "FAILED"
    assert executed.receipt["reason"] == "recipient_not_allowlisted"
    assert executed.receipt["production_side_effect"] is False
    assert fake.sent == []


def test_hil_required_before_send() -> None:
    prepared = _prepare_email(logical_recipient="FIREWALL_TEAM", email={"to": "FIREWALL_TEAM"})
    try:
        ec_actions.execute_action(prepared.action_id)
        raise AssertionError("execute must require approval")
    except ValueError as exc:
        assert "ec_action_not_executable" in str(exc)


def test_fake_transport_success_and_idempotent_second_execute(monkeypatch) -> None:
    fake = FakeEmailTransport()
    ec_email.set_transport_for_tests(fake)
    monkeypatch.setenv("AI_SOC_EC_EMAIL_FIREWALL_TEAM", "fw@example.test")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_ALLOWLIST", "fw@example.test")
    prepared = _prepare_email(
        logical_recipient="FIREWALL_TEAM",
        email={"to": "FIREWALL_TEAM", "subject": "SOC fixture", "body": "synthetic EC data"},
        idempotency_key="mail-dup",
    )
    first = ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id)
    assert first.state == "EXECUTED"
    assert first.receipt["status"] == "SUCCESS"
    assert first.receipt["production_side_effect"] is False
    assert first.receipt["external_side_effect"] is False
    assert first.receipt["execution_mode"] == "fake_test_transport"
    second = ec_actions.execute_action(first.action_id)
    assert second.state == "EXECUTED"
    assert len(fake.sent) == 1


def test_unconfigured_live_returns_configuration_required(monkeypatch) -> None:
    monkeypatch.setenv("AI_SOC_EC_EMAIL_TRANSPORT", "smtp")
    monkeypatch.delenv("AI_SOC_EC_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.setenv("AI_SOC_EC_EMAIL_FIREWALL_TEAM", "fw@example.test")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_ALLOWLIST", "fw@example.test")
    ec_email.set_transport_for_tests(None)
    prepared = _prepare_email(
        logical_recipient="FIREWALL_TEAM",
        email={"to": "FIREWALL_TEAM", "subject": "x", "body": "y"},
        idempotency_key="mail-unconfigured",
    )
    executed = ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id)
    assert executed.state == "FAILED"
    assert executed.receipt["status"] == CONFIGURATION_REQUIRED
    assert executed.receipt["production_side_effect"] is False
    assert executed.production_side_effect is False


def test_adapter_module_is_isolated_from_s3_pack() -> None:
    import inspect

    from app.demo.fixtures.s3 import pack as s3_pack

    source = inspect.getsource(s3_pack)
    assert "smtplib" not in source
    assert "routes_actions" not in source
    from app.demo import ec_email as adapter

    assert "smtplib" in inspect.getsource(adapter)


def test_smtp_ssl_uses_smtp_ssl_not_starttls(monkeypatch) -> None:
    from email.message import EmailMessage
    from unittest.mock import MagicMock

    import smtplib

    client = MagicMock()
    client.send_message.return_value = {}
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    ssl_ctor = MagicMock(return_value=client)
    monkeypatch.setattr(smtplib, "SMTP_SSL", ssl_ctor)
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(side_effect=AssertionError("STARTTLS path must not run")))
    transport = ec_email.SmtpEmailTransport(
        host="smtp.example.test",
        port=465,
        user="user",
        password="secret",
        use_ssl=True,
    )
    message = EmailMessage()
    message["To"] = "fw@example.test"
    message["From"] = "from@example.test"
    message["Subject"] = "t"
    message.set_content("body")
    receipt = transport.send(message)
    assert receipt.status == "SUCCESS"
    ssl_ctor.assert_called_once()
    assert ssl_ctor.call_args.args[0] == "smtp.example.test"
    assert ssl_ctor.call_args.args[1] == 465
    client.login.assert_called_once_with("user", "secret")


def test_active_transport_port_465_enables_ssl(monkeypatch) -> None:
    monkeypatch.setenv("AI_SOC_EC_EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_FROM", "from@example.test")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_SMTP_USER", "user")
    monkeypatch.setenv("AI_SOC_EC_EMAIL_SMTP_PASSWORD", "secret")
    monkeypatch.delenv("AI_SOC_EC_EMAIL_SMTP_SSL", raising=False)
    ec_email.set_transport_for_tests(None)
    transport = ec_email._active_transport()
    assert isinstance(transport, ec_email.SmtpEmailTransport)
    assert transport.use_ssl is True
    assert transport.use_tls is False
