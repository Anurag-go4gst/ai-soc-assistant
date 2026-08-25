"""P4 PP4 — few-shot and negative-example governance.

Covers mission checks L (comparison stays unsupported) and N (no negative example
conflicts with deterministic architecture).
"""

from __future__ import annotations

import pytest

from app.llm.policy.examples import (
    FEW_SHOT_CATALOG_VERSION,
    FEW_SHOT_EXAMPLES,
    NEGATIVE_EXAMPLE_CATALOG_VERSION,
    NEGATIVE_EXAMPLES,
    SEMANTIC_SHAPES,
    all_few_shot_set_ids,
    all_negative_set_ids,
    few_shot_set,
    negative_set,
    p2_shape_for,
    shape_is_declared_unsupported,
    shape_is_supported,
    unsupported_gap_examples,
)
from app.llm.policy.registry import contracts
from app.llm.policy.role_inventory import role_ids
from app.spl.spl_intent_spec import SUPPORTED_ANALYSIS_SHAPES, UNSUPPORTED_ANALYSIS_SHAPES


def test_catalog_versions_are_declared() -> None:
    assert FEW_SHOT_CATALOG_VERSION == "few_shot_catalog_v1"
    assert NEGATIVE_EXAMPLE_CATALOG_VERSION == "negative_example_catalog_v1"


# --- required metadata ------------------------------------------------------


@pytest.mark.parametrize("example", FEW_SHOT_EXAMPLES, ids=lambda e: e.example_id)
def test_few_shot_examples_carry_required_metadata(example) -> None:
    for field in ("example_id", "role_id", "purpose", "input_shape", "expected_output_shape",
                  "authority_boundary", "version", "activation", "set_id"):
        assert str(getattr(example, field)).strip(), f"{example.example_id}.{field} blank"


@pytest.mark.parametrize("example", NEGATIVE_EXAMPLES, ids=lambda e: e.example_id)
def test_negative_examples_carry_required_metadata(example) -> None:
    for field in ("example_id", "role_id", "purpose", "failure_mode", "corrected_behaviour",
                  "enforcing_rule", "version", "activation", "set_id"):
        assert str(getattr(example, field)).strip(), f"{example.example_id}.{field} blank"


def test_example_ids_are_unique() -> None:
    ids = [e.example_id for e in FEW_SHOT_EXAMPLES] + [e.example_id for e in NEGATIVE_EXAMPLES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "role_id",
    sorted({e.role_id for e in FEW_SHOT_EXAMPLES} | {e.role_id for e in NEGATIVE_EXAMPLES}),
)
def test_examples_reference_a_real_role(role_id: str) -> None:
    assert role_id in role_ids()


# --- examples teach shapes, not literal customer queries --------------------


@pytest.mark.parametrize("example", FEW_SHOT_EXAMPLES, ids=lambda e: e.example_id)
def test_few_shot_input_shape_describes_a_class_not_one_query(example) -> None:
    """A memorised customer question would show up as a quoted literal query."""
    shape = example.input_shape
    assert not shape.strip().endswith("?"), (
        f"{example.example_id} looks like a literal question, not a request class"
    )
    assert len(shape) > 20, f"{example.example_id} input_shape is too thin to be a class"


# --- L: comparison remains a product gap ------------------------------------


def test_shape_support_is_read_from_p2_not_asserted_locally() -> None:
    for shape in SEMANTIC_SHAPES:
        p2 = p2_shape_for(shape)
        assert shape_is_supported(shape) == (p2 in SUPPORTED_ANALYSIS_SHAPES)
        assert shape_is_declared_unsupported(shape) == (p2 in UNSUPPORTED_ANALYSIS_SHAPES)


def test_comparison_is_the_declared_unsupported_shape() -> None:
    assert shape_is_declared_unsupported("COMPARISON") is True
    assert shape_is_supported("COMPARISON") is False


def test_comparison_few_shot_is_marked_as_an_unsupported_gap() -> None:
    gaps = {e.example_id for e in unsupported_gap_examples()}
    assert gaps == {"fs.spl.comparison"}


def test_comparison_example_is_never_served_as_active() -> None:
    """Serving it would teach the model that a product gap is a feature."""
    active_shapes = {e.semantic_shape for e in few_shot_set("fewshot:spl_shape_v1")}
    assert "COMPARISON" not in active_shapes


