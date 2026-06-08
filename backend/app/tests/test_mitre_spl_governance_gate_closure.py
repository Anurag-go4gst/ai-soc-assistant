from __future__ import annotations

from types import SimpleNamespace

from app.chat import pipeline as chat_pipeline
from app.chat.pipeline import _mitre_outputs_for_finalize
from app.config import settings
from app.threat.mitre_decision import resolve_mitre_decision
from app.threat.mitre_registry_enrichment import (
    registry_mitre_metadata,
    registry_mitre_metadata_for_runtime,
)


def _planning(*branches: str) -> dict:
    return {"branches": list(branches), "path_type": "hybrid_investigation"}


def test_mitre_branch_on_planner_omits_mitre_suppresses_evidence_supported(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)

    mappings, decision = _mitre_outputs_for_finalize(
        query="Map failed login attempts across 12 users to MITRE",
        question_ref=None,
        use_case_id="auth_failed_login_spike",
        source_refs=["src-1"],
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": False},
        planning_decision=_planning("spl"),
        query_signals={"failed_login": True, "spray_breadth": True},
        session_alert_context=True,
    )

    assert mappings == []
    assert decision is not None
    assert decision["mitre_status"] == "not_applicable"
    assert decision["answer_visible"] is False
    assert "evidence_supported" not in str(decision.get("evidence_statuses") or {}).lower()


def test_finalize_fallback_receives_planning_decision(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)

    seen: dict[str, object] = {}

    def _capture_branch(**kwargs):
        seen["planning_decision"] = kwargs.get("planning_decision")
        return [], None, SimpleNamespace(ran=False, status="not_applicable", reason="planner_did_not_select_mitre_branch")

    monkeypatch.setattr(chat_pipeline, "run_mitre_evidence_branch", _capture_branch)

    planning = _planning("spl")
    _mitre_outputs_for_finalize(
        query="Map failed logins to MITRE",
        question_ref=None,
        use_case_id="auth_failed_login_spike",
        source_refs=["src-1"],
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": False},
        planning_decision=planning,
        session_alert_context=True,
    )

    assert seen["planning_decision"] == planning


def test_phase6_on_activation_off_blocks_stub_spl(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", False)
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)

    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="spl_generation",
        user_query="write SPL for failed login spike",
        template_id=None,
        use_case_id="auth_failed_login_spike",
    )

    assert candidate is not None
    assert validation is not None
    assert candidate["generation_mode"] == "clarification_required"
    assert candidate["candidate_spl"] == ""
    assert validation["approved"] is False
    assert validation["execution_enabled"] is False
    assert candidate.get("generation_mode") != "saia_generate_spl"


def test_runtime_mitre_path_blocks_enrichment_only_metadata(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)

    legacy = registry_mitre_metadata(use_case_id="email_phishing_header_review")
    runtime = registry_mitre_metadata_for_runtime(use_case_id="email_phishing_header_review")

    assert legacy is not None
    assert legacy.mitre_candidate
    assert runtime is None

    decision = resolve_mitre_decision(
        use_case_id="email_phishing_header_review",
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": True},
        alert_context_present=True,
    )
    assert decision.answer_visible is False
    assert decision.mitre_status == "no_registry_mapping"


def test_finalize_spl_governance_uses_runtime_wrapper(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)

    governance = chat_pipeline._runtime_spl_governance("auth_failed_login_spike")

    assert governance is not None
    assert governance.get("governed_enrichment_load_allowed") is True
    assert governance.get("allowed_spl_templates") == ["auth_failed_login_spike"]


def test_legacy_paths_remain_when_new_flags_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", False)
    monkeypatch.setattr(settings, "control_plane_enabled", False)

    mappings, decision = _mitre_outputs_for_finalize(
        query="policy",
        question_ref="q0.q046",
        use_case_id="auth_failed_login_spike",
        source_refs=["legacy"],
        intent_classification={"intent_family": "policy_knowledge", "answer_goal": []},
        evidence_plan={"answer_mode": "rag_only"},
    )

    assert decision is None
    assert mappings
    assert chat_pipeline._runtime_spl_governance("auth_failed_login_spike") is not None
