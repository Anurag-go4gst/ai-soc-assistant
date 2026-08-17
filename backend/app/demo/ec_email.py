"""EC-only allowlisted outbound email. Never used by production /api/actions."""

from __future__ import annotations

import os
import smtplib
import sys
from dataclasses import dataclass, field
from email.message import EmailMessage
from threading import Lock
from typing import Any, Protocol

LOGICAL_TEAMS = (
    "FIREWALL_TEAM",
    "APPSEC_TEAM",
    "NETWORK_TEAM",
    "INCIDENT_OWNER",
    "OT_TEAM",
    "SOC_LEAD",
)

CONFIGURATION_REQUIRED = "REAL_EMAIL_CONFIGURATION_REQUIRED"

_lock = Lock()
_sent_keys: dict[str, dict[str, Any]] = {}
_transport_override: "EmailTransport | None" = None


@dataclass
class EmailReceipt:
    status: str
    execution_mode: str
    production_side_effect: bool = False
    external_side_effect: bool = False
    provider_message_id: str | None = None
    reason: str | None = None
    logical_recipient: str | None = None
    to: str | None = None

    def as_dict(self) -> dict[str, Any]:
        if self.status == "SUCCESS" and self.external_side_effect:
            summary = f"Email accepted by SMTP for {self.to}."
        elif self.status == "SUCCESS":
            summary = f"Test transport recorded email to {self.to} (not a live send)."
        else:
            summary = self.reason or "Email was not sent."
        return {
            "status": self.status,
            "execution_mode": self.execution_mode,
            "production_side_effect": self.production_side_effect,
            "external_side_effect": self.external_side_effect,
            "provider_message_id": self.provider_message_id,
            "reason": self.reason,
            "logical_recipient": self.logical_recipient,
            "to": self.to,
            "summary": summary,
            "provenance": "ec_allowlisted_email" if self.external_side_effect else "simulated_phase10_action",
        }


class EmailTransport(Protocol):
    def send(self, message: EmailMessage) -> EmailReceipt: ...


@dataclass
class FakeEmailTransport:
    sent: list[EmailMessage] = field(default_factory=list)

    def send(self, message: EmailMessage) -> EmailReceipt:
        self.sent.append(message)
        msg_id = f"fake-{len(self.sent)}"
        return EmailReceipt(
            status="SUCCESS",
            execution_mode="fake_test_transport",
            production_side_effect=False,
            external_side_effect=False,
            provider_message_id=msg_id,
            to=str(message["To"]),
        )


class SmtpEmailTransport:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls and not use_ssl
        self.use_ssl = use_ssl

    def send(self, message: EmailMessage) -> EmailReceipt:
        import ssl

        context = ssl.create_default_context()
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=15) as client:
                if self.user:
                    client.login(self.user, self.password)
                refused = client.send_message(message)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=15) as client:
                if self.use_tls:
                    client.starttls(context=context)
                if self.user:
                    client.login(self.user, self.password)
                refused = client.send_message(message)
        if refused:
            return EmailReceipt(
                status="FAILED",
                execution_mode="live_allowlisted_email",
                production_side_effect=False,
                external_side_effect=True,
                reason="provider_refused",
                to=str(message["To"]),
            )
        return EmailReceipt(
            status="SUCCESS",
            execution_mode="live_allowlisted_email",
            production_side_effect=False,
            external_side_effect=True,
            provider_message_id=str(message.get("Message-ID") or ""),
            to=str(message["To"]),
        )


def clear_all_for_tests() -> None:
    global _transport_override
    with _lock:
        _sent_keys.clear()
        _transport_override = None


def set_transport_for_tests(transport: EmailTransport | None) -> None:
    global _transport_override
    _transport_override = transport


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def logical_recipient_address(logical: str) -> str | None:
    key = f"AI_SOC_EC_EMAIL_{logical}"
    value = _env(key)
    return value or None


def allowlisted(address: str) -> bool:
    exact = {item.strip().lower() for item in _env("AI_SOC_EC_EMAIL_ALLOWLIST").split(",") if item.strip()}
    domains = {item.strip().lower().lstrip("@") for item in _env("AI_SOC_EC_EMAIL_ALLOWLIST_DOMAINS").split(",") if item.strip()}
    addr = address.strip().lower()
    if addr in exact:
        return True
    if "@" in addr and addr.split("@", 1)[1] in domains:
        return True
    return False


