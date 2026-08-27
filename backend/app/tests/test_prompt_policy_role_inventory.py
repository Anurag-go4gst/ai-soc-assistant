"""P4 PP1 — freeze role posture and reachability, reproved from live code.

These tests exist to stop two failure modes: an inventory that quietly stops matching
the code, and a dormant reasoning role that gets switched on as a side effect of an
unrelated change. Neither is caught by reading a table.
"""

from __future__ import annotations

import pytest

from app.llm.adapter.role_registry import ROLE_SCHEMA_REGISTRY
from app.llm.policy.role_inventory import (
    OFF_REGISTRY_ROLES,
    ROLE_ALIASES,
    blocked_role_ids,
    canonical_for_alias,
    facts_for,
    role_facts,
    role_ids,
)
from app.llm.prompts import PROMPT_CONTRACTS
from app.llm.registry_settings import ROLE_DEFAULTS, ROLE_ENV_MAP
from app.llm.sidecar_clients import _REASONING_ALLOWED_ROLES

#: Measured at 29933dda; 25 -> 26 for OPTIONAL_PHASE_S Layer 3 `spl_optimization_llm`,
#: a deliberate reviewed addition with an OFF_REGISTRY_ROLES call site and a contract.
#: Rises only with a deliberate, reviewed role addition.
_EXPECTED_ROLE_COUNT = 26

#: Measured at 29933dda. The master plan named four blocked reasoners; the live
#: allowlist blocks seven by the identical mechanism. Recorded as the reproved set.
_EXPECTED_BLOCKED = (
    "evidence_reasoner",
    "hypothesis_reasoner",
    "missing_evidence_reasoner",
    "mitre_reasoner",
    "pattern_reasoner",
    "plan_delta_reasoner",
    "risk_rationale_reasoner",
)

#: The four the master plan explicitly required a posture decision for.
_PLAN_NAMED_BLOCKED = (
    "mitre_reasoner",
    "missing_evidence_reasoner",
    "risk_rationale_reasoner",
    "plan_delta_reasoner",
)


def test_inventory_meets_the_twenty_four_role_minimum() -> None:
    assert len(role_ids()) >= 24


def test_inventory_size_is_frozen_against_silent_growth() -> None:
    """A new LLM role must be an intentional, reviewed event."""
    assert len(role_ids()) == _EXPECTED_ROLE_COUNT


def test_role_ids_are_unique() -> None:
    ids = role_ids()
    assert len(ids) == len(set(ids))


def test_every_role_has_a_posture_and_evidence() -> None:
    missing = [
        fact.role_id for fact in role_facts() if not fact.posture or not fact.posture_evidence.strip()
    ]
    assert not missing, f"roles without posture evidence: {missing}"


# ---------------------------------------------------------------------------
# The allowlist block, reproved rather than assumed
# ---------------------------------------------------------------------------


def test_blocked_set_matches_the_measured_allowlist() -> None:
    assert tuple(sorted(blocked_role_ids())) == _EXPECTED_BLOCKED


def test_plan_named_reasoners_are_all_still_blocked() -> None:
    """The four the plan called out must not become reachable without a decision."""
    blocked = set(blocked_role_ids())
    for role in _PLAN_NAMED_BLOCKED:
        assert role in blocked, f"{role} is no longer blocked; that needs an operator decision"


def test_blocking_mechanism_is_the_reasoning_allowlist_not_a_role_denylist() -> None:
    """Reproves *why* the roles are blocked, so a refactor cannot silently relocate it.

    Blocking is: prefers the reasoning provider AND absent from the allowlist. Any role
    matching that pair must be blocked, and no other role may be.
    """
    for fact in role_facts():
        expected_blocked = fact.prefers_reasoning_provider and not fact.reasoning_allowlisted
        actual_blocked = fact.posture == "BLOCKED_BY_ALLOWLIST"
        assert expected_blocked == actual_blocked, (
            f"{fact.role_id}: prefers_reasoning={fact.prefers_reasoning_provider} "
            f"allowlisted={fact.reasoning_allowlisted} posture={fact.posture}"
        )


