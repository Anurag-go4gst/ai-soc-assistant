"""investigation_planner promotion: a pointer, not an edit.

The frozen 16-row bank (bank_hash 5f78ccbe…) measured ACTIVE producing an
`investigation_plan` wrapper key that `additionalProperties: false` rejects,
plus missing required `hypotheses`/`evidence_needed` -- planner schema 0/1.
The candidate produced a contract-valid proposal, 1/1, with zero authority
violations. Evidence: docs/evals/p8_l3/ab_v131_comparison.json.

These pins exist so the promotion cannot silently drift into an edit: the text
now serving must be byte-identical to the text that was measured, the candidate
record must survive as evidence, and rollback must stay one bounded deletion.
"""

from __future__ import annotations

from app.llm.policy.candidates import (
    CANDIDATES,
    PROMOTED_TO_ACTIVE,
    live_system_prompt,
    promoted_for,
    promoted_stable_prefix_hash,
    promoted_system_instruction,
)
from app.llm.policy.eval_arm import use_prompt_eval_arm
from app.llm.policy.registry import contract_for
from app.llm.policy.request_provenance import (
    hash_prompt_text,
    reset_prompt_provenance,
    selected_prompt_for_role,
)

ROLE = "investigation_planner"

#: The candidate instruction hash the frozen A/B actually measured.
MEASURED_CANDIDATE_INSTRUCTION_SHA = (
    "43a5367e2d9362c334837f4761eb8f9d1e8ea89216346230b33bdaad5df5f3f0"
)


def test_promoted_text_is_the_text_the_ab_measured() -> None:
    """Promotion serves the evaluated bytes, not a re-typed copy of them."""
    text = promoted_system_instruction(ROLE)
    assert text is not None
    assert hash_prompt_text(text) == MEASURED_CANDIDATE_INSTRUCTION_SHA
    # Sourced from the candidate record, so the two can never diverge.
    assert text == CANDIDATES[ROLE].system_instruction


def test_promotion_does_not_mutate_the_candidate_record() -> None:
    """The candidate stays on file as historical evidence of what was measured."""
    cand = CANDIDATES[ROLE]
    assert cand.template_id == "tmpl.investigation_planner.candidate"
    assert cand.version == "1.3.0-candidate"
    assert cand.status == "CANDIDATE"


def test_promoted_identity_is_an_active_version_not_a_candidate_one() -> None:
    promoted = promoted_for(ROLE)
    assert promoted is not None
    assert promoted.template_id == contract_for(ROLE).prompt_template_id
    assert not promoted.version.endswith("-candidate")
    assert promoted.version != promoted.rollback_version
    assert promoted.promoted_from_version == "1.3.0-candidate"


def test_rollback_target_is_recorded_and_is_the_previous_active() -> None:
    """studio_config refuses an activation with no rollback target; record one."""
    promoted = promoted_for(ROLE)
    assert promoted is not None
    active = contract_for(ROLE)
    assert promoted.rollback_template_id == active.prompt_template_id
    assert promoted.rollback_version == active.prompt_version == "1.0.0"


def test_promoted_role_serves_promoted_text_in_both_arms() -> None:
    """Once promoted there is no second arm; reporting one would fake a delta."""
    expected = promoted_system_instruction(ROLE)
    for arm in ("active", "candidate"):
        with use_prompt_eval_arm(arm):
            assert live_system_prompt(ROLE, "OLD_ACTIVE_MUST_NOT_WIN") == expected


def test_promoted_selection_is_recorded_as_active_provenance() -> None:
    reset_prompt_provenance()
    with use_prompt_eval_arm("active"):
        text = live_system_prompt(ROLE, "OLD_ACTIVE_MUST_NOT_WIN")
    selected = selected_prompt_for_role(ROLE)
    assert selected is not None
    assert selected["status"] == "ACTIVE"
    assert selected["template_id"] == "tmpl.investigation_planner"
    assert selected["version"] == "1.1.0"
    assert selected["instruction_sha256"] == hash_prompt_text(text)
    assert selected["prefix_hash"] == promoted_stable_prefix_hash(ROLE)


def test_planner_remains_promoted_and_spl_stays_unpromoted() -> None:
    """SPL stays unpromoted; planner promotion remains ACTIVE."""
    assert "investigation_planner" in PROMOTED_TO_ACTIVE
    assert "spl_advisory_generator" not in PROMOTED_TO_ACTIVE


def test_unpromoted_roles_keep_the_two_arm_behaviour() -> None:
    for role in ("spl_advisory_generator",):
        assert role not in PROMOTED_TO_ACTIVE
        with use_prompt_eval_arm("active"):
            assert live_system_prompt(role, "ACTIVE_TEXT") == "ACTIVE_TEXT"
        with use_prompt_eval_arm("candidate"):
            assert live_system_prompt(role, "ACTIVE_TEXT") == CANDIDATES[role].system_instruction
