"""P8-A — candidate prompts are registered separately and never become production default."""

from __future__ import annotations

from app.chat.semantic_t4_understanding import (
    _SEMANTIC_T4_SYSTEM_PROMPT,
    _build_semantic_t4_user_prompt,
)
from app.chat.resolved_query_builder import build_resolved_query_contract
from app.llm.policy.candidates import (
    CANDIDATES,
    candidate_for,
    candidate_stable_prefix_hash,
    extra_few_shots_for_live,
    live_system_prompt,
)
from app.llm.policy.eval_arm import prompt_eval_arm, use_prompt_eval_arm
from app.llm.policy.evaluation import contract_for_role
from app.llm.policy.role_inventory import blocked_role_ids
from app.llm.sidecar_clients import _REASONING_ALLOWED_ROLES, _system_prompt_for_role
from app.spl.llm_plan_compiler import _plan_system_prompt

_CANDIDATE_ROLES = ("semantic_t4", "spl_advisory_generator", "investigation_planner")
_ACTIVE_HASHES = {
    "semantic_t4": "6ccdbaee5c9d0779672a9b879581de8a5a2498ac28177f9a61cfb77acb905592",
    "spl_advisory_generator": "6f8380e028ca4b4d4a79c379028f13ccb853ac6264333a1591642cdbb109a1fb",
    "investigation_planner": "a19fb35608a25aa9dd2aa3d4a865a685d7ed5ac0473abdff91a0f6762c6c9df1",
}


def test_production_eval_arm_defaults_to_active() -> None:
    assert prompt_eval_arm() == "active"


def test_active_live_prompts_are_unchanged_on_default_arm() -> None:
    assert live_system_prompt("semantic_t4", _SEMANTIC_T4_SYSTEM_PROMPT) == _SEMANTIC_T4_SYSTEM_PROMPT
    assert live_system_prompt("spl_advisory_generator", _plan_system_prompt()) == _plan_system_prompt()
    from app.llm.prompts import PROMPT_CONTRACTS

    planner = str(PROMPT_CONTRACTS["investigation_planner"]["system_instruction"])
    assert _system_prompt_for_role("investigation_planner", None) == planner


def test_candidates_are_registered_separately_with_distinct_identity() -> None:
    assert set(CANDIDATES) == set(_CANDIDATE_ROLES)
    for role_id in _CANDIDATE_ROLES:
        contract = contract_for_role(role_id)
        cand = candidate_for(role_id)
        assert cand is not None
        assert cand.status == "CANDIDATE"
        assert cand.template_id != contract.active.template_id
        assert cand.version != contract.active.version
        cand_hash = candidate_stable_prefix_hash(role_id)
        assert cand_hash != contract.active.stable_prefix_hash
        assert contract.active.stable_prefix_hash == _ACTIVE_HASHES[role_id]
        assert len(cand_hash) == 64
        assert contract.candidate is None
        assert contract.eval_status == "NOT_RUN_LIVE"
        assert contract.can_activate() == (False, "no_candidate_prompt")


def test_shape_advisor_has_no_candidate() -> None:
    assert candidate_for("shape_advisor") is None
    contract = contract_for_role("shape_advisor")
    assert contract.candidate is None


def test_blocked_reasoners_remain_blocked_and_have_no_candidate() -> None:
    blocked = set(blocked_role_ids())
    assert blocked >= {
        "mitre_reasoner",
        "missing_evidence_reasoner",
        "risk_rationale_reasoner",
        "plan_delta_reasoner",
        "pattern_reasoner",
        "evidence_reasoner",
        "hypothesis_reasoner",
    }
    for role_id in blocked:
        assert candidate_for(role_id) is None
    assert set(_REASONING_ALLOWED_ROLES) == {"investigation_planner"}


def test_candidate_arm_selects_candidate_live_text() -> None:
    with use_prompt_eval_arm("candidate"):
        assert prompt_eval_arm() == "candidate"
        t4 = live_system_prompt("semantic_t4", _SEMANTIC_T4_SYSTEM_PROMPT)
        spl = live_system_prompt("spl_advisory_generator", _plan_system_prompt())
        planner = live_system_prompt(
            "investigation_planner",
            "You are the advisory investigation planning role. Return JSON only.",
        )
        assert t4 == CANDIDATES["semantic_t4"].system_instruction
        assert "LOCKED FIELDS ARE IMMUTABLE" in t4
        assert spl == CANDIDATES["spl_advisory_generator"].system_instruction
        assert "Never drop a denied_traffic" in spl
        assert "investigation_plan" in planner
        assert "hypotheses" in planner
        assert extra_few_shots_for_live("semantic_t4")
    assert prompt_eval_arm() == "active"
    assert extra_few_shots_for_live("semantic_t4") == ()


def test_candidate_t4_few_shots_are_eval_arm_only() -> None:
    from app.chat.intent_classifier import build_query_to_intent
    from app.query_understanding.parser import understand_query

    query = "signs that something is moving sideways through the estate"
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=understanding,
        qualification_tier="T4",
        qualification_source="p8_candidate_test",
        query_to_intent=q2i,
    )
    active_user = _build_semantic_t4_user_prompt(query, contract)
    assert "NEG invented host" not in active_user
    with use_prompt_eval_arm("candidate"):
        candidate_user = _build_semantic_t4_user_prompt(query, contract)
    assert "NEG invented host" in candidate_user
    assert "LOCKED FIELDS ARE IMMUTABLE" not in active_user


def test_roles_without_candidates_keep_active_on_candidate_arm() -> None:
    with use_prompt_eval_arm("candidate"):
        assert live_system_prompt("shape_advisor", "ACTIVE_SHAPE") == "ACTIVE_SHAPE"
