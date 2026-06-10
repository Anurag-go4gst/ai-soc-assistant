"""T0.2 — ResourcePlan contract: projections and EvidencePlan compatibility."""

from __future__ import annotations

from app.chat.contracts.evidence_plan import EvidencePlan
from app.planner.resource_plan import PlanStep, ResourcePlan, project_booleans


def _step(step_id: str, resource_id: str, purpose: str, **kwargs) -> PlanStep:
    return PlanStep(step_id=step_id, resource_id=resource_id, purpose=purpose, **kwargs)


def test_project_booleans_per_purpose() -> None:
    plan = ResourcePlan(
        steps=[
            _step("s1", "rag_corpus:soc_kb", "knowledge_retrieval"),
            _step("s2", "spl_template_family:auth_failed_login_spike", "spl_artifact"),
            _step("s3", "mcp_tool:splunk_run_query", "mcp_execution"),
            _step("s4", "skill:mitre_mapping", "mitre_mapping"),
            _step("s5", "llm_role:narration", "narration"),
        ]
    )
    assert project_booleans(plan) == {
        "needs_rag": True,
        "needs_spl": True,
        "needs_mcp": True,
        "needs_mitre": True,
    }


def test_project_booleans_empty_plan_all_false() -> None:
    assert project_booleans(ResourcePlan()) == {
        "needs_rag": False,
        "needs_spl": False,
        "needs_mcp": False,
        "needs_mitre": False,
    }


def test_unknown_purpose_projects_nothing() -> None:
    plan = ResourcePlan(steps=[_step("s1", "llm_role:judge", "quality_judgment")])
    assert not any(project_booleans(plan).values())


def test_evidence_plan_serialization_unchanged_without_resource_plan() -> None:
    plan = EvidencePlan(
        answer_mode="rag_only",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=True,
        policy_context_recommended=False,
    )
    dumped = plan.model_dump()
    assert dumped["resource_plan"] is None
    # Existing keys all still present (consumers read these by name).
    for key in (
        "answer_mode",
        "rag_phase",
        "needs_rag",
        "needs_spl",
        "needs_mcp",
        "needs_mitre",
        "spl_allowed",
        "mcp_allowed",
        "requires_hil",
        "reasons",
        "limitations",
    ):
        assert key in dumped


def test_evidence_plan_accepts_attached_resource_plan() -> None:
    resource_plan = ResourcePlan(
        steps=[_step("s1", "rag_corpus:soc_kb", "knowledge_retrieval")],
        plan_source="deterministic",
    )
    plan = EvidencePlan(
        answer_mode="rag_only",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=True,
        resource_plan=resource_plan.model_dump(),
    )
    assert plan.resource_plan["plan_source"] == "deterministic"
    assert plan.resource_plan["steps"][0]["resource_id"] == "rag_corpus:soc_kb"


def test_summary_exposes_ids_not_args() -> None:
    plan = ResourcePlan(
        steps=[
            _step("s1", "rag_corpus:soc_kb", "knowledge_retrieval", args_template={"q": "secret"})
        ]
    )
    summary = plan.summary()
    assert summary["steps"][0]["resource_id"] == "rag_corpus:soc_kb"
    assert "args_template" not in summary["steps"][0]
    assert "q" not in str(summary)
