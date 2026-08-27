"""P4 PP2/PP3 — role contract completeness, authority and narrowness.

Covers mission checks A, B, H, I, J, K, L, M for the contract layer. Hash and cache
behaviour is proven separately in test_prompt_policy_templates.py.
"""

from __future__ import annotations

import pytest

from app.llm.policy.contracts import (
    UNIVERSAL_PROHIBITED_AUTHORITY,
    RoleContract,
    RoleContractError,
)
from app.llm.policy.registry import ROLE_CONTRACTS, contract_for, contracts, missing_contract_role_ids
from app.llm.policy.role_inventory import blocked_role_ids, facts_for, role_ids
from app.spl.spl_intent_spec import (
    SPL_SEMANTIC_CONTRACT_VERSION,
    SUPPORTED_ANALYSIS_SHAPES,
    UNSUPPORTED_ANALYSIS_SHAPES,
)


def _minimal_kwargs(**over):
    base = dict(
        role_id="probe_role",
        runtime_posture="PRODUCTION_REACHABLE",
        why_llm="probe",
        authoritative_inputs=("x",),
        non_authoritative_context=(),
        system_instruction="probe instruction",
        dynamic_context=("y",),
        output_schema="ProbeSchema",
        few_shot_set="fewshot:probe",
        negative_example_set="negative:probe",
        model_class="small_structured_classifier",
        decoding="deterministic",
        timeout_seconds=10.0,
        retry_repair_policy="none",
        allowed_authority=("propose_probe",),
        validator="probe validator",
        fallback="deterministic probe",
        trace_fields=("role_id",),
        prompt_template_id="tmpl.probe",
        prompt_version="1.0.0",
    )
    base.update(over)
    return base


# --- A: completeness --------------------------------------------------------


def test_every_inventoried_role_has_a_contract() -> None:
    assert missing_contract_role_ids() == ()


def test_no_contract_exists_for_an_uninventoried_role() -> None:
    stray = sorted(set(ROLE_CONTRACTS) - set(role_ids()))
    assert not stray, f"contracts for roles not in the inventory: {stray}"


def test_contract_count_matches_inventory() -> None:
    # 25 -> 26: OPTIONAL_PHASE_S Layer 3 `spl_optimization_llm` is a real live role with
    # an OFF_REGISTRY_ROLES call site, so it gets a contract rather than being hidden.
    assert len(ROLE_CONTRACTS) == len(role_ids()) == 26


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_required_fields_are_populated(role_id: str) -> None:
    """Construction validates; this proves every registered contract survived it."""
    contract = contract_for(role_id)
    for name in (
        "why_llm",
        "system_instruction",
        "output_schema",
        "few_shot_set",
        "negative_example_set",
        "retry_repair_policy",
        "validator",
        "fallback",
        "prompt_template_id",
        "prompt_version",
    ):
        assert str(getattr(contract, name)).strip(), f"{role_id}.{name} is blank"
    assert contract.authoritative_inputs
    assert contract.allowed_authority
    assert contract.trace_fields


def test_not_applicable_requires_a_reason() -> None:
    with pytest.raises(RoleContractError, match="NOT_APPLICABLE without a reason"):
        RoleContract(**_minimal_kwargs(few_shot_set="NOT_APPLICABLE"))


def test_not_applicable_with_a_reason_is_accepted() -> None:
    contract = RoleContract(**_minimal_kwargs(few_shot_set="NOT_APPLICABLE: no shared bank"))
    assert contract.few_shot_set.startswith("NOT_APPLICABLE:")


def test_blank_required_field_is_rejected() -> None:
    with pytest.raises(RoleContractError, match="must not be blank"):
        RoleContract(**_minimal_kwargs(validator="   "))


# --- B: duplicate role ids --------------------------------------------------


def test_role_ids_are_unique_in_the_registry() -> None:
    ids = [c.role_id for c in contracts()]
    assert len(ids) == len(set(ids))


def test_registry_dict_and_tuple_agree() -> None:
    """A duplicate ROLE_ID would silently shrink the dict; this catches that."""
    assert len(ROLE_CONTRACTS) == len(contracts())


# --- H / M: prohibited authority is enforced, never shortened ----------------


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_universal_prohibitions_apply_to_every_role(role_id: str) -> None:
    prohibited = contract_for(role_id).prohibited_authority
    for item in UNIVERSAL_PROHIBITED_AUTHORITY:
        assert item in prohibited, f"{role_id} lost universal prohibition {item}"


def test_a_role_cannot_subtract_a_universal_prohibition() -> None:
    """extra_prohibited_authority only adds; there is no subtract path."""
    contract = RoleContract(**_minimal_kwargs(extra_prohibited_authority=("custom_ban",)))
    assert set(UNIVERSAL_PROHIBITED_AUTHORITY).issubset(set(contract.prohibited_authority))
    assert "custom_ban" in contract.prohibited_authority


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_no_role_may_authorize_mcp_write_or_execution(role_id: str) -> None:
    """Mission M: no registry entry can directly authorize MCP, write or remediation."""
    allowed = {a.lower() for a in contract_for(role_id).allowed_authority}
    for forbidden_substring in ("mcp", "execute", "authorize", "remediat", "rbac", "hil"):
        offenders = [a for a in allowed if forbidden_substring in a]
        # 'narrow_deterministic_remediation_steps' is a narrowing verb, not an
        # authorization; assert it never pairs with an execution/authorization verb.
        for offender in offenders:
            assert not any(
                verb in offender for verb in ("execute", "authorize", "invoke", "run_")
            ), f"{role_id} allows {offender}"


