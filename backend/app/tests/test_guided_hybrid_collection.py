"""REV4 batch 2 P12 — guided hybrid evidence collection."""

from __future__ import annotations

from app.spl.guided_safe_spl_catalog import (
    GuidedSafeSplCatalog,
    GuidedSafeSplCatalogEntry,
)
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guided_capability_validator import validate_guided_resource_plan
from app.chat.guided_hybrid_collection import collect_guided_hybrid_evidence
from app.planner.composer import compose_guided_resource_plan


def _hybrid_evidence() -> EvidencePlan:
    return EvidencePlan(
        answer_mode="guided_investigation",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=True,
        discovery_allowed=True,
        investigation_planning_enabled=True,
        spl_review_allowed=False,
        safe_spl_execution_allowed=True,
        freeform_spl_execution_allowed=False,
        mcp_action_allowed=False,
    )


def test_collect_guided_hybrid_records_planned_discovery_and_catalog_hops() -> None:
    evidence = _hybrid_evidence()
    investigation = InvestigationPlan(
        investigation_objective="OT outbound hunt",
        hypotheses=["Beaconing"],
        evidence_needed=["DNS and firewall context"],
        read_only_tool_requests=["mcp_tool:splunk_get_metadata"],
        safe_spl_template_requests=["dns_beaconing_candidate"],
    )
    plan = compose_guided_resource_plan(evidence, investigation)
    validated = validate_guided_resource_plan(evidence, plan).validated_resource_plan
    state, collected_count = collect_guided_hybrid_evidence({}, validated_resource=validated)
    assert collected_count == 0
    hops = state.get("mcp_evidence") or []
    assert len(hops) == 2
    tools = {hop.get("tool") for hop in hops}
    assert "splunk_get_metadata" in tools
    assert "guided_safe_catalog" in tools
    assert all(hop.get("outcome") == "planned" for hop in hops)
    assert all(hop.get("tool") != "splunk_run_query" for hop in hops)
    catalog_hop = next(hop for hop in hops if hop.get("tool") == "guided_safe_catalog")
    assert catalog_hop["payload"]["coe_signed"] is False
    assert catalog_hop["payload"]["block_reason"] == "guided_safe_catalog_unsigned"


def test_signed_catalog_safe_query_reaches_mediated_execution(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.spl.guided_safe_spl_dispatch.load_guided_safe_spl_catalog",
        lambda: GuidedSafeSplCatalog(
            coe_signed=True,
            entries=[GuidedSafeSplCatalogEntry(template_id="dns_beaconing_candidate")],
        ),
    )
    evidence = _hybrid_evidence()
    investigation = InvestigationPlan(
        investigation_objective="OT outbound hunt",
        hypotheses=["Beaconing"],
        evidence_needed=["DNS context"],
        safe_spl_template_requests=["dns_beaconing_candidate"],
    )
    plan = compose_guided_resource_plan(evidence, investigation)
    validated = validate_guided_resource_plan(evidence, plan).validated_resource_plan
    calls: list[dict] = []

    def _fake_execution(spl_validation: dict) -> tuple[dict, dict]:
        calls.append(spl_validation)
        return (
            {
                "status": "requires_human_review",
                "tool_selection_status": "selected",
                "tool_selection_reason": "deterministic_safe_tool_selected",
                "block_reason": "analyst_confirmation_required",
            },
            {"required": True, "reason": "analyst_confirmation_required"},
        )

    state, collected_count = collect_guided_hybrid_evidence(
        {},
        validated_resource=validated,
        execute_safe_catalog_spl=_fake_execution,
    )

    assert collected_count == 0
    assert len(calls) == 1
    assert calls[0]["approved"] is True
    assert calls[0]["normalized_spl"]
    hop = (state.get("mcp_evidence") or [])[0]
    assert hop["outcome"] == "requires_human_review"
    assert hop["payload"]["coe_signed"] is True
    assert hop["payload"]["human_review_required"] is True
    assert hop["payload"]["human_review_reason"] == "analyst_confirmation_required"