def test_every_supported_shape_has_an_active_few_shot() -> None:
    active_shapes = {e.semantic_shape for e in few_shot_set("fewshot:spl_shape_v1")}
    for shape in SEMANTIC_SHAPES:
        if shape_is_supported(shape):
            assert shape in active_shapes, f"supported shape {shape} has no active few-shot"


def test_no_active_asset_claims_comparison_support() -> None:
    for example in FEW_SHOT_EXAMPLES:
        if example.activation == "ACTIVE":
            assert "comparison" not in example.expected_output_shape.lower()


# --- N: negative examples name real deterministic machinery -----------------


@pytest.mark.parametrize("example", NEGATIVE_EXAMPLES, ids=lambda e: e.example_id)
def test_negative_examples_name_an_enforcing_rule(example) -> None:
    """An example whose rule does not exist is a story, not a guardrail."""
    rule = example.enforcing_rule
    assert len(rule) > 15, f"{example.example_id} enforcing_rule is too vague: {rule}"


@pytest.mark.parametrize("example", NEGATIVE_EXAMPLES, ids=lambda e: e.example_id)
def test_negative_examples_never_loosen_a_check(example) -> None:
    """A negative example teaches rejection; it must not permit anything."""
    corrected = example.corrected_behaviour.lower()
    for loosening in ("may ignore", "can skip", "is allowed to bypass", "override the validator"):
        assert loosening not in corrected, f"{example.example_id} loosens a check"


def test_required_spl_negative_coverage_is_present() -> None:
    """The specific failure classes the plan named must each own an example."""
    ids = {e.example_id for e in negative_set("negative:spl_semantic_v1")}
    for required in (
        "neg.spl.semantic_noun_literalised",
        "neg.spl.horizon_window_confused",
        "neg.spl.wrong_grouping_entity",
        "neg.spl.missing_event_population",
        "neg.spl.lost_sequence_order",
        "neg.spl.lost_max_gap",
        "neg.spl.trend_became_alert",
        "neg.spl.invented_threshold",
        "neg.spl.arbitrary_head_100",
        "neg.spl.unused_normalized_alias",
        "neg.spl.candidate_treated_executable",
    ):
        assert required in ids, f"missing required SPL negative example: {required}"


def test_required_cross_role_negative_coverage_is_present() -> None:
    ids = {e.example_id for e in NEGATIVE_EXAMPLES}
    for required in (
        "neg.evidence.planned_as_obtained",
        "neg.evidence.failed_call_as_evidence",
        "neg.evidence.fabricated_provenance",
        "neg.authority.override_deterministic",
        "neg.planning.delta_widens_scope",
        "neg.planning.self_authorized_tool_call",
        "neg.composer.changed_verdict",
    ):
        assert required in ids, f"missing required cross-role negative example: {required}"


# --- contracts and catalogues agree -----------------------------------------


def test_every_contract_few_shot_set_exists_or_is_justified() -> None:
    known = set(all_few_shot_set_ids())
    for contract in contracts():
        ref = contract.few_shot_set
        if ref.startswith("NOT_APPLICABLE"):
            continue
        assert ref in known, f"{contract.role_id} references unknown few-shot set {ref}"


def test_every_contract_negative_set_exists() -> None:
    known = set(all_negative_set_ids())
    for contract in contracts():
        ref = contract.negative_example_set
        if ref.startswith("NOT_APPLICABLE"):
            continue
        assert ref in known, f"{contract.role_id} references unknown negative set {ref}"


def test_accessors_return_canonical_order() -> None:
    """Ordering is part of the stable-prefix hash, so it must be deterministic."""
    for set_id in all_few_shot_set_ids():
        served = few_shot_set(set_id)
        assert list(served) == sorted(served, key=lambda e: e.example_id)
    for set_id in all_negative_set_ids():
        served = negative_set(set_id)
        assert list(served) == sorted(served, key=lambda e: e.example_id)


def test_accessors_exclude_non_active_assets() -> None:
    for set_id in all_few_shot_set_ids():
        assert all(e.activation == "ACTIVE" for e in few_shot_set(set_id))
    for set_id in all_negative_set_ids():
        assert all(e.activation == "ACTIVE" for e in negative_set(set_id))
