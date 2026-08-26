from __future__ import annotations

import json
from pathlib import Path

from app.api.routes_chat import chat
from app.chat.planning_decision import plan_path_and_tools
from app.schemas.requests import ChatRequest
from app.use_cases.content_enrichment import (
    enrichment_spl_governance,
    llm_facing_curated_enrichment_projection,
    load_curated_enrichment_context,
    resolve_use_case_activation,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CROSSWALK_PATH = REPO_ROOT / "docs" / "evals" / "soc_capability_crosswalk.json"
RETIRED_FACTORY_PATHS = [
    REPO_ROOT / "docs" / "skills" / "github_skill_discovery_index.json",
    REPO_ROOT / "docs" / "skills" / "github_skill_triage_scores.json",
    REPO_ROOT / "docs" / "skills" / "proposed_use_cases_from_github.json",
    REPO_ROOT / "docs" / "skills" / "skill_enrichment_status_matrix.json",
    REPO_ROOT / "docs" / "skills" / "pending_skill_enrichment_backlog.json",
]


def test_runtime_active_catalog_enrichment_loads_curated_context() -> None:
    context = load_curated_enrichment_context("auth_failed_login_spike")

    assert context is not None
    assert context.use_case_id == "auth_failed_login_spike"
    assert context.runtime_support_status == "runtime_active"
    assert context.activation_lifecycle_stage == "runtime_active"
    assert context.activation_decision.planner_runtime_activation_allowed is True
    assert context.evidence_requirements
    assert context.investigation_workflow
    assert context.analyst_checklist
    assert context.answer_rules
    assert context.limitations
    assert context.not_claimed_defaults
    assert context.required_sources
    assert context.optional_sources
    assert context.allowed_spl_templates == ["auth_failed_login_spike"]
    assert context.spl_template_status == "active"
    assert context.rag_doc_ids == ["auth_sop"]
    assert "T1110.001" in context.mitre_candidates
    assert context.planning_or_analytic_skill == "threshold_anomaly"
    assert context.provenance_ref_ids


def test_catalog_present_planned_use_case_trace_only_not_runtime_active() -> None:
    activation = resolve_use_case_activation("soc_show_sop")

    assert activation.catalog_present is True
    assert activation.runtime_support_status == "planned"
    assert activation.planner_runtime_activation_allowed is False
    assert activation.governed_enrichment_load_allowed is False
    assert activation.trace_metadata_allowed is True
    assert activation.activation_lifecycle_stage == "planned_trace_metadata"
    assert load_curated_enrichment_context("soc_show_sop") is None


def test_enrichment_only_pilot_does_not_runtime_activate() -> None:
    activation = resolve_use_case_activation("soc_incident_triage")

    assert activation.catalog_present is False
    assert activation.enrichment_present is True
    assert activation.enrichment_only is True
    assert activation.proposed_github_use_case is True
    assert activation.planner_runtime_activation_allowed is False
    assert activation.governed_enrichment_load_allowed is False
    assert activation.activation_lifecycle_stage == "enrichment_only"


def test_github_accepted_skill_is_not_treated_as_runtime_skill() -> None:
    activation = resolve_use_case_activation("edr_powershell_suspicious_command")

    assert activation.github_accepted_for_enrichment_only is True
    assert activation.github_lifecycle_status == "accepted_for_enrichment"
    assert "github_skill_acceptance_is_enrichment_only" in activation.reasons
    assert activation.live_execution_skill_allowed is True
    assert activation.planner_runtime_activation_allowed is True


def test_proposed_github_use_case_is_not_runtime_active() -> None:
    activation = resolve_use_case_activation("email_phishing_header_review")

    assert activation.proposed_github_use_case is True
    assert activation.runtime_support_status == "metadata_only"
    assert activation.planner_runtime_activation_allowed is False
    assert activation.governed_enrichment_load_allowed is False
    assert "github_proposed_use_case_never_runtime_active_phase4" in activation.reasons


def test_metadata_only_planned_crosswalk_row_does_not_set_planner_runtime_activation(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_planner_path_selection_enabled", True)
    planning = plan_path_and_tools(
        intent_classification={"intent_family": "spl_generation_only", "requires_clarification": False},
        evidence_plan={"needs_spl": True, "needs_mcp": False, "reasons": ["phase4"]},
        routed={"skill": "attack_discovery", "tool_plan": ["generate_spl", "validate_spl"]},
        query_understanding=type(
            "QU",
            (),
            {
                "mapped_use_case_ids": ["email_phishing_header_review"],
                "mapped_question_ref": None,
                "mapped_operation_type": "phishing_triage",
            },
        )(),
    )

    assert planning.runtime_support_status == "metadata_only"
    assert planning.activation_lifecycle_stage == "enrichment_only"
    assert planning.planner_runtime_activation_allowed is False
    assert planning.activation_decision is not None
    assert planning.activation_decision["planner_runtime_activation_allowed"] is False


def test_raw_github_skill_markdown_paths_are_not_projected_to_llm_payload() -> None:
    context = load_curated_enrichment_context("auth_failed_login_spike")
    projection = llm_facing_curated_enrichment_projection(context)

    assert projection is not None
    serialized = json.dumps(projection)
    assert "SKILL.md" not in serialized
    assert "skills/" not in serialized
    assert "github_ref:" not in serialized
    assert "provenance_ref_ids" not in projection
    assert "mitre_candidates_metadata_only" in projection


def test_enrichment_spl_governance_remains_backward_compatible() -> None:
    governance = enrichment_spl_governance("auth_failed_login_spike")

    assert governance is not None
    assert governance["use_case_id"] == "auth_failed_login_spike"
    assert governance["use_case_status"] == "active"
    assert governance["spl_template_status"] == "active"
    assert governance["allowed_spl_templates"] == ["auth_failed_login_spike"]
    assert governance["evidence_requirements"]
    assert governance["limitations"]
    assert governance["governed_limitation"] is None
    assert governance["llm_fallback_allowed"] is False
    assert governance["activation"]["planner_runtime_activation_allowed"] is True


def test_canonical_runtime_surfaces_planning_trace(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.langgraph_orchestration_enabled", False)
    monkeypatch.setattr("app.config.settings.ai_soc_planner_path_selection_enabled", False)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_intent_advisor_enabled", False)

    response = chat(ChatRequest(message="What is the escalation policy for repeated failed login alerts?"))

    assert response.control_plane_trace is not None
    assert response.planning_decision is not None
    assert response.planning_decision["execution_enabled"] is False


def test_knowledge_crosswalk_retired_factory_artifacts_removed() -> None:
    crosswalk = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))

    assert crosswalk["use_case_rows"]
    assert "github_skill_rows" not in crosswalk
    assert "proposed_use_case_rows" not in crosswalk
    assert "factory_visibility" not in crosswalk
    assert all(not path.exists() for path in RETIRED_FACTORY_PATHS)
