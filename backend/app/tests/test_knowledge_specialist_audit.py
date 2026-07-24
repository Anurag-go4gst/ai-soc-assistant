"""Deterministic Knowledge specialist audit — item 9 (re-scoped, no LLM).

Matrix contract: "intent says X, plan has Y → report Z". Covers domain
expectation, gap warnings, fill-blank proposals, merge integration through
``apply_specialist_reports``, and the thin reference-dispatch consumer.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.pipeline import (
    _knowledge_reference_domains,
    _reference_dataset_allowed,
    _resolve_reference_knowledge,
)
from app.graph.resource_planner_graph import rp_node_specialist_knowledge
from app.planner.knowledge_specialist import (
    KNOWLEDGE_ALIGNED,
    KNOWLEDGE_GAP,
    KNOWLEDGE_IDLE,
    build_knowledge_audit_report,
)
from app.planner.planner_hierarchy import (
    WorkBundle,
    apply_specialist_reports,
    validate_bundle_policy_parity,
    work_bundle_from_resource_plan,
)
from app.planner.resource_plan import PlanStep, ResourcePlan


def _evidence_plan_with_steps(steps: list[dict[str, Any]], **booleans: bool) -> dict[str, Any]:
    return {"resource_plan": {"steps": steps}, **booleans}


def _step(purpose: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "step_id": f"step:{purpose}",
        "resource_id": f"resource:{purpose}",
        "purpose": purpose,
        "args_template": dict(args or {}),
    }


# --- matrix: intent says X, plan has Y → report Z ---------------------------


def test_mitre_intent_with_mitre_step_fills_blank_reference_domains() -> None:
    report = build_knowledge_audit_report(
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan=_evidence_plan_with_steps([_step("mitre_mapping")]),
    )
    assert report.decision_reason == KNOWLEDGE_ALIGNED
    assert report.reference_domains == ["mitre"]
    assert not report.warnings
    assert [proposal.purpose for proposal in report.proposals] == ["mitre_mapping"]
    assert report.proposals[0].args_template == {"reference_domains": ["mitre"]}


def test_cve_intent_without_cve_step_reports_gap_and_no_proposal() -> None:
    report = build_knowledge_audit_report(
        intent_classification={"intent_family": "cve_investigation", "answer_goal": []},
        evidence_plan=_evidence_plan_with_steps([_step("mitre_mapping")]),
    )
    assert report.decision_reason == KNOWLEDGE_GAP
    assert "knowledge_gap:cve:no_plan_step" in report.warnings
    assert all(proposal.purpose != "cve_lookup" for proposal in report.proposals)


def test_reference_intent_with_retrieval_step_proposes_reference_lookup() -> None:
    report = build_knowledge_audit_report(
        intent_classification={"intent_family": "reference_knowledge", "answer_goal": ["reference_lookup"]},
        evidence_plan=_evidence_plan_with_steps([_step("knowledge_retrieval")]),
    )
    assert report.decision_reason == KNOWLEDGE_ALIGNED
    assert report.proposals[0].args_template == {"reference_domains": ["reference_lookup"]}


def test_no_knowledge_intent_and_no_knowledge_steps_is_idle() -> None:
    report = build_knowledge_audit_report(
        intent_classification={"intent_family": "live_investigation", "answer_goal": ["live_results"]},
        evidence_plan=_evidence_plan_with_steps([_step("spl_artifact")]),
    )
    assert report.decision_reason == KNOWLEDGE_IDLE
    assert report.reference_domains == []
    assert not report.proposals
    assert not report.warnings


def test_surplus_knowledge_step_without_intent_domain_warns() -> None:
    report = build_knowledge_audit_report(
        intent_classification={"intent_family": "live_investigation", "answer_goal": []},
        evidence_plan=_evidence_plan_with_steps([_step("knowledge_retrieval")]),
    )
    assert report.decision_reason == KNOWLEDGE_IDLE
    assert "knowledge_step_without_intent_domain:knowledge_retrieval" in report.warnings


def test_existing_reference_domains_args_are_not_reproposed() -> None:
    report = build_knowledge_audit_report(
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": []},
        evidence_plan=_evidence_plan_with_steps(
            [_step("mitre_mapping", {"reference_domains": ["mitre"]})]
        ),
    )
    assert report.decision_reason == KNOWLEDGE_ALIGNED
    assert not report.proposals


def test_evidence_plan_booleans_count_as_required_evidence() -> None:
    report = build_knowledge_audit_report(
        intent_classification={"intent_family": "live_investigation", "answer_goal": []},
        evidence_plan=_evidence_plan_with_steps([], needs_mitre=True, needs_rag=True),
    )
    assert report.decision_reason == KNOWLEDGE_GAP
    assert report.reference_domains == ["mitre", "rag"]
    assert {"knowledge_gap:mitre:no_plan_step", "knowledge_gap:rag:no_plan_step"} <= set(report.warnings)


def test_missing_intent_and_plan_degrade_to_idle() -> None:
    report = build_knowledge_audit_report(intent_classification=None, evidence_plan=None)
    assert report.decision_reason == KNOWLEDGE_IDLE
    assert report.specialist_id == "knowledge"


# --- merge integration: proposals stay in the owned lane --------------------


def test_merge_applies_knowledge_proposal_to_owned_task_only() -> None:
    plan = ResourcePlan(
        steps=[
            PlanStep(step_id="s1", resource_id="rag", purpose="knowledge_retrieval"),
            PlanStep(step_id="s2", resource_id="spl", purpose="spl_artifact", policy_checks=["hil"]),
        ]
    )
    bundle: WorkBundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:test")
    report = build_knowledge_audit_report(
        intent_classification={"intent_family": "policy_knowledge", "answer_goal": []},
        evidence_plan={"resource_plan": plan.model_dump()},
    )
    merged = apply_specialist_reports(bundle, [report])
    assert validate_bundle_policy_parity(merged) == []
    by_step = {task.step_id: task for task in merged.tasks}
    assert by_step["s1"].args_template["reference_domains"] == ["rag"]
    assert by_step["s1"].source_specialist == "knowledge"
    assert by_step["s2"].source_specialist is None
    assert "reference_domains" not in by_step["s2"].args_template
    assert merged.merge_decision_reason == "specialist_reports_merged"


def test_graph_node_emits_audit_report_from_state() -> None:
    state: dict[str, Any] = {
        "intent_classification": {"intent_family": "cve_investigation", "answer_goal": []},
        "evidence_plan": _evidence_plan_with_steps([_step("cve_lookup")]),
    }
    result = rp_node_specialist_knowledge(state)  # type: ignore[arg-type]
    reports = result["specialist_reports"]
    assert len(reports) == 1
    assert reports[0]["specialist_id"] == "knowledge"
    assert reports[0]["decision_reason"] == KNOWLEDGE_ALIGNED
    assert reports[0]["proposals"][0]["args_template"] == {"reference_domains": ["cve"]}


# --- thin consumer: reference dispatch scoping ------------------------------


def test_reference_dataset_scope_unrestricted_without_domains() -> None:
    assert _reference_dataset_allowed("mitre_atlas", None)
    assert _reference_dataset_allowed("mitre_atlas", [])
    assert _reference_dataset_allowed("cve", ["reference_lookup", "cve"])


def test_reference_dataset_scope_filters_unmerged_domains() -> None:
    assert _reference_dataset_allowed("cve", ["cve"])
    assert not _reference_dataset_allowed("mitre_atlas", ["cve"])
    assert not _reference_dataset_allowed("mitre_attack_enterprise", ["cve"])


def test_knowledge_reference_domains_read_from_validated_plan_args() -> None:
    evidence_plan = _evidence_plan_with_steps(
        [
            _step("knowledge_retrieval", {"reference_domains": ["rag", "reference_lookup"]}),
            _step("cve_lookup", {"reference_domains": ["cve"]}),
            _step("spl_artifact", {"reference_domains": ["ignored_not_knowledge"]}),
        ]
    )
    assert _knowledge_reference_domains(evidence_plan) == ["rag", "reference_lookup", "cve"]
    assert _knowledge_reference_domains(None) == []
    assert _knowledge_reference_domains({}) == []


def test_resolve_reference_knowledge_scopes_keyword_search(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.planner.reference_registry as reference_registry_module

    class _FakeResolver:
        def __init__(self, dataset_id: str) -> None:
            self.dataset_id = dataset_id

        def resolve_ids(self, ids: list[str]) -> list[Any]:
            return []

        def search_domain(self, keywords: list[str], *, limit: int = 10) -> list[Any]:
            return [
                reference_registry_module.ReferenceFact(
                    reference_id=f"{self.dataset_id}-hit",
                    dataset_id=self.dataset_id,
                )
            ]

    def _fake_registry() -> Any:
        return reference_registry_module.ReferenceRegistry(
            [
                reference_registry_module.ReferenceDataset(
                    dataset_id="cve",
                    id_patterns=(r"CVE-\d{4}-\d{4,7}",),
                    keyword_domains=("vulnerability",),
                    resolver=_FakeResolver("cve"),
                    provenance_tier="test",
                ),
                reference_registry_module.ReferenceDataset(
                    dataset_id="mitre_atlas",
                    id_patterns=(r"AML\.T\d{4}",),
                    keyword_domains=("vulnerability",),
                    resolver=_FakeResolver("mitre_atlas"),
                    provenance_tier="test",
                ),
            ]
        )

    monkeypatch.setattr(reference_registry_module, "load_reference_registry", _fake_registry)
    scoped = _resolve_reference_knowledge("vulnerability question", reference_domains=["cve"])
    scoped_datasets = {fact["dataset_id"] for fact in scoped["facts"]}
    assert scoped_datasets == {"cve"}

    unscoped = _resolve_reference_knowledge("vulnerability question")
    unscoped_datasets = {fact["dataset_id"] for fact in unscoped["facts"]}
    assert unscoped_datasets == {"cve", "mitre_atlas"}
