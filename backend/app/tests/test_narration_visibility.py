"""T3.2 — narration/LLM usage visibility (read-model, never authority)."""

from __future__ import annotations

import uuid
from typing import Any

from app.api.routes_chat import chat
from app.evals.golden_answer_runner import _model_to_dict
from app.evals.sentinel_eval import sentinel_runtime
from app.schemas.requests import ChatRequest
from app.synthesis.narration_visibility import build_narration_visibility

_AUTHORITY_FIELDS = (
    "severity_label",
    "intent_family",
    "answer_mode",
    "human_review_required",
    "execution_eligible",
    "mitre_technique_ids",
)


def _live(question: str) -> dict[str, Any]:
    with sentinel_runtime():
        return _model_to_dict(
            chat(ChatRequest(message=question, session_id=f"nv-{uuid.uuid4()}"))
        )


def test_llm_skipped_still_returns_governed_deterministic_answer() -> None:
    # Pinned runtime keeps live synthesis off → composer never used.
    payload = _live("Which hosts ran suspicious PowerShell?")
    visibility = payload.get("narration_visibility") or {}
    assert visibility.get("composer_used") is False
    assert visibility.get("final_answer_source") == "deterministic_contract"
    contract = payload.get("answer_contract") or {}
    assert contract.get("analyst_checklist_safe")
    card = payload.get("answer_scorecard") or {}
    assert card.get("verdict") == "pass"
    assert (card.get("narration") or {}).get("final_answer_source") == "deterministic_contract"


def test_guard_blocked_llm_does_not_remove_answer() -> None:
    visibility = build_narration_visibility(
        {
            "llm_composer": {
                "composer_is_enabled": True,
                "llm_composer_used": False,
                "llm_guard_status": "blocked",
                "llm_fallback_used": True,
                "llm_blocked_reason": "guard rejected unsupported claim",
            }
        }
    )
    assert visibility["guard_blocked"] is True
    assert visibility["fallback_used"] is True
    assert visibility["final_answer_source"] == "deterministic_contract"
    assert visibility["skip_category"] == "compose_validation_blocked"


def test_timeout_fallback_is_visible() -> None:
    visibility = build_narration_visibility(
        {
            "llm_composer": {
                "composer_is_enabled": True,
                "llm_composer_used": False,
                "llm_fallback_used": True,
                "llm_blocked_reason": "llm call timed out after 120s",
            }
        }
    )
    assert visibility["timeout_or_degraded"] is True
    assert visibility["skip_category"] == "timeout_degraded"
    assert visibility["fallback_used"] is True


def test_llm_usage_cannot_change_authority_fields() -> None:
    """Same question, composer-used trace vs not — authority fields identical
    because visibility is computed FROM the answer, never into it."""
    payload = _live("Which hosts are generating the most SMB traffic?")
    contract = payload.get("answer_contract") or {}
    severity = payload.get("severity_decision") or {}
    before = {
        "severity": severity.get("severity_label"),
        "hil": contract.get("human_review_required"),
        "exec": (payload.get("candidate_spl") or {}).get("execution_eligible"),
        "mitre": sorted(contract.get("mitre_technique_ids") or []),
    }
    # Rebuilding visibility (even with a forged composer-used trace) only
    # changes the read-model, not the answer payload.
    forged = dict(payload)
    forged["llm_composer"] = {"composer_is_enabled": True, "llm_composer_used": True}
    visibility = build_narration_visibility(forged)
    assert visibility["final_answer_source"] == "llm_narration"
    after = {
        "severity": (payload.get("severity_decision") or {}).get("severity_label"),
        "hil": (payload.get("answer_contract") or {}).get("human_review_required"),
        "exec": (payload.get("candidate_spl") or {}).get("execution_eligible"),
        "mitre": sorted((payload.get("answer_contract") or {}).get("mitre_technique_ids") or []),
    }
    assert before == after


def test_live_packaging_status_shows_fallback_clearly() -> None:
    payload = _live("Which accounts had a successful login after repeated failures?")
    visibility = payload.get("narration_visibility") or {}
    # Pinned posture: provider not invoked — the answer must say so honestly.
    assert visibility.get("final_answer_source") == "deterministic_contract"
    assert visibility.get("skip_category") is not None
    assert payload.get("synthesis_status") is not None
