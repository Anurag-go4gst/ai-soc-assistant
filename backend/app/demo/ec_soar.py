"""EC-only SOAR / firewall-block adapter. Never used by production /api/actions."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

CONFIGURATION_REQUIRED = "SOAR_OR_FIREWALL_MCP_NOT_CONFIGURED"


@dataclass
class SoarReceipt:
    status: str
    execution_mode: str
    production_side_effect: bool = False
    external_side_effect: bool = False
    reason: str | None = None
    playbook: str | None = None
    indicator: str | None = None
    summary: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "execution_mode": self.execution_mode,
            "production_side_effect": self.production_side_effect,
            "external_side_effect": self.external_side_effect,
            "reason": self.reason,
            "playbook": self.playbook,
            "indicator": self.indicator,
            "summary": self.summary,
            "provenance": "simulated_phase10_action",
        }


class SoarTransport(Protocol):
    def submit_block(self, payload: dict[str, Any]) -> SoarReceipt: ...


@dataclass
class FakeSoarTransport:
    submitted: list[dict[str, Any]] = field(default_factory=list)

    def submit_block(self, payload: dict[str, Any]) -> SoarReceipt:
        self.submitted.append(payload)
        indicator = str(payload.get("indicator") or "")
        return SoarReceipt(
            status="SUCCESS",
            execution_mode="fake_test_transport",
            production_side_effect=False,
            external_side_effect=False,
            playbook=str(payload.get("playbook") or "ip_block"),
            indicator=indicator,
            summary=f"Simulated SOAR block request recorded for {indicator or 'indicator'} (pytest fake; no production change).",
        )


class HttpSoarTransport:
    def __init__(self, *, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def submit_block(self, payload: dict[str, Any]) -> SoarReceipt:
        request = urllib.request.Request(
            f"{self.base_url}/playbooks/ip_block",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}" if self.token else "",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            return SoarReceipt(
                status="FAILED",
                execution_mode="live_soar_http",
                production_side_effect=False,
                external_side_effect=False,
                reason="soar_unreachable",
                playbook=str(payload.get("playbook") or "ip_block"),
                indicator=str(payload.get("indicator") or ""),
                summary=f"SOAR call failed: {exc}. No firewall change was applied.",
            )
        return SoarReceipt(
            status="SUCCESS",
            execution_mode="live_soar_http",
            production_side_effect=False,
            external_side_effect=True,
            playbook=str(payload.get("playbook") or "ip_block"),
            indicator=str(payload.get("indicator") or ""),
            summary=f"SOAR accepted the block request. Provider response: {body[:240]}",
        )


_transport_override: SoarTransport | None = None


def set_transport_for_tests(transport: SoarTransport | None) -> None:
    global _transport_override
    _transport_override = transport


def clear_all_for_tests() -> None:
    global _transport_override
    _transport_override = None


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def configured_for_live() -> bool:
    return bool(_env("AI_SOC_EC_SOAR_BASE_URL"))


def _active_transport() -> SoarTransport | None:
    if _transport_override is not None:
        return _transport_override
    mode = _env("AI_SOC_EC_SOAR_TRANSPORT", "auto").lower()
    if mode == "fake" or (mode == "auto" and "pytest" in sys.modules):
        return FakeSoarTransport()
    if mode in {"auto", "http"} and configured_for_live():
        return HttpSoarTransport(base_url=_env("AI_SOC_EC_SOAR_BASE_URL"), token=_env("AI_SOC_EC_SOAR_TOKEN"))
    return None


def submit_block(extra: dict[str, Any]) -> SoarReceipt:
    soar = extra.get("soar") if isinstance(extra.get("soar"), dict) else {}
    payload = {
        "playbook": str(soar.get("playbook") or extra.get("requested_action") or "ip_block"),
        "indicator": str(soar.get("indicator") or extra.get("indicator") or ""),
        "action": str(soar.get("action") or extra.get("requested_action") or "block"),
        "reason": str(soar.get("reason") or extra.get("reason") or ""),
    }
    transport = _active_transport()
    if transport is None:
        indicator = payload["indicator"]
        return SoarReceipt(
            status=CONFIGURATION_REQUIRED,
            execution_mode="unconfigured",
            production_side_effect=False,
            external_side_effect=False,
            reason=CONFIGURATION_REQUIRED,
            playbook=payload["playbook"],
            indicator=indicator,
            summary=(
                "SOAR / firewall MCP is not configured on this host. No production block was applied. "
                "Send the firewall-team email instead."
            ),
        )
    return transport.submit_block(payload)
