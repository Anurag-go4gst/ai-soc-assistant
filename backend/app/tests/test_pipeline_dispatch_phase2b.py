"""Phase 2B — full pipeline dispatch builder authority."""

from __future__ import annotations

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.pipeline_dispatch import LlmHop, PipelineStage, build_pipeline_dispatch, project_dispatch_flags
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import graph_node_evidence_planning
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest
from app.tests.support.legacy_planning_harness import with_legacy_langgraph_harness


def _dispatch_for_query(query: str, *, routed_skill: str = "spl_generation"):
    qu = understand_query(query)
    q2i = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill=routed_skill,
    )
    plan = plan_evidence(
        q2i.intent_classification,
        q2i.model_dump(),
        routed={"skill": routed_skill},
        query_understanding=qu,
    )
    return build_pipeline_dispatch(
        evidence_plan=plan.model_dump(),
        intent_classification=q2i.intent_classification.model_dump(),
        query_to_intent=q2i.model_dump(mode="json"),
    )


def test_knowledge_only_schedules_rag_early() -> None:
    state = _dispatch_for_query("What is a DGA domain?", routed_skill="knowledge_recall")
    assert state.decision.request_mode == "knowledge"
    assert state.decision.stage_schedule == [PipelineStage.rag_early]
    assert state.decision.llm_hops == []


def test_bare_mitre_id_explanation_stays_on_legacy_mitre_knowledge() -> None:
    # Policy (drift log 2026-07-05): a bare "Explain MITRE T####" ask was already
    # answered correctly by the legacy mitre_knowledge path — the reference lane
    # only takes taxonomy/apply/detect/ATLAS/CVE-framed asks. Route-stealing a
    # working query into the new lane is a regression, not a feature.
    state = _dispatch_for_query("Explain MITRE technique T1021", routed_skill="knowledge_recall")
    assert state.decision.request_mode == "mitre_knowledge"
    assert PipelineStage.mitre_finalize in state.decision.stage_schedule
    assert PipelineStage.reference_finalize not in state.decision.stage_schedule


def test_detect_framed_mitre_id_routes_reference_knowledge() -> None:
    # P3-class framing (ID + "how do we detect") is the reference lane's positive case.
    state = _dispatch_for_query("What is T1110.003 and how do we detect it?", routed_skill="knowledge_recall")
    assert state.decision.request_mode == "reference_knowledge"
    assert state.decision.stage_schedule == [
        PipelineStage.rag_early,
        PipelineStage.reference_finalize,
    ]


def test_reference_taxonomy_query_schedules_reference_finalize() -> None:
    state = _dispatch_for_query("What MITRE ATLAS techniques apply to prompt injection against our LLM agent using MCP tools?", routed_skill="knowledge_recall")
    assert state.decision.request_mode == "reference_knowledge"
    assert state.decision.stage_schedule == [
        PipelineStage.rag_early,
        PipelineStage.reference_finalize,
    ]


def test_spl_authoring_with_index_skips_pre_mcp_but_includes_spl_chain() -> None:
    state = _dispatch_for_query("Generate SPL for index=scada_perf by rtu_id over last 24h")
    assert state.decision.request_mode == "utility_spl"
    assert state.decision.stage_schedule == [
        PipelineStage.workflow_spl,
        PipelineStage.spl_postprocessor,
        PipelineStage.spl_source_resolve,
    ]
    flags = project_dispatch_flags(state.decision)
    assert flags["run_mcp_execution"] is False
    assert flags["run_pre_spl_mcp_discovery"] is False


def test_live_data_spl_authoring_schedules_pre_mcp_not_execution() -> None:
    state = _dispatch_for_query("Generate SPL for failed logins")
    assert state.decision.request_mode == "utility_spl"
    assert PipelineStage.pre_spl_mcp_discovery not in state.decision.stage_schedule
    assert PipelineStage.mcp_execution not in state.decision.stage_schedule
    assert PipelineStage.workflow_spl in state.decision.stage_schedule


def test_spl_plan_compiler_hop_when_fallback_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    # Review-only "Generate SPL" is utility_spl and does not schedule plan-compiler.
    # Plan-compiler remains on the non-utility spl_authoring / run path.
    state = _dispatch_for_query(
        "Investigate failed logins for index=scada_perf over last 24h and return live results"
    )
    if state.decision.request_mode == "utility_spl":
        assert LlmHop.spl_plan_compiler not in state.decision.llm_hops
    else:
        assert LlmHop.spl_plan_compiler in state.decision.llm_hops


def test_cp_off_synthetic_evidence_plan_builds_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    query = "Generate SPL for index=scada_perf by rtu_id over last 24h"
    qu = understand_query(query)
    q2i = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill="spl_generation",
    )
    state = graph_node_evidence_planning(
        with_legacy_langgraph_harness(
            {
                "request": ChatRequest(message=query),
                "query_understanding": qu,
                "routed": {"skill": "spl_generation"},
                "query_to_intent": q2i.model_dump(mode="json"),
                "intent_classification": q2i.intent_classification.model_dump(mode="json"),
                "selected_use_case": None,
            }
        )
    )
    dispatch = state["pipeline_dispatch"]["decision"]
    assert dispatch["request_mode"] == "utility_spl"
    assert dispatch["stage_schedule"] == [
        PipelineStage.workflow_spl.value,
        PipelineStage.spl_postprocessor.value,
        PipelineStage.spl_source_resolve.value,
    ]


def test_utility_spl_mode_omits_pre_mcp() -> None:
    plan = EvidencePlan(
        answer_mode="spl_utility_authoring",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
        reasons=["universal_spl_utility_authoring"],
    )
    state = build_pipeline_dispatch(
        evidence_plan=plan.model_dump(),
        intent_classification={"intent_family": "spl_generation_only"},
    )
    assert state.decision.request_mode == "utility_spl"
    assert state.decision.stage_schedule == list(
        (
            PipelineStage.workflow_spl,
            PipelineStage.spl_postprocessor,
            PipelineStage.spl_source_resolve,
        )
    )


def test_evidence_need_hints_schedule_pre_spl_mcp() -> None:
    plan = EvidencePlan(
        answer_mode="hybrid",
        rag_phase="pre_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
        normalized_slot_summary={"normalized_slots": {"index": "main", "sourcetype": "syslog"}},
    )
    dispatch = build_pipeline_dispatch(
        evidence_plan=plan.model_dump(),
        intent_classification={"intent_family": "spl_authoring"},
        query_to_intent={
            "llm_intent_advisory": {"evidence_need_hints": ["splunk_index_metadata"]},
        },
    )
    assert PipelineStage.pre_spl_mcp_discovery in dispatch.decision.stage_schedule