def test_signed_catalog_validation_failure_blocks_before_execution(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.spl.guided_safe_spl_dispatch.load_guided_safe_spl_catalog",
        lambda: GuidedSafeSplCatalog(
            coe_signed=True,
            entries=[GuidedSafeSplCatalogEntry(template_id="dns_beaconing_candidate")],
        ),
    )
    template = __import__(
        "app.spl.guided_safe_spl_dispatch",
        fromlist=["get_spl_template"],
    ).get_spl_template("dns_beaconing_candidate")
    monkeypatch.setattr(
        "app.spl.guided_safe_spl_dispatch.get_spl_template",
        lambda _template_id: template.model_copy(update={"spl_text": "search index=* | delete"}),
    )
    evidence = _hybrid_evidence()
    investigation = InvestigationPlan(
        investigation_objective="OT outbound hunt",
        safe_spl_template_requests=["dns_beaconing_candidate"],
    )
    validated = validate_guided_resource_plan(
        evidence,
        compose_guided_resource_plan(evidence, investigation),
    ).validated_resource_plan

    state, _ = collect_guided_hybrid_evidence(
        {},
        validated_resource=validated,
        execute_safe_catalog_spl=lambda _validation: (_ for _ in ()).throw(AssertionError("must not execute")),
    )

    hop = (state.get("mcp_evidence") or [])[0]
    assert hop["outcome"] == "blocked"
    assert hop["payload"]["block_reason"] == "guided_safe_template_validation_failed"


def test_signed_catalog_without_execution_callback_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.spl.guided_safe_spl_dispatch.load_guided_safe_spl_catalog",
        lambda: GuidedSafeSplCatalog(
            coe_signed=True,
            entries=[GuidedSafeSplCatalogEntry(template_id="dns_beaconing_candidate")],
        ),
    )
    evidence = _hybrid_evidence()
    investigation = InvestigationPlan(
        investigation_objective="OT outbound hunt",
        safe_spl_template_requests=["dns_beaconing_candidate"],
    )
    validated = validate_guided_resource_plan(
        evidence,
        compose_guided_resource_plan(evidence, investigation),
    ).validated_resource_plan

    state, _ = collect_guided_hybrid_evidence({}, validated_resource=validated)

    hop = (state.get("mcp_evidence") or [])[0]
    assert hop["outcome"] == "blocked"
    assert hop["payload"]["block_reason"] == "guided_safe_execution_callback_unavailable"


def test_guided_hybrid_stale_uncertain_step_requires_reconciliation_without_execution(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    from app.chat import canonical_execution_idempotency as store
    from app.chat.canonical_execution_idempotency import acquire_execution_step, build_idempotency_key

    monkeypatch.setattr(
        "app.spl.guided_safe_spl_dispatch.load_guided_safe_spl_catalog",
        lambda: GuidedSafeSplCatalog(
            coe_signed=True,
            entries=[GuidedSafeSplCatalogEntry(template_id="dns_beaconing_candidate")],
        ),
    )
    monkeypatch.setattr(
        "app.chat.guided_hybrid_collection.operation_contract_for_step",
        lambda _step: "side_effecting_without_stable_idempotency",
    )
    evidence = _hybrid_evidence()
    investigation = InvestigationPlan(
        investigation_objective="OT outbound hunt",
        safe_spl_template_requests=["dns_beaconing_candidate"],
    )
    validated = validate_guided_resource_plan(
        evidence,
        compose_guided_resource_plan(evidence, investigation),
    ).validated_resource_plan.model_copy(
        update={"provenance": {"resource_plan_id": "rp:guided", "handoff_id": "h-guided", "handoff_version": 1}}
    )
    step = next(item for item in validated.steps if item.purpose == "safe_catalog_query")
    params = {
        "resource_plan_id": "rp:guided",
        "handoff_id": "h-guided",
        "handoff_version": 1,
        "step_id": step.step_id,
        "operation": f"{step.purpose}:{step.resource_id}",
    }
    acquire_execution_step(
        **params,
        lease_owner="worker-a",
        side_effecting=True,
        operation_contract="side_effecting_without_stable_idempotency",
    )
    key = build_idempotency_key(**params)
    stale = store._TEST_STORE[key]
    stale["lease_expires_at"] = datetime.now(UTC) - timedelta(seconds=5)
    store._TEST_STORE[key] = stale
    calls = {"count": 0}

    state, collected_count = collect_guided_hybrid_evidence(
        {"trace_id": "t-guided"},
        validated_resource=validated,
        execute_safe_catalog_spl=lambda _validation: calls.__setitem__("count", calls["count"] + 1) or ({}, {}),
    )

    assert collected_count == 0
    assert calls["count"] == 0
    assert state["execution_reconciliation"]["reason"] == "execution_outcome_uncertain"
    assert state["human_review"]["reason"] == "execution_outcome_uncertain"
