"""REV4 batch 2 P9 — bounded LLM InvestigationPlan propose."""

from __future__ import annotations

import json

from app.chat.guided_investigation_plan_llm import propose_investigation_plan_llm
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)


def test_propose_maps_llm_json_to_validator_proposal() -> None:
    baseline = build_deterministic_investigation_plan(query=SAMPLE_QUERY)

    def _provider() -> str:
        return json.dumps(
            {
                "hypotheses": ["Vendor maintenance window may explain the traffic."],
                "evidence_needed": ["Correlate firewall egress with change tickets."],
                "data_categories": ["network_flow"],
                "rag_sufficient": False,
                "env_kb_needed": False,
                "discovery_needed": True,
                "read_only_tools": ["mcp_tool:splunk_get_metadata"],
                "safe_spl_templates": [],
                "spl_review_requested": False,
                "clarification_needed": False,
                "clarification_questions": [],
                "refinement_recommended": False,
                "rationale": "",
            }
        )

    result = propose_investigation_plan_llm(
        query=SAMPLE_QUERY,
        baseline=baseline,
        llm_raw_output_provider=_provider,
    )
    assert result.attempted is True
    assert result.raw_llm is not None
    validated = validate_investigation_plan(
        baseline,
        result.proposal,
        llm_attempted=result.attempted,
    )
    assert validated.plan_source == "llm_proposed_validated"
    assert "Vendor maintenance window may explain the traffic." in validated.hypotheses
    assert validated.discovery_needed is True
    assert "mcp_tool:splunk_get_metadata" in validated.read_only_tool_requests
    assert validated.llm_budget_used == 1


def test_llm_timeout_falls_back_to_baseline_only() -> None:
    baseline = build_deterministic_investigation_plan(query=SAMPLE_QUERY)
    result = propose_investigation_plan_llm(
        query=SAMPLE_QUERY,
        baseline=baseline,
        llm_raw_output_provider=lambda: "",
    )
    assert result.attempted is True
    validated = validate_investigation_plan(
        baseline,
        result.proposal,
        llm_attempted=result.attempted,
    )
    assert validated.plan_source == "llm_failed_baseline_only"
    assert validated.hypotheses == baseline.hypotheses


def test_llm_not_configured_skips_attempt() -> None:
    baseline = build_deterministic_investigation_plan(query=SAMPLE_QUERY)
    result = propose_investigation_plan_llm(query=SAMPLE_QUERY, baseline=baseline)
    if result.attempted:
        return
    validated = validate_investigation_plan(baseline, result.proposal, llm_attempted=False)
    assert validated.plan_source == "deterministic_only"
    assert validated.llm_budget_used == 0