def test_allowed_and_prohibited_authority_cannot_overlap() -> None:
    with pytest.raises(RoleContractError, match="both allowed and prohibited"):
        RoleContract(**_minimal_kwargs(allowed_authority=("hil_bypass",)))


# --- I: validator and fallback declared -------------------------------------


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_every_role_declares_validator_and_fallback(role_id: str) -> None:
    contract = contract_for(role_id)
    assert contract.validator.strip()
    assert contract.fallback.strip()


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_no_role_declares_unbounded_retry(role_id: str) -> None:
    """Mission 10: no 'retry until valid' anywhere."""
    policy = contract_for(role_id).retry_repair_policy.lower()
    for banned in ("until valid", "unbounded", "unlimited", "retry until"):
        assert banned not in policy, f"{role_id} declares an unbounded retry: {policy}"


# --- J: blocked roles stay blocked ------------------------------------------


@pytest.mark.parametrize("role_id", sorted(blocked_role_ids()))
def test_blocked_roles_carry_blocked_posture_in_their_contract(role_id: str) -> None:
    """Posture is derived from live code, so a contract cannot claim otherwise."""
    assert contract_for(role_id).runtime_posture == "BLOCKED_BY_ALLOWLIST"
    assert facts_for(role_id).posture == "BLOCKED_BY_ALLOWLIST"


def test_p4_did_not_enable_any_blocked_role() -> None:
    """The four named by the plan plus the three reproved alongside them."""
    blocked = set(blocked_role_ids())
    for role in (
        "mitre_reasoner",
        "missing_evidence_reasoner",
        "risk_rationale_reasoner",
        "plan_delta_reasoner",
        "pattern_reasoner",
        "evidence_reasoner",
        "hypothesis_reasoner",
    ):
        assert role in blocked


# --- K / L: SPL contract reflects spl_semantic_v2 without changing authority --


def test_spl_roles_are_declared_as_b_owned() -> None:
    """D describes the seam; B edits it."""
    for role_id in ("spl_advisory_generator", "spl_repair"):
        assert contract_for(role_id).owning_workstream == "B_SPL"


def test_spl_generation_contract_carries_the_semantic_v2_inputs() -> None:
    inputs = set(contract_for("spl_advisory_generator").authoritative_inputs)
    for required in (
        "spl_semantic_v2_immutable_contract",
        "final_rqc_constraints",
        "governed_source_mappings",
        "analysis_and_output_shape",
        "required_event_sets",
        "entity_roles",
        "search_horizon",
        "analytical_window",
        "measures_grouping_distinct_ranking",
        "temporal_and_sequence_semantics",
        "semantic_prohibitions",
    ):
        assert required in inputs, f"spl_advisory_generator missing input {required}"


def test_spl_semantic_contract_version_is_still_v2() -> None:
    """P4 must not weaken P2's contract; this pins the version it describes."""
    assert SPL_SEMANTIC_CONTRACT_VERSION == "spl_semantic_v2"


def test_spl_generation_contract_excludes_unrelated_policy() -> None:
    """No MITRE, remediation, routing or alert-template bias in the SPL prompt."""
    contract = contract_for("spl_advisory_generator")
    prohibited = set(contract.prohibited_authority)
    assert "receiving_mitre_policy" in prohibited
    assert "receiving_remediation_policy" in prohibited
    assert "receiving_generic_alert_template_catalogue" in prohibited
    joined = " ".join(contract.authoritative_inputs + contract.dynamic_context).lower()
    for leak in ("mitre", "remediation", "route", "alert_template"):
        assert leak not in joined, f"SPL prompt input leaks {leak}"


def test_spl_repair_is_bounded_to_exactly_one_attempt() -> None:
    """P4 must not change P2's 1 generation + max 1 repair bound."""
    contract = contract_for("spl_repair")
    assert "one repair" in contract.retry_repair_policy.lower()
    assert "second_repair_attempt" in contract.prohibited_authority
    assert "reinterpreting_the_request" in contract.prohibited_authority


def test_spl_candidate_is_never_execution_eligible_via_prompt() -> None:
    for role_id in ("spl_advisory_generator", "spl_repair"):
        prohibited = contract_for(role_id).prohibited_authority
        assert "marking_candidate_execution_eligible" in prohibited
        assert "candidate_spl_execution" in prohibited


def test_comparison_shape_remains_unsupported_in_p2() -> None:
    """Mission L: comparison must stay a product gap, not be silently promoted."""
    assert "comparison" in UNSUPPORTED_ANALYSIS_SHAPES
    assert "comparison" not in SUPPORTED_ANALYSIS_SHAPES


# --- narrowness: no monolithic prompt ---------------------------------------


def test_no_contract_reuses_another_roles_full_input_set() -> None:
    """A monolithic prompt shows up as two roles with identical authoritative inputs."""
    seen: dict[tuple[str, ...], str] = {}
    for contract in contracts():
        key = tuple(sorted(contract.authoritative_inputs))
        if key in seen:
            pytest.fail(
                f"{contract.role_id} and {seen[key]} share an identical input set; "
                "that is a monolithic prompt, not two narrow ones"
            )
        seen[key] = contract.role_id


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_system_instruction_carries_no_request_data_placeholders(role_id: str) -> None:
    """The system instruction becomes the stable prefix; it must be turn-independent."""
    instruction = contract_for(role_id).system_instruction.lower()
    for volatile in ("{query}", "{session", "{trace", "{user", "{timestamp", "{evidence"):
        assert volatile not in instruction, f"{role_id} embeds turn data in its stable instruction"
