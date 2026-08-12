"""Schema pins for the routing truth set (Plan 4 R1.1).

The point of these tests is that the schema has teeth *before* any real row is
written. A deliberately malformed fixture must fail; if it passes, the schema is
decoration and the benchmark it guards is worthless.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evals.routing_truth_set import (
    CAPABILITIES,
    CONTRACT_GATED_CAPABILITIES,
    INTENT_FAMILIES,
    STAGE_CORPUS,
    STAGE_LABELED,
    answer_shapes,
    capability_consistency,
    file_sha256,
    validate_row,
    validate_rows,
)
from contracts.skill_enum import SKILL_ENUM

REPO_ROOT = Path(__file__).resolve().parents[3]
TRUTH_SET_PATH = REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json"
CONTRACT_DOC = REPO_ROOT / "docs" / "evals" / "ROUTING_TRUTH_SET_CONTRACT.md"


def _valid_row() -> dict:
    return {
        "row_id": "rt.example.001",
        "query": "Which hosts contacted known malicious IPs today?",
        "source": "question_runtime_map_v1.json:q0.q004",
        "expected_intent_family": "spl_generation_only",
        "expected_answer_shape": "hunt",
        "acceptable_skills": ["attack_discovery", "spl_generation"],
        "required_capabilities": ["spl"],
        "forbidden_capabilities": [],
        "ambiguous": False,
        "label_confidence": "high",
        "rationale": "IOC-correlation hunt over live data; needs a review-only SPL draft.",
        "labeled_without_registry_hint": True,
    }


# --------------------------------------------------------------------------- #
# Failing-first: the malformed fixture the plan names must be rejected.
# --------------------------------------------------------------------------- #


def test_malformed_fixture_row_is_rejected() -> None:
    """The exact malformed row Plan 4 R1.1 specifies must fail validation."""
    malformed = _valid_row()
    del malformed["rationale"]
    malformed["acceptable_skills"] = []
    malformed["labeled_without_registry_hint"] = False

    result = validate_row(malformed, stage=STAGE_LABELED)

    assert not result.ok
    joined = " | ".join(result.errors)
    assert "rationale" in joined
    assert "acceptable_skills" in joined
    assert "labeled_without_registry_hint" in joined


def test_valid_row_passes() -> None:
    assert validate_row(_valid_row(), stage=STAGE_LABELED).ok


@pytest.mark.parametrize(
    "mutation, expected_fragment",
    [
        ({"expected_intent_family": "totally_invented_family"}, "expected_intent_family"),
        ({"expected_answer_shape": "not_a_shape"}, "expected_answer_shape"),
        ({"acceptable_skills": ["attack_discovery", "attack_discovery"]}, "duplicate"),
        ({"acceptable_skills": ["not_a_skill"]}, "not a routable skill"),
        ({"required_capabilities": ["telepathy"]}, "required_capabilities"),
        ({"label_confidence": "very_sure"}, "label_confidence"),
        ({"rationale": "   "}, "rationale"),
        ({"ambiguous": "yes"}, "ambiguous"),
        ({"required_capabilities": ["spl"], "forbidden_capabilities": ["spl"]}, "contradict"),
    ],
)
def test_single_field_mutations_are_rejected(mutation: dict, expected_fragment: str) -> None:
    row = _valid_row()
    row.update(mutation)
    result = validate_row(row, stage=STAGE_LABELED)
    assert not result.ok
    assert expected_fragment in " | ".join(result.errors)


def test_ambiguous_row_must_record_two_readings() -> None:
    row = _valid_row()
    row["ambiguous"] = True
    row["label_confidence"] = "low"
    assert not validate_row(row, stage=STAGE_LABELED).ok

    row["candidate_readings"] = [
        "notable-index lookup is an alert_summary capability",
        "notable-index lookup is live-data retrieval and belongs to a hunt skill",
    ]
    assert validate_row(row, stage=STAGE_LABELED).ok


# --------------------------------------------------------------------------- #
# Staging: corpus rows must not arrive pre-labelled.
# --------------------------------------------------------------------------- #


def test_corpus_stage_rejects_pre_labelled_rows() -> None:
    result = validate_row(_valid_row(), stage=STAGE_CORPUS)
    assert not result.ok
    assert "labels belong to R1.3" in " | ".join(result.errors)


def test_corpus_stage_accepts_identity_only_rows() -> None:
    row = {"row_id": "rt.example.002", "query": "Show me the DNS beaconing checklist.", "source": "bank:x"}
    assert validate_row(row, stage=STAGE_CORPUS).ok


def test_labeled_stage_rejects_an_unlabelled_corpus_row() -> None:
    """Validating a corpus file as `labeled` is the proof R1.3 actually ran."""
    row = {"row_id": "rt.example.003", "query": "Which hosts show beaconing?", "source": "bank:x"}
    assert not validate_row(row, stage=STAGE_LABELED).ok


def test_duplicate_row_ids_are_rejected() -> None:
    rows = [_valid_row(), _valid_row()]
    results = validate_rows(rows, stage=STAGE_LABELED)
    assert any("duplicate row_id" in " | ".join(r.errors) for r in results)


# --------------------------------------------------------------------------- #
# Vocabularies are pinned to the runtime, not copied and left to rot.
# --------------------------------------------------------------------------- #


def test_intent_families_all_exist_in_the_live_classifier() -> None:
    """A label may never name a family the runtime cannot produce."""
    source = (REPO_ROOT / "backend" / "app" / "chat" / "intent_classifier.py").read_text(encoding="utf-8")
    missing = sorted(f for f in INTENT_FAMILIES if f'intent_family="{f}"' not in source)
    assert missing == [], f"families not produced by intent_classifier.py: {missing}"


def test_answer_shapes_track_the_router_vocabulary() -> None:
    from typing import get_args

    from app.chat.answer_shape_router import AnswerShape

    assert set(get_args(AnswerShape)).issubset(answer_shapes())
    assert "clarification" in answer_shapes()


def test_acceptable_skills_vocabulary_is_the_skill_enum() -> None:
    assert set(SKILL_ENUM) == {
        "alert_summary",
        "spl_generation",
        "attack_discovery",
        "knowledge_recall",
        "guided_investigation",
    }


# --------------------------------------------------------------------------- #
# The capability-consistency invariant, and its independence from route verdict.
# --------------------------------------------------------------------------- #


def test_capability_inconsistency_is_independent_of_route_correctness() -> None:
    """The D1 defect class: an accepted route that still denies a required capability.

    `knowledge_recall` may legitimately be in `acceptable_skills` for a row whose
    label requires SPL — the route is then `route_ok` — yet the contract denies
    SPL, so the row must still be flagged `capability_inconsistent`.
    """
    row = _valid_row()
    row["acceptable_skills"] = ["knowledge_recall"]

    route_ok = "knowledge_recall" in row["acceptable_skills"]
    consistent, denied = capability_consistency(
        selected_skill="knowledge_recall",
        required_capabilities=row["required_capabilities"],
    )

    assert route_ok is True
    assert consistent is False
    assert denied == frozenset({"spl"})


def test_capability_consistency_passes_for_a_permitting_skill() -> None:
    consistent, denied = capability_consistency(
        selected_skill="attack_discovery", required_capabilities=["spl", "mcp"]
    )
    assert consistent is True
    assert denied == frozenset()


def test_capability_consistency_flags_mcp_denied_by_contract() -> None:
    consistent, denied = capability_consistency(
        selected_skill="spl_generation", required_capabilities=["spl", "mcp"]
    )
    assert consistent is False
    assert denied == frozenset({"mcp"})


def test_rag_is_labelled_but_not_contract_gated() -> None:
    """RAG has no permit key; gating on it would require a second capability table."""
    assert "rag" in CAPABILITIES
    assert "rag" not in CONTRACT_GATED_CAPABILITIES
    consistent, denied = capability_consistency(
        selected_skill="knowledge_recall", required_capabilities=["rag"]
    )
    assert consistent is True
    assert denied == frozenset()


def test_capability_authority_is_not_reimplemented() -> None:
    """One capability implementation, as Plan 3 B2 established."""
    source = (REPO_ROOT / "backend" / "app" / "evals" / "routing_truth_set.py").read_text(encoding="utf-8")
    assert "_contract_grants" in source
    # Prose may name the table (the module explains why it does not own it); a
    # *definition* or a re-read of contract internals is the actual violation.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert "_PURPOSE_TOOL_HINTS =" not in code, "the permit hint table must not be redefined here"
    assert "blocked_tools" not in code, "contract internals must not be re-read here"
    assert "default_workflow" not in code, "contract internals must not be re-read here"


# --------------------------------------------------------------------------- #
# Order commitment.
# --------------------------------------------------------------------------- #


def test_file_sha256_changes_when_a_label_changes(tmp_path: Path) -> None:
    path = tmp_path / "rows.json"
    path.write_text(json.dumps({"rows": [_valid_row()]}), encoding="utf-8")
    before = file_sha256(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rows"][0]["label_confidence"] = "low"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert file_sha256(path) != before


# --------------------------------------------------------------------------- #
# Real artifacts, once they exist. Skipped until their owning items run.
# --------------------------------------------------------------------------- #


def test_contract_doc_states_the_invariant_verbatim() -> None:
    if not CONTRACT_DOC.is_file():
        pytest.skip("contract doc not written yet (R1.1)")
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    assert "capability_inconsistent" in text
    assert "even if the answer would still match an answer golden" in text


def test_committed_truth_set_validates() -> None:
    if not TRUTH_SET_PATH.is_file():
        pytest.skip("truth set not assembled yet (R1.2 / R1.3)")
    payload = json.loads(TRUTH_SET_PATH.read_text(encoding="utf-8"))
    stage = payload.get("stage", STAGE_LABELED)
    failures = [r for r in validate_rows(payload["rows"], stage=stage) if not r.ok]
    assert failures == [], "\n".join(f"{r.row_id}: {r.errors}" for r in failures)
