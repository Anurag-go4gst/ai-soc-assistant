"""Focused skill-bucket probes: CVE, MITRE threshold, cross-skill."""

from __future__ import annotations

import pytest

from app.chat.guidance_templates import build_cve_investigation_guidance, is_mitre_evidence_threshold_query
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import build_live_chat_response
from app.chat.query_signals import is_cve_focus_query, is_cross_skill_investigation_query
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest
from app.tests.support.chat_visible import visible_chat_prose

CVE_QUERY = (
    "CVE focus: CISA advisory flags CVE-2024-6387 in OpenSSH. What can we confirm from "
    "current logs without live scanning, and what evidence is missing?"
)
MITRE_QUERY = (
    "MITRE focus: map suspicious OT remote command sequence to ATT&CK for ICS with status "
    "labels (confirmed/candidate/not-claimed) and explain evidence thresholds."
)
@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)


CROSS_SKILL_QUERY = (
    "Cross-skill check: combine CVE context, MITRE candidate mapping, and GitHub commit "
    "timeline into one review-only investigation plan."
)


def test_cve_focus_detected_not_recon_scan() -> None:
    assert is_cve_focus_query(CVE_QUERY) is True
    from app.chat.signal_class_guidance import classify_signal_class

    assert classify_signal_class(CVE_QUERY) != "recon_scan"


def test_mitre_focus_threshold_signal() -> None:
    assert is_mitre_evidence_threshold_query(MITRE_QUERY) is True


def test_cross_skill_intent() -> None:
    assert is_cross_skill_investigation_query(CROSS_SKILL_QUERY) is True
    qti = build_query_to_intent(query=CROSS_SKILL_QUERY, query_understanding=understand_query(CROSS_SKILL_QUERY))
    assert qti.intent_classification.primary_intent == "cross_skill_investigation"


def test_cve_live_pipeline_has_vulnerability_source_and_substance() -> None:
    response = build_live_chat_response(ChatRequest(message=CVE_QUERY))
    blob = (response.message or "") + (response.analyst_response.direct_answer_summary or "")
    assert "cve-2024-6387" in blob.lower()
    assert len(blob) >= 180
    assert any(
        (item.model_dump() if hasattr(item, "model_dump") else item).get("source_name")
        == "vulnerability_source"
        for item in (response.source_evidence or [])
    )


def test_mitre_threshold_live_not_clarification_stub() -> None:
    response = build_live_chat_response(ChatRequest(message=MITRE_QUERY))
    msg = response.message or ""
    assert "need alert context" not in msg.lower()
    ar = response.analyst_response
    assert ar is not None
    # COE renderer ownership collapses the markdown fallback once the card owns the
    # checklist; assert substance on the combined visible answer, not the message alone.
    blob = msg + (ar.direct_answer_summary or "")
    assert len(blob) >= 180
    assert ar.recommended_actions
    assert ar.mitre_mappings


def test_cross_skill_live_has_three_legs() -> None:
    response = build_live_chat_response(ChatRequest(message=CROSS_SKILL_QUERY))
    blob = visible_chat_prose(response).lower()
    assert "github" in blob
    assert "cve" in blob or "token" in blob
    assert "mitre" in blob or "checklist" in blob
    assert len(blob) >= 180
    assert response.analyst_response is not None
    assert response.analyst_response.mitre_mappings
