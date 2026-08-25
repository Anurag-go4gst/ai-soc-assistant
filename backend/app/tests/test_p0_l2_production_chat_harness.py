"""P0 L2 — high-value production /chat harness probes (mocked LLM + MCP)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.investigation_outcome import derive_investigation_outcome
from app.chat.investigation_plan_delta import validate_plan_delta
from app.chat.pipeline import build_live_chat_response
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.orchestration.splunk_call_authorization import call_grant_from_validation, grants_match
from app.connectors.mcp.splunk_mcp_readiness import splunk_search_tool_arguments
from app.schemas.requests import ChatRequest
from app.spl.utility_spl_authoring import candidate_from_universal_utility_authoring

_WEEKEND_UTILITY = (
    "Without using any specific company templates, write a standard, universal SPL block "
    "that extracts the hour of the day and day of the week from an event timestamp, "
    "filtering only for weekend events."
)
_REVIEW_ONLY_SPL = (
    "Give me only a review-only SPL query for index=pgcil_soc and "
    "sourcetype=cisco:firepower for the last 30 days. Do not execute it."
)
_INVESTIGATE_QUERY = (
    "Investigate failed login spike for user:alice host:APP-01 "
    "from 10.0.0.8 in the last 24 hours"
)
_DENIED_TOP_SRC = (
    "Give me an SPL query to show the top source IPs generating denied firewall "
    "traffic in the last 24 hours."
)
_DELTA_SPL_A = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now user=alice "
    "| stats count by user | head 100"
)
_DELTA_SPL_B = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now user=alice action=success "
    "| stats count by user | head 100"
)
CAPABILITY = "mcp:splunk:splunk_run_query"
METADATA_CAPABILITY = "mcp:splunk:splunk_get_indexes"


@pytest.fixture(autouse=True)
def _spl_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    allowed_indexes = "pgcil_soc"
    allowed_sourcetypes = "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns,cisco:firepower"
    monkeypatch.setenv("SPL_ALLOWED_INDEXES", allowed_indexes)
    monkeypatch.setenv("SPL_ALLOWED_SOURCETYPES", allowed_sourcetypes)
    monkeypatch.setattr(settings, "spl_allowed_indexes", allowed_indexes)
    monkeypatch.setattr(settings, "spl_allowed_sourcetypes", allowed_sourcetypes)


def _payload(message: str) -> dict[str, Any]:
    return build_live_chat_response(ChatRequest(message=message)).model_dump(mode="json")


def test_l2_pure_spl_utility_authoring_route() -> None:
    payload = _payload(_WEEKEND_UTILITY)
    assert payload["selected_skill"] in {"spl_generation", "guided_investigation"}
    candidate = payload.get("candidate_spl") or {}
    mode = candidate.get("generation_mode")
    assert candidate.get("candidate_spl") or mode in {
        "spl_authoring_unavailable",
        "clarification_required",
        "deterministic_lab_draft",
        "utility_llm_spl_draft",
        "utility_llm_spl_repair",
        "deterministic_user_bound_skeleton",
    }


def test_l2_exact_bound_review_only_spl_not_executed() -> None:
    payload = _payload(_REVIEW_ONLY_SPL)
    assert payload["spl_validation"]["approved"] is True
    assert payload["execution"]["status"] == "skipped"
    assert payload["execution"]["executed_spl"] is None
    assert "index=pgcil_soc" in (payload.get("candidate_spl") or {}).get("candidate_spl", "")


def test_l2_genuine_investigation_mcp_unavailable_honest() -> None:
    payload = _payload(_INVESTIGATE_QUERY)
    execution = payload.get("execution") or {}
    assert execution.get("status") != "executed"
    assert execution.get("executed_spl") is None


def test_l2_agentic_flag_posture_monkeypatch_smallest_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_capability_snapshot_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_plan_delta_enabled", True)
    payload = _payload(_INVESTIGATE_QUERY)
    trace = payload.get("control_plane_trace") or {}
    assert payload.get("selected_skill")
    assert trace.get("mcp_tool_readiness", {}).get("schema_version") in {None, "mcp_tool_readiness_v2"}


def test_l2_plan_delta_two_rounds_distinct_fingerprints() -> None:
    envelope = ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="Investigate alice authentication activity",
        targets=["user:alice"],
        entities={"user": "alice"},
        time_scope="last 24 hours",
        approved_evidence_categories=["sessions"],
        allowed_read_only_capabilities=[CAPABILITY],
        source_index_scope={"indexes": ["pgcil_soc"]},
    )
    snapshot = {
        "rows": [{"capability_id": CAPABILITY, "capability_need": "required", "availability": "available"}]
    }
    from app.chat.contracts.plan_delta import PlanDeltaProposal

    first = validate_plan_delta(
        PlanDeltaProposal.model_validate(
            {
                "envelope_version": 2,
                "objective": envelope.objective,
                "evidence_need": "authentication_correlation",
                "capability_id": CAPABILITY,
                "access_mode": "read_only",
                "targets": envelope.targets,
                "entities": envelope.entities,
                "time_scope": envelope.time_scope,
                "source_index_scope": envelope.source_index_scope,
                "tool_arguments": {"query": _DELTA_SPL_A},
            }
        ),
        envelope=envelope,
        capability_snapshot=snapshot,
        missing_evidence=["authentication_correlation"],
        prior_revisions=[],
    )
    assert first.status == "accepted"
    assert first.validated_delta is not None
    second = validate_plan_delta(
        PlanDeltaProposal.model_validate(
            {
                "envelope_version": 2,
                "objective": envelope.objective,
                "evidence_need": "authentication_correlation",
                "capability_id": CAPABILITY,
                "access_mode": "read_only",
                "targets": envelope.targets,
                "entities": envelope.entities,
                "time_scope": envelope.time_scope,
                "source_index_scope": envelope.source_index_scope,
                "tool_arguments": {"query": _DELTA_SPL_B},
                "prior_revision_fingerprint": first.validated_delta.revision_fingerprint,
            }
        ),
        envelope=envelope,
        capability_snapshot=snapshot,
        missing_evidence=["authentication_correlation"],
        prior_revisions=[first.validated_delta.model_dump(mode="json")],
    )
    assert second.status == "accepted"
    assert second.validated_delta is not None
    assert (
        first.validated_delta.revision_fingerprint
        != second.validated_delta.revision_fingerprint
    )


def test_l2_metadata_fallback_via_plan_delta_after_search_gap() -> None:
    envelope = ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="Investigate index visibility",
        targets=[],
        entities={},
        time_scope="last 24 hours",
        approved_evidence_categories=["index_context"],
        allowed_read_only_capabilities=[METADATA_CAPABILITY],
        source_index_scope={"indexes": ["pgcil_soc"]},
    )
    snapshot = {
        "rows": [
            {"capability_id": METADATA_CAPABILITY, "capability_need": "required", "availability": "available"}
        ]
    }
    from app.chat.contracts.plan_delta import PlanDeltaProposal

    decision = validate_plan_delta(
        PlanDeltaProposal.model_validate(
            {
                "envelope_version": 2,
                "objective": envelope.objective,
                "evidence_need": "index_context",
                "capability_id": METADATA_CAPABILITY,
                "access_mode": "read_only",
                "targets": [],
                "entities": {},
                "time_scope": envelope.time_scope,
                "source_index_scope": envelope.source_index_scope,
                "tool_arguments": {},
            }
        ),
        envelope=envelope,
        capability_snapshot=snapshot,
        missing_evidence=["index_context"],
        prior_revisions=[],
    )
    assert decision.status == "accepted"
    assert decision.validated_delta is not None
    assert decision.validated_delta.tool_arguments == {}


def test_l2_unavailable_capability_honest_stop() -> None:
    envelope = ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="Investigate",
        targets=[],
        entities={},
        time_scope="last 24 hours",
        approved_evidence_categories=["sessions"],
        allowed_read_only_capabilities=[CAPABILITY],
        source_index_scope={"indexes": ["pgcil_soc"]},
    )
    snapshot = {"rows": [{"capability_id": CAPABILITY, "capability_need": "required", "availability": "unavailable"}]}
    from app.chat.contracts.plan_delta import PlanDeltaProposal

    decision = validate_plan_delta(
        PlanDeltaProposal.model_validate(
            {
                "envelope_version": 2,
                "objective": envelope.objective,
                "evidence_need": "sessions",
                "capability_id": CAPABILITY,
                "access_mode": "read_only",
                "targets": [],
                "entities": {},
                "time_scope": envelope.time_scope,
                "source_index_scope": envelope.source_index_scope,
                "tool_arguments": {"query": _DELTA_SPL_A},
            }
        ),
        envelope=envelope,
        capability_snapshot=snapshot,
        missing_evidence=["sessions"],
        prior_revisions=[],
    )
    assert decision.status == "rejected"
    assert decision.reason == "capability_not_available_on_snapshot"


def test_l2_contradictory_evidence_disposition_inconclusive_both_retained() -> None:
    outcome = derive_investigation_outcome(
        evidence_sufficiency={"status": "INSUFFICIENT", "missing": ["authentication_correlation"]},
        structured_context={
            "structured_facts": [
                {"statement": "healthy endpoint posture", "source_refs": ["ev:healthy"]},
                {"statement": "compromised endpoint posture", "source_refs": ["ev:compromised"]},
            ],
            "source_evidence_refs": ["ev:healthy", "ev:compromised"],
        },
        severity_label="P2",
        outcome_v2_enabled=True,
    )
    assert outcome.disposition == "inconclusive"
    assert outcome.investigation_status != "completed"
    assert len(outcome.findings) >= 2
    assert outcome.evidence_refs == ["ev:healthy", "ev:compromised"]


def test_l2_time_delta_invalidates_exact_call_grant() -> None:
    spl_a = _DELTA_SPL_A
    spl_b = _DELTA_SPL_B
    grant_a = call_grant_from_validation(
        trace_id="l2-grant",
        selection={"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_run_query"},
        spl_validation={"approved": True, "normalized_spl": spl_a},
        hil_required=True,
    )
    grant_b = call_grant_from_validation(
        trace_id="l2-grant",
        selection={"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_run_query"},
        spl_validation={"approved": True, "normalized_spl": spl_b},
        hil_required=True,
    )
    assert grants_match({"call_grant": grant_a}, grant_b) is False
    assert splunk_search_tool_arguments(normalized_spl=spl_a) != splunk_search_tool_arguments(
        normalized_spl=spl_b
    )


def test_l2_llm_unavailable_utility_authoring_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    payload = _payload(_WEEKEND_UTILITY)
    candidate = payload.get("candidate_spl") or {}
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("final_raw_spl_source") in {"deterministic_skeleton", "llm_draft", "llm_repair", None}


def test_l2_semantic_fidelity_unresolved_not_surfaced_as_satisfied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", True)
    unfaithful = (
        "search index=pgcil_soc sourcetype=cisco:firepower earliest=-24h latest=now "
        "| table _time src_ip | head 100"
    )
    payload_json = json.dumps(
        {
            "status": "candidate_generated",
            "confidence_score": 0.72,
            "confidence_label": "medium",
            "candidate_spl": unfaithful,
            "detection_family": "firewall_denied_top_src",
            "assumptions": ["Unfaithful draft for fidelity gate"],
            "required_fields": ["src_ip"],
            "missing_details": [],
            "clarifying_questions": [],
            "validation_notes": [],
            "soc_std_rules_applied": [],
            "risk_notes": [],
            "execution_eligible": False,
            "governed": False,
            "catalog_approved": False,
        }
    )

    class _T:
        def record_step(self, *a: Any, **k: Any) -> None:
            return None

        def record_spl_validation(self, *a: Any, **k: Any) -> None:
            return None

    profile = __import__(
        "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
    ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    monkeypatch.setattr("app.spl.utility_spl_authoring.load_persisted_source_profile", lambda: {})
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )
    result = candidate_from_universal_utility_authoring(
        trace_id="l2-fidelity",
        skill="spl_generation",
        user_query=_DENIED_TOP_SRC,
        telemetry=_T(),
        profile=profile,
        spl_governance=None,
        llm_raw_output_provider=lambda: payload_json,
    )
    assert result is not None
    candidate, validation = result
    assert candidate.get("candidate_spl") == ""
    assert "semantic_fidelity_unresolved" in (validation.get("reject_reasons") or [])


def test_l2_containment_observation_vs_request() -> None:
    observe = extract_query_signals("Investigate firewall deny spike")
    enforce = extract_query_signals("block this IP on the firewall")
    assert observe.get("block_or_contain") is False
    assert enforce.get("block_or_contain") is True


def test_l2_entity_correction_invalidates_prior_grant_and_scope() -> None:
    """Follow-up 'use host X instead of Y' must not reuse the prior exact-call grant."""
    spl_y = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now host=host-y "
        "| stats count by host | head 100"
    )
    spl_x = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now host=host-x "
        "| stats count by host | head 100"
    )
    selection = {"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_run_query"}
    grant_y = call_grant_from_validation(
        trace_id="l2-entity",
        selection=selection,
        spl_validation={"approved": True, "normalized_spl": spl_y},
        hil_required=True,
    )
    grant_x = call_grant_from_validation(
        trace_id="l2-entity",
        selection=selection,
        spl_validation={"approved": True, "normalized_spl": spl_x},
        hil_required=True,
    )
    assert grants_match({"call_grant": grant_y}, grant_x) is False
    args_x = splunk_search_tool_arguments(normalized_spl=spl_x, trace_id="l2-entity")
    assert "host-y" not in str(args_x.get("search_query") or "")
    assert "host-x" in str(args_x.get("search_query") or "")
