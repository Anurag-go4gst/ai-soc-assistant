from __future__ import annotations

from app.chat import pipeline as chat_pipeline
from app.config import settings
from app.safeguards.spl_validator import validate_spl
from app.spl.generator import CandidateSpl
from app.splunk.spl_services import merge_post_validation_optimization, optimize_spl


def test_optimizer_uses_revalidation_approved_not_execution_eligible() -> None:
    result = optimize_spl("search index=pgcil_soc sourcetype=pgcil:auth | sort - count")

    assert "execution_eligible" not in result
    assert "revalidation_approved" in result
    assert isinstance(result["revalidation_approved"], bool)


def test_merge_post_validation_optimization_replaces_candidate_when_revalidated() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth action=failure earliest=-60m latest=now "
        "| table user | stats count by user | sort -count | head 100"
    )
    validation = validate_spl(spl)
    final_spl, final_validation, optimization = merge_post_validation_optimization(spl, validation)

    assert optimization["optimization_applied"] is True
    assert optimization["revalidation_approved"] is True
    assert final_spl != spl
    assert final_validation["approved"] is True
    assert final_validation["normalized_spl"] == final_spl


def test_template_pipeline_returns_optimized_candidate_and_normalized_spl(monkeypatch) -> None:
    optimized = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
        "action=failure | stats count by user | sort -count | head 100"
    )
    optimized_validation = validate_spl(optimized)

    def _merge(*args, **kwargs):
        return optimized, optimized_validation, {
            "provider": "rule_based",
            "optimization_applied": True,
            "revalidation_status": optimized_validation,
            "revalidation_approved": True,
        }

    monkeypatch.setattr(chat_pipeline, "merge_post_validation_optimization", _merge)
    candidate, validation = chat_pipeline._candidate_from_default_template(
        trace_id="optimized-template",
        skill="spl_generation",
        user_query="failed login spike by user",
        template_id="auth_failed_login_spike",
    )

    assert candidate["candidate_spl"] == optimized
    assert validation["normalized_spl"] == optimized
    assert validation["optimization_applied"] is True


def test_provider_pipeline_returns_optimized_candidate_and_normalized_spl(monkeypatch) -> None:
    original = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
        "action=failure | table user | stats count by user | sort -count | head 100"
    )
    optimized = original.replace(" | table user", "")
    optimized_validation = validate_spl(optimized)
    candidate_model = CandidateSpl(
        trace_id="optimized-provider",
        skill="spl_generation",
        user_query="failed login spike by user",
        candidate_spl=original,
        generation_mode="stub",
        confidence=0.8,
    )

    monkeypatch.setattr(settings, "control_plane_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", False)
    monkeypatch.setattr(chat_pipeline, "_runtime_spl_governance", lambda _use_case_id: None)
    monkeypatch.setattr(chat_pipeline, "_should_use_llm_spl_failover", lambda _skill, **_: False)
    monkeypatch.setattr(
        chat_pipeline,
        "generate_candidate_spl_with_provider",
        lambda **kwargs: (
            candidate_model,
            {
                "selected_candidate_spl_provider": "template",
                "reason": "test",
                "saia_available": False,
                "fallback_required": True,
            },
        ),
    )
    monkeypatch.setattr(
        chat_pipeline,
        "merge_post_validation_optimization",
        lambda *args, **kwargs: (
            optimized,
            optimized_validation,
            {
                "provider": "rule_based",
                "optimization_applied": True,
                "revalidation_status": optimized_validation,
                "revalidation_approved": True,
            },
        ),
    )

    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="optimized-provider",
        skill="spl_generation",
        user_query="failed login spike by user",
        template_id=None,
        use_case_id=None,
    )

    assert candidate["candidate_spl"] == optimized
    assert validation["normalized_spl"] == optimized
    assert validation["optimization_applied"] is True
