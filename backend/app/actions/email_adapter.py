"""Production allowlisted outbound email adapter (architecture P11).

Deliberately a **separate** module from the Experience Center's ``app.demo.ec_email``:
production ``/chat`` must never import demo code. The transport shape is the same
because SMTP is SMTP; the governance around it is not shared.

Configuration reads ``AI_SOC_ACTION_EMAIL_*`` and falls back to the already-provisioned
``AI_SOC_EC_EMAIL_*`` values so an operator does not have to re-enter the same SMTP
credentials twice on a host where they already exist. Credentials are never returned,
logged, or placed in a receipt — only booleans and the resolved recipient.

Sending is off unless ``AI_SOC_ACTION_EMAIL_ENABLED`` is true **and** the recipient
is allowlisted. A non-allowlisted or unconfigured send is reported honestly as a
failure; it is never reported as a success.
"""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any, Protocol

_ALLOWLIST_KEYS = ("AI_SOC_ACTION_EMAIL_ALLOWLIST", "AI_SOC_EC_EMAIL_ALLOWLIST")
_ALLOWLIST_DOMAIN_KEYS = (
    "AI_SOC_ACTION_EMAIL_ALLOWLIST_DOMAINS",
    "AI_SOC_EC_EMAIL_ALLOWLIST_DOMAINS",
)


@dataclass
class EmailSendReceipt:
    """What actually happened. ``external_side_effect`` is the honest bit."""

    status: str
    execution_mode: str
    external_side_effect: bool = False
    provider_message_id: str | None = None
    reason: str | None = None
    to: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "execution_mode": self.execution_mode,
            "external_side_effect": self.external_side_effect,
            "provider_message_id": self.provider_message_id,
            "reason": self.reason,
            "to": self.to,
            "provenance": "production_allowlisted_email",
        }


class EmailTransport(Protocol):
    def send(self, message: EmailMessage) -> EmailSendReceipt: ...


@dataclass
class RecordingEmailTransport:
    """Test double. Records the message and never touches the network."""

    sent: list[EmailMessage] = field(default_factory=list)

    def send(self, message: EmailMessage) -> EmailSendReceipt:
        self.sent.append(message)
        return EmailSendReceipt(
            status="SUCCESS",
            execution_mode="recording_test_transport",
            external_side_effect=False,
            provider_message_id=f"recorded-{len(self.sent)}",
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
        use_ssl: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_ssl = use_ssl

    def send(self, message: EmailMessage) -> EmailSendReceipt:
        import ssl

        context = ssl.create_default_context()
        try:
            if self.use_ssl:
                with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=15) as client:
                    if self.user:
                        client.login(self.user, self.password)
                    refused = client.send_message(message)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=15) as client:
                    client.starttls(context=context)
                    if self.user:
                        client.login(self.user, self.password)
                    refused = client.send_message(message)
        except Exception as exc:  # noqa: BLE001 - transport failure is reported, never swallowed
            return EmailSendReceipt(
                status="FAILED",
                execution_mode="live_allowlisted_email",
                external_side_effect=False,
                reason=f"smtp_error:{type(exc).__name__}",
                to=str(message["To"]),
            )
        if refused:
            return EmailSendReceipt(
                status="FAILED",
                execution_mode="live_allowlisted_email",
                external_side_effect=True,
                reason="provider_refused",
                to=str(message["To"]),
            )
        return EmailSendReceipt(
            status="SUCCESS",
            execution_mode="live_allowlisted_email",
            external_side_effect=True,
            provider_message_id=str(message.get("Message-ID") or ""),
            to=str(message["To"]),
        )


_transport_override: EmailTransport | None = None


def set_transport_for_tests(transport: EmailTransport | None) -> None:
    global _transport_override
    _transport_override = transport


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _csv(*names: str) -> set[str]:
    return {item.strip().lower() for item in _env(*names).split(",") if item.strip()}


def allowlisted(address: str) -> bool:
    """Exact address or allowlisted domain. An empty allowlist allows nothing."""
    candidate = str(address or "").strip().lower()
    if not candidate or "@" not in candidate:
        return False
    if candidate in _csv(*_ALLOWLIST_KEYS):
        return True
    domain = candidate.rsplit("@", 1)[-1]
    return domain in {item.lstrip("@") for item in _csv(*_ALLOWLIST_DOMAIN_KEYS)}


def configured() -> bool:
    """True when a host and sender exist — availability, not authorization."""
    host = _env("AI_SOC_ACTION_EMAIL_SMTP_HOST", "AI_SOC_EC_EMAIL_SMTP_HOST")
    sender = _env("AI_SOC_ACTION_EMAIL_FROM", "AI_SOC_EC_EMAIL_FROM")
    return bool(host and sender)


def _active_transport() -> EmailTransport | None:
    if _transport_override is not None:
        return _transport_override
    if not configured():
        return None
    port = int(_env("AI_SOC_ACTION_EMAIL_SMTP_PORT", "AI_SOC_EC_EMAIL_SMTP_PORT", default="587"))
    ssl_raw = _env(
        "AI_SOC_ACTION_EMAIL_SMTP_SSL",
        "AI_SOC_EC_EMAIL_SMTP_SSL",
        default="true" if port == 465 else "false",
    )
    return SmtpEmailTransport(
        host=_env("AI_SOC_ACTION_EMAIL_SMTP_HOST", "AI_SOC_EC_EMAIL_SMTP_HOST"),
        port=port,
        user=_env("AI_SOC_ACTION_EMAIL_SMTP_USER", "AI_SOC_EC_EMAIL_SMTP_USER"),
        password=_env("AI_SOC_ACTION_EMAIL_SMTP_PASSWORD", "AI_SOC_EC_EMAIL_SMTP_PASSWORD"),
        use_ssl=ssl_raw.lower() in {"1", "true", "yes", "on"},
    )


def send_remediation_email(
    *,
    to: str,
    subject: str,
    body: str,
    idempotency_key: str,
) -> EmailSendReceipt:
    """Send one allowlisted remediation notification. Fails closed on every gate."""
    from app.config import settings

    if not getattr(settings, "ai_soc_action_email_enabled", False):
        return EmailSendReceipt(
            status="FAILED",
            execution_mode="disabled",
            reason="action_email_connector_disabled",
            to=to,
        )
    if not allowlisted(to):
        return EmailSendReceipt(
            status="FAILED",
            execution_mode="allowlist_rejected",
            reason="recipient_not_allowlisted",
            to=to,
        )
    transport = _active_transport()
    if transport is None:
        return EmailSendReceipt(
            status="FAILED",
            execution_mode="unconfigured",
            reason="action_email_not_configured",
            to=to,
        )
    message = EmailMessage()
    message["From"] = _env("AI_SOC_ACTION_EMAIL_FROM", "AI_SOC_EC_EMAIL_FROM")
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = f"<{idempotency_key}@ai-soc-assistant>"
    message.set_content(body)
    return transport.send(message)
