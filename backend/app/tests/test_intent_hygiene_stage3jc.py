from __future__ import annotations

from app.api.routes_chat import chat
from app.routing.deterministic_router import route_skill_deterministic
from app.schemas.requests import ChatRequest
from app.spl.generator import generate_candidate_spl


def test_sop_prompt_routes_to_knowledge_recall_not_attack_discovery() -> None:
    for prompt in (
        "Show SOP for brute-force investigation",
        "Show SOP for failed login investigation",
        "What is the playbook for brute force?",
    ):
        routed = route_skill_deterministic(prompt)
        assert routed["skill"] == "knowledge_recall", prompt

    response = chat(ChatRequest(message="Show SOP for brute-force investigation"))
    assert response.selected_skill == "knowledge_recall"
    # SOP guidance must not generate or validate SPL.
    assert response.candidate_spl is None
    assert response.spl_validation is None


def test_successful_login_after_failures_generates_correlation_spl() -> None:
    candidate = generate_candidate_spl(
        trace_id="t-3jc",
        skill="spl_generation",
        user_query="Generate SPL for successful login after failures",
    )
    spl = candidate.candidate_spl
    # Must correlate failure AND success, not a failed-login spike only.
    assert 'action="failure"' in spl
    assert 'action="success"' in spl
    assert "success_count" in spl


def test_successful_login_after_failures_not_failed_spike_only() -> None:
    candidate = generate_candidate_spl(
        trace_id="t-3jc",
        skill="spl_generation",
        user_query="successful login after failures",
    )
    failed_spike_only = candidate.candidate_spl.strip().endswith(
        "action=failure | stats count as fail_count by user | where fail_count > 50 | sort -fail_count | head 100"
    )
    assert not failed_spike_only
    assert "success_count" in candidate.candidate_spl


def test_mitre_prompt_without_alert_context_returns_clarification() -> None:
    response = chat(ChatRequest(message="Map this alert to MITRE"))
    # No SPL generated for a bare mapping request.
    assert response.candidate_spl is None
    assert response.spl_validation is None
    # Clarification surfaced through the existing human-review envelope.
    assert response.human_review is not None
    assert response.human_review.review_type == "intent_clarification"
    assert response.human_review.reason == "mitre_mapping_requires_alert_context"
    # Evidence package is genuinely insufficient (nothing collected yet).
    assert response.context_sufficiency is not None
    assert response.context_sufficiency.status == "insufficient_evidence"
    assert response.context_sufficiency.synthesis_allowed is False


def test_mitre_prompt_with_alert_context_does_not_force_clarification() -> None:
    response = chat(
        ChatRequest(message="Map this alert to MITRE: notable signature=brute_force index=pgcil_soc sourcetype=pgcil:auth")
    )
    # With context markers present the clarification heuristic must not fire.
    assert not (response.human_review and response.human_review.review_type == "intent_clarification")
