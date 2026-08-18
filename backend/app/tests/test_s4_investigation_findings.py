"""S4 structured investigation findings — EC fixture discipline."""

from __future__ import annotations

from app.demo.fixtures.s4.investigation_findings import (
    S4_AFFECTED_ASSETS,
    finding_for_investigation_step,
)


def test_skipped_step_does_not_claim_complete_finding() -> None:
    finding = finding_for_investigation_step(
        "agilus_patch_analysis",
        status="SKIPPED",
        applied=["run_network_assessment", "run_splunk_ioc_hunt"],
        agent_state={"agilus_analysis_decision": "skipped"},
        outcome={},
        selected=False,
    )
    assert finding is not None
    assert finding["headline_finding"].startswith("Skipped")
    assert finding["key_evidence"] == []
    assert finding["evidence_sources"] == []


def test_complete_gateway_step_derives_from_fixture_inventory() -> None:
    finding = finding_for_investigation_step(
        "identify_gateways",
        status="COMPLETE",
        applied=["run_network_assessment", "list_affected_assets", "check_gateway_versions"],
        agent_state={},
        outcome={},
        selected=True,
    )
    assert finding is not None
    assert "12 internet-facing" in finding["headline_finding"]
    assert len(finding["affected_entities"]) == len(S4_AFFECTED_ASSETS)
    assert finding["evidence_sources"][0]["evidence_id"] == "ev-s4-cmdb"


def test_ioc_hunt_caveat_states_negative_evidence_limit() -> None:
    finding = finding_for_investigation_step(
        "hunt_iocs",
        status="COMPLETE",
        applied=["run_splunk_ioc_hunt", "search_exploitation_indicators"],
        agent_state={},
        outcome={},
        selected=True,
    )
    assert finding is not None
    assert "not proof of no compromise" in finding["caveat"].lower()
