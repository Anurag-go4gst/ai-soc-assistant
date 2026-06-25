"""Phase 13D-B — firewall draft SPL quality and analyst-facing display."""

from __future__ import annotations

import re

import pytest

from app.chat import pipeline as chat_pipeline
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest
from app.spl.draft_preview import build_draft_preview, match_detection_family

PG_FW_001 = "Search firewall logs for traffic from corporate IT to OT control room network."
PG_FW_002 = "What should SOC review if corporate IT traffic is allowed into an OT VLAN?"
PG_FW_003 = "Look for RDP traffic from corporate IT network to OT control room systems."
PG_FW_004 = "Search firewall logs for SMB traffic between OT network segments."
PG_FW_007 = "Find successful established connections from vendor VPN to OT jump server."
PG_FW_009 = "Search firewall logs for denied traffic from OT assets to the internet."

_FUZZY_SESSION = re.compile(
    r'like\s*\(\s*session_state_norm\s*,\s*["\']%[^"\']+%["\']\s*\)',
    re.IGNORECASE,
)
_AUTH_ANOMALY = re.compile(r"\b(authentication anomaly|auth anomaly)\b", re.IGNORECASE)
_CONSOLIDATED_WARNING = (
    "Lab-only draft SPL preview. Not governed, not approved, not executed. "
    "HIL/SOC review is required before any future execution path."
)


@pytest.fixture(autouse=True)
def _governance_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)


def _blocked_validation() -> dict:
    return {
        "approved": False,
        "normalized_spl": None,
        "reject_reasons": ["spl_template_missing"],
        "review_required_reason": "spl_template_missing",
        "spl_template_status": "unavailable",
    }


def _analyst_blob(response) -> str:
    analyst = response.analyst_response
    # COE renderer ownership: the lab-only / HIL warning is carried once in its owned
    # section (spl_draft_preview.warning), so include that section in the visible blob.
    preview = response.spl_draft_preview
    warning = ""
    if preview is not None:
        warning = str(getattr(preview, "warning", "") or "")
    parts = [
        response.message or "",
        analyst.direct_answer_summary if analyst else "",
        analyst.finding_title if analyst else "",
        analyst.scenario_label if analyst else "",
        analyst.review_notice if analyst else "",
        warning,
    ]
    return " ".join(p for p in parts if p)


@pytest.mark.parametrize(
    ("query", "family_id"),
    [
        (PG_FW_001, "esp_it_to_ot_connection"),
        (PG_FW_003, "firewall_it_ot_rdp"),
        (PG_FW_004, "firewall_ot_smb_lateral"),
        (PG_FW_007, "firewall_vendor_vpn_jump"),
        (PG_FW_009, "firewall_ot_egress_denied"),
    ],
)
def test_firewall_draft_spl_strict_session_and_field_split(query: str, family_id: str) -> None:
    assert match_detection_family(query) == family_id
    preview = build_draft_preview(query, spl_validation=_blocked_validation())
    assert preview is not None
    spl = preview["draft_spl"]
    assert not _FUZZY_SESSION.search(spl)
    assert preview["governed"] is False
    assert preview["execution_enabled"] is False
    assert preview["review_required"] is True
    log_fields = preview["required_log_fields"]
    profile_fields = preview["required_source_profile_fields"]
    assert "corporate_cidr" not in log_fields
    assert "ot_asset_cidr" not in log_fields
    if family_id == "esp_it_to_ot_connection":
        assert "corporate_cidr" in profile_fields
        assert "ot_asset_cidr" in profile_fields
        assert "corporate_it_cidr" not in profile_fields
        assert "ot_control_center_cidr" not in profile_fields
        assert 'session_state_norm IN ("established"' in spl
        assert "tcp_established" in spl


def test_denied_egress_draft_has_no_established_session_filter() -> None:
    preview = build_draft_preview(PG_FW_009, spl_validation=_blocked_validation())
    assert preview is not None
    spl = preview["draft_spl"]
    assert "session_state_norm IN" not in spl
    assert "action=denied" in spl.split("|")[0]


def test_general_traffic_draft_states_established_scope() -> None:
    preview = build_draft_preview(PG_FW_001, spl_validation=_blocked_validation())
    assert preview is not None
    assert preview.get("scope_notice")
    assert "allowed/established" in preview["scope_notice"].lower()


@pytest.mark.parametrize("query", [PG_FW_001, PG_FW_003, PG_FW_004, PG_FW_007, PG_FW_009])
def test_firewall_live_response_labels_and_single_warning(query: str) -> None:
    response = build_live_chat_response(ChatRequest(message=query))
    blob = _analyst_blob(response)
    assert not _AUTH_ANOMALY.search(blob), f"auth anomaly label in: {blob[:200]}"
    assert _CONSOLIDATED_WARNING.lower() in blob.lower()
    assert blob.lower().count("lab-only draft spl preview") == 1
    analyst = response.analyst_response
    assert analyst is not None
    assert analyst.hil_status == "required"
    checklist = analyst.analyst_checklist or []
    if query != PG_FW_009:
        assert any("firewall" in item.lower() or "ot" in item.lower() for item in checklist)


def test_pg_fw_002_draft_spl_has_no_fuzzy_session_when_shown() -> None:
    response = build_live_chat_response(ChatRequest(message=PG_FW_002))
    preview = response.spl_draft_preview
    draft_spl = getattr(preview, "draft_spl", None) if preview else None
    if draft_spl:
        assert not _FUZZY_SESSION.search(str(draft_spl))
