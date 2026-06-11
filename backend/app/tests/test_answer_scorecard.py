"""T3.1 — deterministic answer scorecard (read-model, never authority)."""

from __future__ import annotations

import uuid
from typing import Any

from app.api.routes_chat import chat
from app.evals.golden_answer_runner import _model_to_dict
from app.evals.sentinel_eval import sentinel_runtime
from app.quality.answer_scorecard import build_answer_scorecard
from app.schemas.requests import ChatRequest


def _base_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "message": "Review-only investigation prepared.",
        "severity_decision": {"severity_label": "P3 Medium"},
        "candidate_spl": {"candidate_spl": "search index=x", "execution_eligible": False},
        "execution": {"status": "skipped"},
        "human_review": {"required": False},
        "evidence_plan": {"answer_mode": "live_investigation", "needs_spl": True},
        "spl_template_status": "active",
        "query_to_intent": {
            "candidate_mappings": {"match_path": "use_case_catalog"},
            "intent_classification": {"intent_family": "hybrid_alert_review"},
        },
        "answer_contract": {
            "mitre_technique_ids": [],
            "candidate_mitre": [],
            "evidence_supported_mitre": [],
            "render_sections": {},
            "human_review_required": False,
        },
        "mitre_mappings": [],
        "analyst_response": {
            "render_sections": {},
            "recommended_actions": ["P2 — Correlate failures for the user."],
            "limitations": ["Telemetry alone does not establish validity."],
            "execution_status_label": "Review only — not executed",
            "spl_status": "validated_not_executed",
            "hil_status": "not_required",
            "spl_draft_preview": {},
        },
    }
    base.update(overrides)
    return base


def _live(question: str) -> dict[str, Any]:
    with sentinel_runtime():
        payload = _model_to_dict(chat(ChatRequest(message=question, session_id=f"sc-{uuid.uuid4()}")))
    return payload


def test_answer_scorecard_flags_missing_guidance() -> None:
    payload = _base_payload()
    payload["analyst_response"] = {"render_sections": {}, "spl_draft_preview": {}, "spl_status": "validated_not_executed", "hil_status": "not_required"}
    card = build_answer_scorecard(payload)
    assert card["checks"]["analyst_guidance_present"] is False
    assert card["verdict"] == "review"
    assert any("analyst_guidance_present" in reason for reason in card["reasons"])


def test_answer_scorecard_passes_skill_checklist_answer() -> None:
    payload = _live("Which hosts ran suspicious PowerShell?")
    card = payload.get("answer_scorecard") or {}
    assert card.get("verdict") == "pass", card.get("reasons")
    assert card["checks"]["skill_sections_present"] is True
    assert card["checks"]["analyst_guidance_present"] is True


def test_answer_scorecard_flags_unsupported_execution_claim() -> None:
    payload = _base_payload()
    payload["analyst_response"]["evidence_summary"] = "The SPL was executed in Splunk."
    card = build_answer_scorecard(payload)
    assert card["checks"]["no_unsupported_claims"] is False
    assert card["verdict"] == "review"


def test_answer_scorecard_flags_mitre_overclaim() -> None:
    payload = _base_payload()
    payload["analyst_response"]["mitre_status_summary"] = "Confirmed as T1566.001."
    card = build_answer_scorecard(payload)
    assert card["checks"]["mitre_wording_safe"] is False


def test_answer_scorecard_marks_analytics_severity_not_assigned_as_valid() -> None:
    payload = _live("Which hosts are generating the most SMB traffic?")
    card = payload.get("answer_scorecard") or {}
    assert card["checks"]["severity_state_clear"] is True
    assert "Not assigned" in str(payload.get("severity_decision", {}).get("severity_label"))


def test_answer_scorecard_accepts_draft_spl_review_only_answer() -> None:
    payload = _live("Which systems generated large outbound data transfers?")
    card = payload.get("answer_scorecard") or {}
    assert card["checks"]["spl_status_clear"] is True
    assert card["checks"]["execution_status_clear"] is True
    assert card["checks"]["no_unsupported_claims"] is True
