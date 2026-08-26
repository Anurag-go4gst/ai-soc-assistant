"""semantic_t4 promotion pins: pointer-style activation with frozen evaluated bytes."""

from __future__ import annotations

from app.chat.semantic_t4_understanding import _SEMANTIC_T4_SCHEMA
from app.llm.policy.candidates import (
    CANDIDATES,
    PROMOTED_TO_ACTIVE,
    candidate_t4_response_schema,
    extra_few_shots_for_live,
    live_system_prompt,
    promoted_for,
    promoted_stable_prefix_hash,
    promoted_system_instruction,
)
from app.llm.policy.eval_arm import use_prompt_eval_arm
from app.llm.policy.registry import contract_for
from app.llm.policy.request_provenance import hash_prompt_text

ROLE = "semantic_t4"
MEASURED_CANDIDATE_INSTRUCTION_SHA = (
    "b14234b8e7de9ee9d5971053e2b17519401d9f4d741b99ce634edf386d5d2424"
)
MEASURED_CANDIDATE_PREFIX_HASH = "b335f4c74583c6db24c62892b97d2ea929381ed09f20129fd803697c2e979a47"


def test_t4_promoted_text_is_the_measured_candidate_bytes() -> None:
    text = promoted_system_instruction(ROLE)
    assert text is not None
    assert text == CANDIDATES[ROLE].system_instruction
    assert hash_prompt_text(text) == MEASURED_CANDIDATE_INSTRUCTION_SHA


def test_t4_promoted_identity_and_rollback_are_recorded() -> None:
    promoted = promoted_for(ROLE)
    assert promoted is not None
    assert promoted.template_id == contract_for(ROLE).prompt_template_id == "tmpl.semantic_t4"
    assert promoted.version == "1.1.0"
    assert promoted.rollback_template_id == "tmpl.semantic_t4"
    assert promoted.rollback_version == "1.0.0"
    assert promoted.promoted_from_template_id == "tmpl.semantic_t4.candidate"
    assert promoted.promoted_from_version == "1.4.0-candidate"


def test_t4_promotion_keeps_candidate_schema_and_few_shot_overlay() -> None:
    promoted = promoted_for(ROLE)
    assert promoted is not None
    assert promoted.use_candidate_t4_schema is True
    assert promoted.use_candidate_few_shots is True

    schema = candidate_t4_response_schema(_SEMANTIC_T4_SCHEMA)
    keys = list(schema["properties"])
    assert keys.index("clarification_required") < keys.index("normalized_goal")
    assert "ambiguity_state" not in keys
    assert "confidence" not in keys
    assert len(extra_few_shots_for_live(ROLE)) == len(CANDIDATES[ROLE].extra_few_shots) == 1


def test_t4_promoted_role_serves_promoted_text_in_both_arms() -> None:
    expected = promoted_system_instruction(ROLE)
    for arm in ("active", "candidate"):
        with use_prompt_eval_arm(arm):
            assert live_system_prompt(ROLE, "OLD_ACTIVE_MUST_NOT_WIN") == expected


def test_t4_promoted_prefix_hash_matches_measured_candidate() -> None:
    # Prefix hash changes with promoted ACTIVE identity (template/version) even
    # when instruction bytes are identical to the measured candidate.
    promoted_hash = promoted_stable_prefix_hash(ROLE)
    assert len(promoted_hash) == 64
    assert promoted_hash != MEASURED_CANDIDATE_PREFIX_HASH


def test_t4_and_planner_are_promoted_spl_is_not() -> None:
    assert {"semantic_t4", "investigation_planner"} <= set(PROMOTED_TO_ACTIVE)
    assert "spl_advisory_generator" not in PROMOTED_TO_ACTIVE
