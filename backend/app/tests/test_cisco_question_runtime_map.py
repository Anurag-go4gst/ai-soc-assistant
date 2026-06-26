"""Cisco precision-layer runtime-map registration tests (intent cascade §4).

Asserts the 50 Appendix-A Cisco questions are registered in the SEPARATE Cisco
runtime map (never merged into the 105 map), that every row carries a non-empty
pattern_type + routing skill, that there is no id/question collision with the
105 registry, and that the loader precedence is correct: a 105 query still
returns its 105 row, and a Cisco query returns the Cisco row only after a 105
miss.
"""

from __future__ import annotations

import re

from app.coverage.question_runtime_map import (
    list_cisco_question_runtime_entries,
    list_question_runtime_entries,
    match_question_runtime_entry,
)

# Verbatim Appendix-A ids (cisco.<segment>.NNN). Stable for regression.
APPENDIX_A_IDS = (
    [f"cisco.perim.{n:03d}" for n in range(1, 11)]
    + [f"cisco.identity.{n:03d}" for n in range(11, 21)]
    + [f"cisco.ot.{n:03d}" for n in range(21, 31)]
    + [f"cisco.compliance.{n:03d}" for n in range(31, 41)]
    + [f"cisco.endpoint.{n:03d}" for n in range(41, 51)]
)

_VALID_ROUTER_SKILLS = {
    "alert_summary",
    "spl_generation",
    "attack_discovery",
    "knowledge_recall",
    "guided_investigation",
}

_ID_RE = re.compile(r"^cisco\.[a-z]+\.\d{3}$")


def _cisco_by_id() -> dict[str, dict]:
    return {entry["question_id"]: entry for entry in list_cisco_question_runtime_entries()}


def test_all_50_appendix_a_ids_registered() -> None:
    by_id = _cisco_by_id()
    assert len(APPENDIX_A_IDS) == 50
    missing = [qid for qid in APPENDIX_A_IDS if qid not in by_id]
    assert missing == [], f"Cisco ids missing from runtime map: {missing}"
    assert len(by_id) == 50, f"expected 50 unique Cisco entries, got {len(by_id)}"


def test_every_entry_has_pattern_type_and_skill() -> None:
    for entry in list_cisco_question_runtime_entries():
        qid = entry.get("question_id")
        assert _ID_RE.match(str(qid)), f"bad id format: {qid}"
        pattern_type = entry.get("pattern_type")
        assert isinstance(pattern_type, str) and pattern_type.strip(), f"empty pattern_type for {qid}"
        hint = entry.get("legacy_router_intent_hint")
        assert hint in _VALID_ROUTER_SKILLS, f"invalid router skill {hint!r} for {qid}"
        assert isinstance(entry.get("proposed_primary_skill"), str) and entry["proposed_primary_skill"].strip(), qid
        assert isinstance(entry.get("question"), str) and entry["question"].strip(), qid


def test_no_id_collision_with_105_map() -> None:
    cisco_ids = {entry["question_id"] for entry in list_cisco_question_runtime_entries()}
    cisco_refs = {entry.get("question_ref") for entry in list_cisco_question_runtime_entries()}
    map_105_refs = {entry.get("question_ref") for entry in list_question_runtime_entries()}
    assert cisco_ids.isdisjoint(map_105_refs), "Cisco question_id collides with a 105 question_ref"
    assert cisco_refs.isdisjoint(map_105_refs), "Cisco question_ref collides with a 105 question_ref"


def test_no_question_text_collision_with_105_map() -> None:
    def _norm(text: str) -> str:
        return " ".join(text.strip().lower().split())

    map_105_questions = {_norm(e["question"]) for e in list_question_runtime_entries() if e.get("question")}
    for entry in list_cisco_question_runtime_entries():
        assert _norm(entry["question"]) not in map_105_questions, f"Cisco question collides with 105: {entry['question_id']}"


def test_loader_precedence_cisco_after_105() -> None:
    # A Cisco-id query resolves to the Cisco entry (105 miss → Cisco fall-through).
    cisco_q = "Show all outbound firewall connections originating from the Industrial DMZ to foreign geographic locations."
    cisco_match = match_question_runtime_entry(cisco_q)
    assert cisco_match is not None
    assert cisco_match.get("question_id") == "cisco.perim.006"
    assert cisco_match.get("registry_source") == "cisco_question_runtime_map_v1"

    # A 105 query still returns its 105 row, not a Cisco row (105 precedence).
    first_105 = list_question_runtime_entries()[0]
    match_105 = match_question_runtime_entry(first_105["question"])
    assert match_105 is not None
    assert match_105.get("question_ref") == first_105.get("question_ref")
    assert match_105.get("registry_source") != "cisco_question_runtime_map_v1"


def test_metadata_questions_labelled_environment_hygiene() -> None:
    # Q44-48 are the metadata/env-hygiene rows; they must NOT be routed to a hunt
    # pattern (the env_hygiene path is not built yet — labelled, not broken-routed).
    by_id = _cisco_by_id()
    for qid in [f"cisco.endpoint.{n:03d}" for n in range(44, 49)]:
        assert by_id[qid]["pattern_type"] == "environment_hygiene", qid
        assert by_id[qid]["legacy_router_intent_hint"] == "knowledge_recall", qid
