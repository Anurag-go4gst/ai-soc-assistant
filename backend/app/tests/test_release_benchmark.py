"""Corpus → release benchmark: builder, §4.3 validator, §4.4 scorer scaffold."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _REPO / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


builder = _load("build_labeled_release_v1")
validator = _load("validate_release_bank")
scorer = _load("score_release_bank")


def test_builder_emits_100_schema_rows() -> None:
    out = builder.build()
    assert out["row_count"] == 100
    row = out["rows"][0]
    for f in validator.REQUIRED_FIELDS:
        assert f in row
    # expert fields intentionally unfilled, flagged
    assert row["must_include"] == []
    assert row["label_status"] == "needs_expert"


def test_validator_passes_on_built_bank() -> None:
    out = builder.build()
    assert validator.validate(out) == []


def test_validator_flags_bad_enum_and_dupes() -> None:
    bad = {
        "rows": [
            {**_min_row(id="a"), "tier": "BOGUS"},
            {**_min_row(id="a")},  # dup id + dup question
        ]
    }
    failures = validator.validate(bad)
    assert any("bad tier" in f for f in failures)
    assert any("duplicate id" in f for f in failures)


def test_validator_requires_boundary_safety_seed() -> None:
    row = {**_min_row(id="b"), "tier": "boundary", "must_not_claim": []}
    failures = validator.validate({"rows": [row]})
    assert any("missing must_not_claim safety seed" in f for f in failures)


def test_scorer_layer1_blocks_unsafe_execution_on_boundary() -> None:
    label = {**_min_row(id="c"), "tier": "boundary", "expected_artifacts": [], "label_status": "needs_expert"}
    answer = {"http_status": 200, "trace_id": "t", "executed": True, "artifacts": [], "answer_text": "ok"}
    scored = scorer.score_row(label, answer)
    assert scored["layer1_hard_gates"]["checks"]["no_unsafe_execution"] is False
    assert scored["blocking_failure"] is True


def test_scorer_safety_violation_detected() -> None:
    label = {**_min_row(id="d"), "must_not_claim": ["ran the query"], "expected_artifacts": []}
    answer = {"http_status": 200, "trace_id": "t", "artifacts": [], "answer_text": "I ran the query and here are results"}
    scored = scorer.score_row(label, answer)
    assert scored["layer2_rubric"]["safety_pass"] is False
    assert scored["blocking_failure"] is True


def test_scorer_must_include_deferred_when_no_expert_labels() -> None:
    label = {**_min_row(id="e"), "expected_artifacts": [], "label_status": "needs_expert", "must_include": []}
    answer = {"http_status": 200, "trace_id": "t", "artifacts": [], "answer_text": "anything"}
    scored = scorer.score_row(label, answer)
    assert scored["layer2_rubric"]["must_include_coverage"] is None
    assert scored["release_gating"] is False


def test_scorer_must_include_scored_when_expert_present() -> None:
    label = {
        **_min_row(id="f"), "expected_artifacts": [], "label_status": "expert_signed",
        "must_include": ["failed login", "source ip"], "must_not_claim": [],
    }
    answer = {"http_status": 200, "trace_id": "t", "artifacts": [],
              "answer_text": "review failed login counts grouped by source ip"}
    scored = scorer.score_row(label, answer)
    assert scored["layer2_rubric"]["must_include_coverage"] == 1.0
    assert scored["release_gating"] is True


def _min_row(*, id: str) -> dict:
    return {
        "id": id, "category": "soc", "tier": "T1", "question": f"q for {id}",
        "primary_objective": "do thing", "expected_answer_shape": "hunt",
        "acceptable_skills": ["attack_discovery"], "required_evidence_legs": [],
        "expected_artifacts": ["spl"], "must_include": [], "must_not_claim": ["ran the query"],
        "expected_hil": "none", "latency_class": "deterministic", "authority_source": "registry",
    }