def test_only_investigation_planner_is_reasoning_allowlisted() -> None:
    """Widening this frozenset activates dormant reasoners; it must be deliberate."""
    assert set(_REASONING_ALLOWED_ROLES) == {"investigation_planner"}


def test_investigation_planner_is_reachable_despite_preferring_reasoning() -> None:
    fact = facts_for("investigation_planner")
    assert fact.prefers_reasoning_provider is True
    assert fact.reasoning_allowlisted is True
    assert fact.posture == "PRODUCTION_REACHABLE"


# ---------------------------------------------------------------------------
# Namespace coherence — states the gaps rather than smoothing them over
# ---------------------------------------------------------------------------


def test_registry_roles_are_bound_in_both_registry_namespaces() -> None:
    """validate_role_registry's invariant, asserted over the whole inventory."""
    registry_ids = {str(item["role"]) for item in ROLE_DEFAULTS}
    assert registry_ids == set(ROLE_ENV_MAP), (
        "ROLE_DEFAULTS and ROLE_ENV_MAP must describe the same role set"
    )


def test_structured_roles_have_an_output_schema() -> None:
    """Every role whose consumer parses JSON must have an adapter schema."""
    for role_id in ROLE_SCHEMA_REGISTRY:
        assert facts_for(role_id).has_output_schema is True


def test_off_registry_roles_are_declared_with_their_call_site() -> None:
    """A role outside the registry namespaces is a fact to record, not to hide."""
    for role_id, evidence in OFF_REGISTRY_ROLES.items():
        fact = facts_for(role_id)
        assert fact.in_role_defaults is False
        assert fact.in_env_map is False
        assert evidence.strip(), f"{role_id} must name its call site"


def test_semantic_t4_is_recorded_as_bypassing_the_registry() -> None:
    """It resolves an endpoint directly, so no registry namespace can describe it."""
    fact = facts_for("semantic_t4")
    assert fact.posture == "PRODUCTION_REACHABLE"
    assert fact.in_role_defaults is False
    assert fact.has_output_schema is False
    assert fact.has_prompt_contract is False


@pytest.mark.parametrize("role_id", ["governed_composer", "remediation_planner"])
def test_timeout_only_roles_are_recorded_as_contract_gaps(role_id: str) -> None:
    """These have a wrapper timeout but no governance row, schema or prompt contract."""
    fact = facts_for(role_id)
    assert fact.has_sidecar_timeout is True
    assert fact.in_role_defaults is False
    assert fact.has_prompt_contract is False


# ---------------------------------------------------------------------------
# Aliases resolve to one canonical role and are never double counted
# ---------------------------------------------------------------------------


def test_aliases_resolve_to_a_real_canonical_role() -> None:
    for canonical in ROLE_ALIASES:
        assert canonical in role_ids()


def test_aliases_are_not_counted_as_separate_roles() -> None:
    inventory = set(role_ids())
    for aliases in ROLE_ALIASES.values():
        for alias in aliases:
            assert alias not in inventory, f"alias {alias} leaked into the inventory"


@pytest.mark.parametrize(
    "alias,canonical",
    [
        ("intent_advisor", "intent_shadow_classifier"),
        ("spl_generation", "spl_advisory_generator"),
        ("intent_shadow_classifier", "intent_shadow_classifier"),
    ],
)
def test_alias_lookup_resolves(alias: str, canonical: str) -> None:
    assert canonical_for_alias(alias) == canonical


def test_unknown_alias_resolves_to_none() -> None:
    assert canonical_for_alias("no_such_role") is None


# ---------------------------------------------------------------------------
# Prompt contract reachability
# ---------------------------------------------------------------------------


def test_prompt_contracts_cover_every_registry_role() -> None:
    registry_ids = {str(item["role"]) for item in ROLE_DEFAULTS}
    uncovered = sorted(registry_ids - set(PROMPT_CONTRACTS))
    assert not uncovered, f"registry roles with no prompt contract: {uncovered}"


def test_facts_for_rejects_unknown_role() -> None:
    with pytest.raises(KeyError):
        facts_for("definitely_not_a_role")
