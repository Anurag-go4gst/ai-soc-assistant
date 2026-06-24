"""Regression tests for out-of-catalog novel-question collapse fixes."""

from __future__ import annotations

import pytest

from app.chat.skill_contribution import (
    SkillContribution,
    apply_out_of_catalog_guidance_floor,
    build_skill_contribution,
)
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.responses import AnalystResponseEnvelope


@pytest.fixture(autouse=True)
def _enable_t2(monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)


def test_out_of_registry_supply_chain_routes_guided_not_knowledge_recall() -> None:
    query = (
        "A vendor pushed a firmware update signed with an unexpected code-signing "
        "certificate to 40 RTUs overnight. How do we determine whether this is a "
        "legitimate vendor key rotation or a supply-chain compromise?"
    )
    understanding = understand_query(query)
    base, provenance = select_route_from_understanding(understanding, query)
    assert base["skill"] == "guided_investigation"
    assert "out_of_registry_t2_answer_shape_floor" in base["reasons"]


def test_out_of_registry_dlp_containment_shape_floor() -> None:
    query = (
        "A privileged user copied 12 GB to a personal cloud drive after hours. "
        "Should we isolate the endpoint or start with DLP review?"
    )
    understanding = understand_query(query)
    base, _ = select_route_from_understanding(understanding, query)
    assert base["skill"] == "guided_investigation"


def test_out_of_catalog_guidance_floor_preserves_message() -> None:
    message = "Supply-chain firmware integrity review (review-only)\nVerify certificate chain."
    contrib = build_skill_contribution(
        selected_skill="guided_investigation",
        envelope=None,
        routing_provenance={"deterministic_match_path": "out_of_registry"},
    )
    envelope = apply_out_of_catalog_guidance_floor(
        envelope=None,
        contribution=contrib,
        message=message,
        match_path="out_of_registry",
    )
    assert envelope is not None
    assert "Supply-chain" in (envelope.direct_answer_summary or "")
    assert contrib.floor_applied is True
    assert contrib.visible_domain_section is True


def test_out_of_catalog_floor_skips_kb_no_match_stub() -> None:
    contrib = SkillContribution(selected_skill="knowledge_recall")
    envelope = apply_out_of_catalog_guidance_floor(
        envelope=AnalystResponseEnvelope(),
        contribution=contrib,
        message="No governed KB/SOP match was found for this request.",
        match_path="out_of_registry",
    )
    assert envelope.direct_answer_summary in (None, "")
    assert contrib.floor_applied is False
