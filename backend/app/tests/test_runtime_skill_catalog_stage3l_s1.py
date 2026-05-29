from __future__ import annotations

from app.routing.runtime_skill_catalog import get_runtime_skill_catalog

GOVERNANCE_TOKENS = {
    "no_spl_execution",
    "candidate_plan_only",
    "deterministic_validation_required",
    "no_model_authored_threshold_policy",
    "no_llm_authored_detection_spl",
    "no_write_actions",
    "no_external_threat_intel_call",
    "local_lookup_only",
    "no_post_enrichment",
    "no_behavioral_binding",
    "no_action_chain",
    "read_only",
    "approved_context_only",
    "max_depth_2",
    "no_nested_multi_signal",
    "no_nested_sub_invocations",
    "entity_must_be_explicit",
}


def test_runtime_skill_catalog_governance_constraints() -> None:
    catalog = get_runtime_skill_catalog()
    for skill_id, contract in catalog.items():
        constraints = contract.get("governance_constraints")
        assert isinstance(constraints, list) and constraints, f"{skill_id} missing governance_constraints"
        for token in constraints:
            assert token in GOVERNANCE_TOKENS, f"{skill_id} unknown governance token: {token}"


def test_runtime_skill_catalog_examples_and_non_examples() -> None:
    catalog = get_runtime_skill_catalog()
    for skill_id, contract in catalog.items():
        examples = contract.get("examples")
        non_examples = contract.get("non_examples")
        assert isinstance(examples, list) and any(str(item).strip() for item in examples), skill_id
        assert isinstance(non_examples, list) and any(str(item).strip() for item in non_examples), skill_id


def test_runtime_skill_catalog_allowed_operation_types_non_empty() -> None:
    catalog = get_runtime_skill_catalog()
    for skill_id, contract in catalog.items():
        allowed = contract.get("allowed_operation_types")
        assert isinstance(allowed, list) and allowed, skill_id
