"""P8-A — candidate prompts are registered separately and never become production default."""

from __future__ import annotations

from app.chat.semantic_t4_understanding import (
    _SEMANTIC_T4_SYSTEM_PROMPT,
    _build_semantic_t4_user_prompt,
)
from app.chat.resolved_query_builder import build_resolved_query_contract
from app.llm.policy.candidates import (
    CANDIDATES,
    PROMOTED_TO_ACTIVE,
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
    """Unpromoted roles still serve their registry ACTIVE text on the default arm.

    investigation_planner is deliberately not asserted here: it has been promoted,
    so its ACTIVE text is now the promoted one. That is pinned separately in
    test_p8_planner_promotion.py, including that the promoted bytes are exactly
    the bytes the frozen A/B measured.
    """
    assert live_system_prompt("semantic_t4", _SEMANTIC_T4_SYSTEM_PROMPT) == _SEMANTIC_T4_SYSTEM_PROMPT
    assert live_system_prompt("spl_advisory_generator", _plan_system_prompt()) == _plan_system_prompt()
    assert "investigation_planner" in PROMOTED_TO_ACTIVE


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
        # v2 keeps the locked-field prohibition, stated plainly rather than shouted.
        assert "locked" in t4.lower()
        assert spl == CANDIDATES["spl_advisory_generator"].system_instruction
        assert "denied" in spl
        assert "investigation_plan" in planner
        assert "hypotheses" in planner
    assert prompt_eval_arm() == "active"
    # No candidate shot ever reaches the ACTIVE arm. Which shots the candidate arm
    # carries is asserted in test_t4_candidate_shot_is_arm_scoped_and_not_a_bank_question.
    assert extra_few_shots_for_live("semantic_t4") == ()


def test_candidate_eval_arm_is_visible_inside_sidecar_worker_thread() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from app.llm.policy.candidates import live_system_prompt
    from app.llm.policy.eval_arm import prompt_eval_arm, use_prompt_eval_arm

    def _worker() -> tuple[str, str]:
        return prompt_eval_arm(), live_system_prompt("semantic_t4", "ACTIVE_MUST_NOT_WIN")

    with use_prompt_eval_arm("candidate"):
        with ThreadPoolExecutor(max_workers=1) as pool:
            arm, text = pool.submit(_worker).result(timeout=5)
    assert arm == "candidate"
    assert text == CANDIDATES["semantic_t4"].system_instruction
    assert prompt_eval_arm() == "active"


def test_t4_candidate_shot_is_arm_scoped_and_not_a_bank_question() -> None:
    """v1.4.0 ships ONE synthetic clarification shot, candidate arm only.

    v1's five shots were near-verbatim frozen-bank questions; they contaminated
    the measurement and bled across examples, so v1.3.0 withdrew them entirely.
    v1.4.0 reintroduces exactly one, for the clarification-with-arrays shape that
    the model otherwise never demonstrates -- written from scratch, never taken
    from the bank.
    """
    import json as _json
    from pathlib import Path

    from app.chat.intent_classifier import build_query_to_intent
    from app.llm.policy.candidates import _T4_EXTRA_SHOTS
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
    with use_prompt_eval_arm("candidate"):
        candidate_user = _build_semantic_t4_user_prompt(query, contract)

    # The withdrawn v1 shots stay withdrawn.
    assert "NEG invented host" not in active_user
    assert "NEG invented host" not in candidate_user
    # The one v1.4.0 shot reaches the candidate arm and only the candidate arm.
    assert len(_T4_EXTRA_SHOTS) == 1
    marker = str(_T4_EXTRA_SHOTS[0]["query"])
    assert marker in candidate_user
    assert marker not in active_user

    # No T4 shot may be a frozen-bank question: an example keyed to a bank row
    # memorises the answer key. few_shot_catalog_v1 states the rule directly.
    bank = _json.loads(
        (Path(__file__).resolve().parents[3] / "docs/evals/p8_l3/bank_v1.json").read_text()
    )
    bank_queries = {str(row.get("query") or "").strip().lower() for row in bank["rows"]}
    for shot in _T4_EXTRA_SHOTS:
        assert str(shot["query"]).strip().lower() not in bank_queries


def test_spl_shape_few_shot_is_candidate_arm_only_and_shape_selected() -> None:
    """One shape-keyed plan example, chosen deterministically, candidate arm only."""
    from app.llm.policy.candidates import spl_shape_few_shot_block

    for shape in ("rolling", "trend", "sequence", "ranking", "raw"):
        assert spl_shape_few_shot_block(shape) == "", f"{shape} leaked into ACTIVE"

    with use_prompt_eval_arm("candidate"):
        rolling = spl_shape_few_shot_block("rolling")
        sequence = spl_shape_few_shot_block("sequence")
        assert "fs.spl.rolling.plan.candidate" in rolling
        assert "fs.spl.sequence.plan.candidate" in sequence
        assert rolling != sequence
        # An unsupported or unknown shape renders nothing, never a wrong example.
        assert spl_shape_few_shot_block("comparison") == ""
        assert spl_shape_few_shot_block("") == ""


def test_spl_shape_few_shots_are_not_frozen_bank_questions() -> None:
    """An example keyed to a bank question memorises the answer key.

    ``few_shot_catalog_v1`` states the rule directly: examples teach a shape,
    not a query.
    """
    import json as _json
    from pathlib import Path

    from app.llm.policy.candidates import _SPL_SHAPE_FEW_SHOTS

    bank = _json.loads(
        (Path(__file__).resolve().parents[3] / "docs/evals/p8_l3/bank_v1.json").read_text()
    )
    bank_queries = {str(row.get("query") or "").strip().lower() for row in bank["rows"]}
    for shape, shot in _SPL_SHAPE_FEW_SHOTS.items():
        assert str(shot["request"]).strip().lower() not in bank_queries, shape


def test_roles_without_candidates_keep_active_on_candidate_arm() -> None:
    with use_prompt_eval_arm("candidate"):
        assert live_system_prompt("shape_advisor", "ACTIVE_SHAPE") == "ACTIVE_SHAPE"


# v1.3.0-candidate stable prefixes. Frozen so a prompt edit cannot silently
# change what an A/B arm measured. v1.2.0-candidate's hashes were
# semantic_t4=6e897303..., spl_advisory_generator=42ede55d...,
# investigation_planner=ff1a47c9...; its results live in
# docs/evals/p8_l3/ab_binding_fair_*.json.
_EXPECTED_CANDIDATE_PREFIX = {
    # v1.4.0-candidate. v1.3.0's was ade105b7…; its results are in
    # docs/evals/p8_l3/ab_v131_candidate_scorecard.json.
    "semantic_t4": "b335f4c74583c6db24c62892b97d2ea929381ed09f20129fd803697c2e979a47",
    "spl_advisory_generator": "1e68b2908b8bcdb1c89a3a3125b342ad9b841b3895c7c85a5d71f8d38a703a49",
    "investigation_planner": "5283ec8a1bf24201b8bfce023d7722cdd3f9f892fc834a7f592cbbdecb4ec67b",
}


def test_candidate_arm_records_selected_instruction_hash_for_provider_binding() -> None:
    from app.llm.policy.request_provenance import (
        hash_prompt_text,
        reset_prompt_provenance,
        selected_prompt_for_role,
    )

    reset_prompt_provenance()
    with use_prompt_eval_arm("candidate"):
        # A promoted role no longer has a candidate arm to bind: its promoted
        # binding is pinned in test_p8_planner_promotion.py instead.
        for role_id in (r for r in _CANDIDATE_ROLES if r not in PROMOTED_TO_ACTIVE):
            text = live_system_prompt(role_id, "ACTIVE_MUST_NOT_WIN")
            selected = selected_prompt_for_role(role_id)
            assert selected is not None
            assert text == CANDIDATES[role_id].system_instruction
            assert selected["template_id"] == CANDIDATES[role_id].template_id
            # Track the registry rather than a literal: candidate versions are
            # immutable once evaluated, but a new bounded attempt bumps them.
            assert selected["version"] == CANDIDATES[role_id].version
            assert selected["version"].endswith("-candidate")
            assert selected["prefix_hash"] == _EXPECTED_CANDIDATE_PREFIX[role_id]
            assert selected["instruction_sha256"] == hash_prompt_text(text)
            assert candidate_stable_prefix_hash(role_id) == _EXPECTED_CANDIDATE_PREFIX[role_id]


def test_local_chat_client_hashes_the_system_message_placed_on_the_wire(monkeypatch) -> None:
    import json

    from app.llm.clients.local_chat_client import LocalChatClient
    from app.llm.policy.request_provenance import (
        hash_prompt_text,
        last_provider_request,
        record_selected_system_prompt,
        reset_prompt_provenance,
    )

    class _Resp:
        def read(self, _n: int) -> bytes:
            return json.dumps(
                {
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_a) -> bool:
            return False

    reset_prompt_provenance()
    monkeypatch.setattr("app.llm.clients.local_chat_client.urlopen", lambda *_a, **_k: _Resp())
    system = "CANDIDATE_SYSTEM_ON_THE_WIRE"
    record_selected_system_prompt(
        role_id="semantic_t4",
        template_id="tmpl.semantic_t4.candidate",
        version="1.2.0-candidate",
        status="CANDIDATE",
        system_instruction=system,
        prefix_hash=_EXPECTED_CANDIDATE_PREFIX["semantic_t4"],
    )
    client = LocalChatClient(base_url="http://example.invalid/v1", model="foundation-sec-instruct")
    client.generate(system_prompt=system, user_prompt="user", max_tokens=8, temperature=0.0)
    request = last_provider_request()
    assert request is not None
    assert request["system_prompt_sha256"] == hash_prompt_text(system)
    assert request["matches_selected_instruction"] is True
    assert request["role_id"] == "semantic_t4"


def test_prompt_provenance_survives_sidecar_worker_thread() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from app.llm.policy.request_provenance import (
        hash_prompt_text,
        provider_request_for_role,
        record_provider_system_prompt,
        record_selected_system_prompt,
        reset_prompt_provenance,
        selected_prompt_for_role,
    )

    reset_prompt_provenance()
    system = "WORKER_THREAD_CANDIDATE"

    def _worker() -> None:
        record_selected_system_prompt(
            role_id="semantic_t4",
            template_id="tmpl.semantic_t4.candidate",
            version="1.2.0-candidate",
            status="CANDIDATE",
            system_instruction=system,
            prefix_hash=_EXPECTED_CANDIDATE_PREFIX["semantic_t4"],
        )
        record_provider_system_prompt(system)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_worker).result(timeout=5)
    selected = selected_prompt_for_role("semantic_t4")
    request = provider_request_for_role("semantic_t4")
    assert selected is not None
    assert request is not None
    assert selected["instruction_sha256"] == hash_prompt_text(system)
    assert request["system_prompt_sha256"] == hash_prompt_text(system)
    assert request["matches_selected_instruction"] is True


def test_candidate_t4_schema_decides_clarification_before_describing_the_goal() -> None:
    """Field order is the mechanism that fixed L3.T4.03, so it is pinned.

    Guided decoding emits properties in schema order and generation is
    autoregressive. Under the ACTIVE order the model writes ``normalized_goal``
    first -- committing to a confident reading -- and then answers
    ``clarification_required``, where "false" is the self-consistent
    continuation. Measured: with the ACTIVE order the model refused to clarify
    L3.T4.03 even with that exact question and its correct clarify answer
    present in the prompt; moving the decision ahead of the goal flipped it.

    Reordering keys adds, removes and relaxes nothing: JSON object key order is
    not semantic to any consumer, and the frozen SemanticT4Proposal is untouched.
    """
    from app.chat.semantic_t4_understanding import _SEMANTIC_T4_SCHEMA
    from app.llm.policy.candidates import candidate_t4_response_schema

    # Production is byte-identical to the ACTIVE schema object.
    assert candidate_t4_response_schema(_SEMANTIC_T4_SCHEMA) is _SEMANTIC_T4_SCHEMA

    with use_prompt_eval_arm("candidate"):
        schema = candidate_t4_response_schema(_SEMANTIC_T4_SCHEMA)
    keys = list(schema["properties"])
    assert keys.index("clarification_required") < keys.index("normalized_goal")
    assert keys.index("clarification_reason") < keys.index("normalized_goal")

    # Same field set as ACTIVE minus only the deprecated aliases: nothing invented.
    assert set(keys) == set(_SEMANTIC_T4_SCHEMA["properties"]) - {"ambiguity_state", "confidence"}
    # T4 is never offered capability authority, in either arm.
    for forbidden in ("required_capabilities", "prohibited_capabilities", "intent_family"):
        assert forbidden not in keys
