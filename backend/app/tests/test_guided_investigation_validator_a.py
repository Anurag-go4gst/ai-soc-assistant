"""REV4 batch 1 P3 — InvestigationPlan Validator (A)."""

from __future__ import annotations

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guided_investigation_planner import validate_investigation_plan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)


def _baseline() -> InvestigationPlan:
    return build_deterministic_investigation_plan(query=SAMPLE_QUERY)


def test_validate_baseline_only_returns_deterministic_plan() -> None:
    baseline = _baseline()
    validated = validate_investigation_plan(baseline)
    assert validated.plan_source == "deterministic_only"
    assert validated.human_review_required is True
    assert validated.hypotheses == baseline.hypotheses


def test_hostile_raw_spl_in_proposal_is_dropped() -> None:
    baseline = _baseline()
    proposal = {
        "hypotheses": [
            "index=secret_ot | stats count by dest",
            *baseline.hypotheses,
        ],
        "evidence_needed": [
            "sourcetype=made_up_type | head 1000",
        ],
    }
    validated = validate_investigation_plan(baseline, proposal)
    assert all("index=secret_ot" not in item for item in validated.hypotheses)
    assert all("made_up_type" not in item for item in validated.evidence_needed)
    assert any("dropped_hypothesis_unsafe_text" in w for w in validated.validation_warnings)
    assert any("dropped_evidence_unsafe_text" in w for w in validated.validation_warnings)


def test_invented_tool_and_template_requests_are_dropped() -> None:
    baseline = _baseline()
    proposal = {
        "read_only_tool_requests": [
            "mcp_tool:splunk_run_query",
            "mcp_tool:splunk_get_info",
            "mcp_tool:splunk_totally_fake",
        ],
        "safe_spl_template_requests": [
            "not_a_real_template_id",
        ],
    }
    validated = validate_investigation_plan(baseline, proposal)
    assert validated.read_only_tool_requests == ["mcp_tool:splunk_get_info"]
    assert validated.safe_spl_template_requests == []
    assert any("dropped_unknown_tool:" in w for w in validated.validation_warnings)
    assert any("dropped_unknown_template:" in w for w in validated.validation_warnings)


def test_authority_fields_cannot_be_set_via_proposal() -> None:
    baseline = _baseline()
    proposal = {
        "final_route": "spl_generation",
        "execution_eligible": True,
        "mcp_allowed": True,
        "severity": "P1",
        "hypotheses": ["Candidate vendor maintenance change."],
    }
    validated = validate_investigation_plan(baseline, proposal)
    payload = validated.model_dump()
    assert "final_route" not in payload
    assert "execution_eligible" not in payload
    assert "mcp_allowed" not in payload
    assert "severity" not in payload
    assert validated.human_review_required is True
    assert any("dropped_forbidden_authority_field:" in w for w in validated.validation_warnings)
    assert "Candidate vendor maintenance change." in validated.hypotheses


def test_baseline_wins_on_conflicting_objective_and_booleans() -> None:
    baseline = _baseline()
    proposal = {
        "investigation_objective": "Execute SPL now and isolate the host",
        "rag_sufficient": True,
        "discovery_needed": True,
        "human_review_required": False,
        "spl_review_requested": True,
    }
    validated = validate_investigation_plan(baseline, proposal)
    assert validated.investigation_objective == baseline.investigation_objective
    assert validated.rag_sufficient is False
    assert validated.discovery_needed is False
    assert validated.spl_review_requested is False
    assert validated.human_review_required is True
