"""Unit and integration tests for T2 operation-aware review checklists."""

from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.chat.t2_review_checklist import build_t2_review_checklist
from app.config import settings
from app.schemas.requests import ChatRequest

_SCADA_BLOCK = {
    "runtime_operation": "threshold_anomaly",
    "source_profile": "scada_perf",
    "entity_fields": ["rtu_id"],
    "metric_fields": ["transmission_error_count"],
    "baseline_window": "30d",
    "detection_window": "24h",
}

_ASA_BLOCK = {
    "runtime_operation": "lookup_correlation",
    "source_profile": "cisco_asa",
    "lookup_name": "power_sector_iocs.csv",
    "lookup_match_field": "indicator_ip",
    "log_match_field": "dest_ip",
    "entity_fields": ["src_ip", "dest_ip"],
    "detection_window": "24h",
}


def _joined(items: list[str]) -> str:
    return " ".join(items).lower()


def test_threshold_anomaly_checklist_scada() -> None:
    items = build_t2_review_checklist(_SCADA_BLOCK)
    text = _joined(items)
    for token in ("scada_perf", "transmission_error_count", "rtu_id", "baseline"):
        assert token in text
    for bad in ("mfa", "dns", "user correlation", "privileged account", "post-login"):
        assert bad not in text


def test_lookup_correlation_checklist_asa() -> None:
    items = build_t2_review_checklist(_ASA_BLOCK)
    text = _joined(items)
    for token in (
        "cisco_asa",
        "power_sector_iocs.csv",
        "indicator_ip",
        "dest_ip",
        "investigation lead",
    ):
        assert token in text
    for bad in ("dns", "user correlation", "8h", "asset_name", "asset_ip", "asset inventory"):
        assert bad not in text


def test_unknown_operation_neutral_fallback() -> None:
    items = build_t2_review_checklist({"runtime_operation": "unknown"})
    text = _joined(items)
    assert "index, sourcetype" in text
    assert "review-only until analyst approval" in text
    assert "dns" not in text


@pytest.fixture(autouse=True)
def _enable_draft_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)


def test_failed_login_spl_uses_auth_not_scada_or_asa() -> None:
    query = (
        "Generate SPL for failed logins by user in Windows Security logs for the last 24h."
    )
    response = chat(ChatRequest(message=query))
    cs = response.candidate_spl
    if cs is not None:
        assert cs.generation_mode != "t2_spl_native_review"
    combined = " ".join(
        [
            response.message or "",
            " ".join((response.analyst_response.analyst_checklist or []) if response.analyst_response else []),
        ]
    ).lower()
    for bad in ("scada_perf", "rtu_id", "cisco_asa", "power_sector_iocs.csv"):
        assert bad not in combined


def test_generic_main_index_neutral_checklist() -> None:
    query = "Generate review-only SPL to count events by host for index=main over the last 24h."
    response = chat(ChatRequest(message=query))
    combined = " ".join(
        [
            response.message or "",
            " ".join((response.analyst_response.analyst_checklist or []) if response.analyst_response else []),
        ]
    ).lower()
    for bad in ("scada_perf", "rtu_id", "cisco_asa", "power_sector_iocs", "mfa", "dns correlation"):
        assert bad not in combined
