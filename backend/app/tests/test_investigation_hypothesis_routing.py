"""Routing: hypothesis/guidance hunts must not bind catalog SPL templates."""

from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.chat.intent_classifier import build_candidate_mappings, build_query_to_intent
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.routing.skill_router import route_skill
from app.schemas.requests import ChatRequest

COBALT_HYPOTHESIS_QUERY = (
    "What hunting hypotheses should I validate for cobalt strike beaconing "
    "across VPN and DNS logs without a known IOC list?"
)
DNS_BEACONING_SPL_QUERY = "Find DNS beaconing candidates in the last 24 hours"
TEMPLATE_QUERY = "Show failed login spike by user in the last 24 hours"
OT_HUNT_QUERY = "Strange OT chatter to a new external host overnight, anything to hunt?"


@pytest.fixture(autouse=True)
def _spl_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.spl_allowed_sourcetypes",
        "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns",
    )


def test_catalog_overlap_hypothesis_maps_match_path_to_out_of_registry() -> None:
    understanding = understand_query(COBALT_HYPOTHESIS_QUERY)
    mappings = build_candidate_mappings(
        understanding,
        routed_skill="guided_investigation",
        routing_provenance={"deterministic_match_path": "out_of_registry", "catalog_keyword_rescue": True},
    )
    assert mappings["match_path"] == "out_of_registry"
    assert "dns_beaconing_candidate" in mappings["use_case_ids"]

    q2i = build_query_to_intent(
        query=COBALT_HYPOTHESIS_QUERY,
        query_understanding=understanding,
        routed_skill="guided_investigation",
        routing_provenance={"deterministic_match_path": "out_of_registry"},
    )
    assert q2i.intent_classification.intent_family == "guided_investigation"


def test_cobalt_hypothesis_query_prefers_guided_investigation_not_dns_template() -> None:
    understanding = understand_query(COBALT_HYPOTHESIS_QUERY)
    assert "dns_beaconing_candidate" in (understanding.mapped_use_case_ids or [])
    assert understanding.soc_investigation_shaped is True

    routed = route_skill(COBALT_HYPOTHESIS_QUERY)
    assert routed["skill"] == "guided_investigation"
    assert any("hypothesis_guidance" in reason for reason in routed.get("reasons") or [])

    response = chat(ChatRequest(message=COBALT_HYPOTHESIS_QUERY))
    assert response.selected_skill == "guided_investigation"
    assert response.candidate_spl is None
    assert response.spl_validation is None
    contract = response.answer_contract
    notice = contract.get("out_of_catalog_notice") if isinstance(contract, dict) else getattr(contract, "out_of_catalog_notice", None)
    assert notice


def test_dns_beaconing_candidate_query_still_renders_template_spl() -> None:
    response = chat(ChatRequest(message=DNS_BEACONING_SPL_QUERY))
    assert response.candidate_spl is not None
    assert response.candidate_spl.template_id == "dns_beaconing_candidate"
    assert response.spl_validation is not None
    assert response.spl_validation.approved is True


def test_failed_login_template_query_unaffected() -> None:
    response = chat(ChatRequest(message=TEMPLATE_QUERY))
    assert response.candidate_spl is not None
    assert response.candidate_spl.template_id == "auth_failed_login_spike"
    assert "earliest=-24h" in response.candidate_spl.candidate_spl


def test_ot_hunt_query_still_guided_without_catalog_overlap() -> None:
    understanding = understand_query(OT_HUNT_QUERY)
    base, provenance = select_route_from_understanding(understanding, OT_HUNT_QUERY)
    assert base["skill"] == "guided_investigation"
    assert provenance.get("rescue_mode") is True