def configured_for_live() -> bool:
    return bool(_env("AI_SOC_EC_EMAIL_SMTP_HOST") and _env("AI_SOC_EC_EMAIL_FROM"))


def _active_transport() -> EmailTransport | None:
    if _transport_override is not None:
        return _transport_override
    mode = _env("AI_SOC_EC_EMAIL_TRANSPORT", "auto").lower()
    if mode == "fake" or (mode == "auto" and "pytest" in sys.modules):
        return FakeEmailTransport()
    if mode in {"auto", "smtp"} and configured_for_live():
        port = int(_env("AI_SOC_EC_EMAIL_SMTP_PORT", "587") or "587")
        ssl_flag = _env("AI_SOC_EC_EMAIL_SMTP_SSL", "true" if port == 465 else "false").lower() in {
            "1",
            "true",
            "yes",
        }
        return SmtpEmailTransport(
            host=_env("AI_SOC_EC_EMAIL_SMTP_HOST"),
            port=port,
            user=_env("AI_SOC_EC_EMAIL_SMTP_USER"),
            password=_env("AI_SOC_EC_EMAIL_SMTP_PASSWORD"),
            use_tls=not ssl_flag,
            use_ssl=ssl_flag,
        )
    return None


def resolve_recipient(extra: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    email = extra.get("email") if isinstance(extra.get("email"), dict) else {}
    raw = str(email.get("to") or extra.get("to") or "").strip()
    logical = str(extra.get("logical_recipient") or "").strip()
    if "@" in raw:
        return logical or None, raw, None
    token = logical or raw
    if token in LOGICAL_TEAMS:
        mapped = logical_recipient_address(token)
        return token, mapped, None if mapped else "logical_recipient_unmapped"
    return None, raw or None, None


def hydrate_draft(extra: dict[str, Any]) -> dict[str, Any]:
    payload = dict(extra)
    email = dict(payload.get("email") or {}) if isinstance(payload.get("email"), dict) else {}
    logical, address, _error = resolve_recipient(payload)
    if address:
        email["to"] = address
    if logical:
        payload["logical_recipient"] = logical
        email.setdefault("to", logical)
    payload["email"] = email
    return payload


def deliver(*, action_id: str, extra: dict[str, Any], idempotency_key: str) -> EmailReceipt:
    with _lock:
        existing = _sent_keys.get(idempotency_key)
        if existing is not None:
            return EmailReceipt(
                status=str(existing.get("status") or "SUCCESS"),
                execution_mode=str(existing.get("execution_mode") or "fake_test_transport"),
                production_side_effect=bool(existing.get("production_side_effect")),
                external_side_effect=bool(existing.get("external_side_effect")),
                provider_message_id=existing.get("provider_message_id"),
                reason=existing.get("reason"),
                logical_recipient=existing.get("logical_recipient"),
                to=existing.get("to"),
            )

    logical, address, map_error = resolve_recipient(extra)
    if map_error or not address:
        return EmailReceipt(
            status="FAILED",
            execution_mode="unconfigured",
            reason="logical_recipient_unmapped" if map_error else "recipient_missing",
            logical_recipient=logical,
        )
    if not allowlisted(address):
        return EmailReceipt(
            status="FAILED",
            execution_mode="allowlist_rejected",
            reason="recipient_not_allowlisted",
            logical_recipient=logical,
            to=address,
        )
    transport = _active_transport()
    if transport is None:
        return EmailReceipt(
            status=CONFIGURATION_REQUIRED,
            execution_mode="unconfigured",
            reason=CONFIGURATION_REQUIRED,
            logical_recipient=logical,
            to=address,
        )
    email = extra.get("email") if isinstance(extra.get("email"), dict) else {}
    message = EmailMessage()
    message["To"] = address
    message["From"] = _env("AI_SOC_EC_EMAIL_FROM") or "experience-center@localhost"
    message["Subject"] = str(email.get("subject") or "Experience Center notification")
    message.set_content(str(email.get("body") or "Experience Center synthetic notification. Not production data."))
    receipt = transport.send(message)
    receipt.logical_recipient = logical
    receipt.to = address
    if isinstance(transport, FakeEmailTransport):
        receipt.execution_mode = "fake_test_transport"
        receipt.external_side_effect = False
    with _lock:
        _sent_keys[idempotency_key] = receipt.as_dict()
        _sent_keys[action_id] = _sent_keys[idempotency_key]
    return receipt
