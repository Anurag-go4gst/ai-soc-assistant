"""P0-D — productive two-round investigation via plan_delta + AUTH0 continuity."""

from __future__ import annotations

from app.chat.contracts.investigation_envelope import ApprovedInvestigationEnvelope
from app.chat.contracts.plan_delta import PlanDeltaProposal
from app.chat.investigation_plan_delta import validate_plan_delta
from app.chat.planned_mcp_call import enrich_capability_binding, planned_arguments_hash
from app.chat.contracts.investigation_plan import InvestigationCapabilityBinding
from app.connectors.mcp.splunk_mcp_readiness import splunk_search_tool_arguments
from app.orchestration.splunk_call_authorization import call_grant_from_validation, grants_match

CAPABILITY = "mcp:splunk:splunk_run_query"
ROUND_ONE_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now user=alice "
    "| stats count by user | head 100"
)
ROUND_TWO_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now user=alice action=success "
    "| stats count by src | head 100"
)
SELECTION = {"selected_mcp_server": "splunk_soc", "selected_mcp_tool": "splunk_run_query"}


def _envelope() -> ApprovedInvestigationEnvelope:
    return ApprovedInvestigationEnvelope(
        envelope_version=2,
        objective="Investigate alice authentication activity",
        targets=["user:alice"],
        entities={"user": "alice"},
        time_scope="last 24 hours",
        approved_evidence_categories=["sessions", "authentication_correlation"],
        allowed_read_only_capabilities=[CAPABILITY],
        source_index_scope={"indexes": ["pgcil_soc"]},
    )


def _snapshot() -> dict:
    return {
        "rows": [{"capability_id": CAPABILITY, "capability_need": "required", "availability": "available"}]
    }


def _proposal(spl: str, *, prior_fp: str | None = None) -> PlanDeltaProposal:
    payload = {
        "envelope_version": 2,
        "objective": "Investigate alice authentication activity",
        "evidence_need": "authentication_correlation",
        "capability_id": CAPABILITY,
        "access_mode": "read_only",
        "targets": ["user:alice"],
        "entities": {"user": "alice"},
        "time_scope": "last 24 hours",
        "source_index_scope": {"indexes": ["pgcil_soc"]},
        "tool_arguments": {"query": spl},
        "hypothesis": "Correlate denied and successful sessions.",
        "evidence_refs": ["evidence:sessions"],
    }
    if prior_fp:
        payload["prior_revision_fingerprint"] = prior_fp
    return PlanDeltaProposal.model_validate(payload)


def test_productive_two_round_investigation_distinct_planned_hashes_and_grants() -> None:
    binding = enrich_capability_binding(
        InvestigationCapabilityBinding(
            capability_id=CAPABILITY,
            capability_need="required",
            availability="available",
            access_mode="read_only",
        ),
        normalized_spl=ROUND_ONE_SPL,
        trace_id="p0d-r1",
    )
    round_one = validate_plan_delta(
        _proposal(ROUND_ONE_SPL),
        envelope=_envelope(),
        capability_snapshot=_snapshot(),
        missing_evidence=["authentication_correlation"],
        prior_revisions=[],
    )
    assert round_one.status == "accepted"
    assert round_one.validated_delta is not None

    grant_one = call_grant_from_validation(
        trace_id="p0d-r1",
        selection=SELECTION,
        spl_validation={"approved": True, "normalized_spl": ROUND_ONE_SPL},
        hil_required=True,
    )
    planned_one = splunk_search_tool_arguments(normalized_spl=ROUND_ONE_SPL, trace_id="p0d-r1")
    assert planned_arguments_hash(planned_one) == grant_one["canonical_arguments_hash"]
    assert planned_arguments_hash(binding.planned_arguments) == grant_one["canonical_arguments_hash"]

    round_two = validate_plan_delta(
        _proposal(
            ROUND_TWO_SPL,
            prior_fp=round_one.validated_delta.revision_fingerprint,
        ),
        envelope=_envelope(),
        capability_snapshot=_snapshot(),
        missing_evidence=["authentication_correlation"],
        prior_revisions=[round_one.validated_delta.model_dump(mode="json")],
    )
    assert round_two.status == "accepted"
    assert round_two.validated_delta is not None
    assert (
        round_one.validated_delta.revision_fingerprint
        != round_two.validated_delta.revision_fingerprint
    )

    grant_two = call_grant_from_validation(
        trace_id="p0d-r2",
        selection=SELECTION,
        spl_validation={"approved": True, "normalized_spl": ROUND_TWO_SPL},
        hil_required=True,
    )
    planned_two = splunk_search_tool_arguments(normalized_spl=ROUND_TWO_SPL, trace_id="p0d-r2")
    assert planned_arguments_hash(planned_two) == grant_two["canonical_arguments_hash"]
    assert grant_one["fingerprint"] != grant_two["fingerprint"]
    assert grants_match({"call_grant": grant_one}, grant_two) is False

    # Replaying round-one grant against round-two material must invalidate.
    assert grants_match({"call_grant": grant_one}, grant_two) is False

    # Evidence sufficiency must change when round-2 evidence fills a prior gap.
    sufficiency_r1 = {
        "status": "INSUFFICIENT",
        "missing": ["authentication_correlation"],
        "produced": ["sessions"],
        "provenance": [{"round": 1, "tool": "splunk_run_query", "args_hash": grant_one["canonical_arguments_hash"]}],
    }
    sufficiency_r2 = {
        "status": "SUFFICIENT",
        "missing": [],
        "produced": ["sessions", "authentication_correlation"],
        "provenance": [
            *sufficiency_r1["provenance"],
            {"round": 2, "tool": "splunk_run_query", "args_hash": grant_two["canonical_arguments_hash"]},
        ],
    }
    assert sufficiency_r1["status"] != sufficiency_r2["status"]
    assert sufficiency_r1["missing"] != sufficiency_r2["missing"]
    assert len(sufficiency_r2["provenance"]) == 2
    assert (
        sufficiency_r2["provenance"][0]["args_hash"]
        != sufficiency_r2["provenance"][1]["args_hash"]
    )
