"""Answer-shape router + planner-informed adjudication (item 1.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.answer_shape_router import (
    _classify_answer_shape_regex,
    classify_answer_shape,
    plan_purposes_from_resource_plan,
    shape_hint_from_plan_purposes,
)
from app.evals.run_out_of_catalogue_scorecard import _observed_answer_shape

_AMBIGUOUS_OT = "Brand-new external host contacted from OT VLAN overnight."
_REGULATORY = "What is our CERT-In 6-hour reporting obligation for this OT incident?"
_TI = "A new advisory targets utilities; based on what we log today, are we exposed?"


def _promoted_plan(*purposes: str) -> dict:
    return {
        "plan_source": "llm_proposed_validated",
        "provenance": {"llm_bridge": "promoted"},
        "steps": [
            {"step_id": f"llm_{index}", "resource_id": f"resource:{index}", "purpose": purpose}
            for index, purpose in enumerate(purposes)
        ],
    }


def test_regex_floor_unchanged_without_resource_plan() -> None:
    regex = _classify_answer_shape_regex(_REGULATORY)
    assert classify_answer_shape(_REGULATORY).primary_shape == regex.primary_shape == "regulatory_knowledge"


def test_planner_promotes_hunt_on_ambiguous_query_with_spl_plan() -> None:
    plan = _promoted_plan("knowledge_retrieval", "spl_artifact", "narration")
    result = classify_answer_shape(_AMBIGUOUS_OT, resource_plan=plan)
    assert result.primary_shape == "hunt"
    assert result.shape_authority == "planner"


def test_regex_wins_on_high_confidence_regulatory_even_with_hunt_plan() -> None:
    plan = _promoted_plan("spl_artifact", "mcp_execution", "narration")
    result = classify_answer_shape(_REGULATORY, resource_plan=plan)
    assert result.primary_shape == "regulatory_knowledge"
    assert result.shape_authority == "regex"


def test_knowledge_only_plan_defers_to_regex_for_ti_advisory() -> None:
    plan = _promoted_plan("knowledge_retrieval", "narration")
    result = classify_answer_shape(_TI, resource_plan=plan)
    assert result.primary_shape == "ti_advisory_mapping"
    assert result.shape_authority in {"regex", "planner_plus_regex"}


def test_mitre_mapping_plan_hints_ti_when_regex_is_weak() -> None:
    plan = _promoted_plan("knowledge_retrieval", "mitre_mapping", "narration")
    result = classify_answer_shape(_AMBIGUOUS_OT, resource_plan=plan)
    assert result.primary_shape == "ti_advisory_mapping"
    assert result.shape_authority == "planner"


def test_shape_hint_mapping_table() -> None:
    assert shape_hint_from_plan_purposes(frozenset({"spl_artifact", "narration"})) == "hunt"
    assert shape_hint_from_plan_purposes(frozenset({"mcp_discovery"})) == "hunt"
    assert shape_hint_from_plan_purposes(frozenset({"knowledge_retrieval"})) is None
    assert shape_hint_from_plan_purposes(frozenset({"mitre_mapping"})) == "ti_advisory_mapping"


def test_plan_purposes_from_resource_plan() -> None:
    purposes = plan_purposes_from_resource_plan(_promoted_plan("spl_artifact", "narration"))
    assert purposes == frozenset({"spl_artifact", "narration"})


def test_scorecard_observed_shape_uses_resource_plan() -> None:
    payload = {
        "evidence_plan": {
            "resource_plan": _promoted_plan("spl_artifact", "narration"),
        }
    }
    assert _observed_answer_shape(_AMBIGUOUS_OT, payload) == "hunt"
    assert _observed_answer_shape(_AMBIGUOUS_OT, {}) == _classify_answer_shape_regex(_AMBIGUOUS_OT).primary_shape


def test_scorecard_shape_corrections_only_when_plan_promoted() -> None:
    """Promoted spl plans correct ambiguous defaults only; regex floor wins on conflict."""
    ambiguous = _AMBIGUOUS_OT
    assert _classify_answer_shape_regex(ambiguous).primary_shape == "hunt"
    assert (
        classify_answer_shape(ambiguous, resource_plan=_promoted_plan("spl_artifact")).primary_shape == "hunt"
    )
    assert (
        classify_answer_shape(_REGULATORY, resource_plan=_promoted_plan("spl_artifact")).primary_shape
        == "regulatory_knowledge"
    )
    probes_path = Path(__file__).resolve().parents[1] / "evals" / "out_of_catalogue_probes.json"
    probes = json.loads(probes_path.read_text(encoding="utf-8"))["probes"]
    for probe in probes:
        query = str(probe["query"])
        regex_shape = _classify_answer_shape_regex(query).primary_shape
        if regex_shape != "hunt":
            promoted_shape = classify_answer_shape(
                query, resource_plan=_promoted_plan("spl_artifact")
            ).primary_shape
            assert promoted_shape == regex_shape
