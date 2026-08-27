"""P4 PP1 — the governed LLM role inventory, derived from live code.

Why this is derived rather than written down
--------------------------------------------
A hand-maintained list of roles is wrong the day someone adds a call site. Every
function here reads the *actual* runtime namespaces and computes posture from them,
so the inventory cannot silently drift from the code it describes. The only hardcoded
data are the facts that genuinely live outside those namespaces (the two orphan roles
that exist only as a timeout entry, and the one role that bypasses the registry
entirely), and each of those carries the call site that proves it.

The five role namespaces
------------------------
``ROLE_DEFAULTS``        registry_settings — governance posture, decoding, token bounds
``ROLE_ENV_MAP``         registry_settings — provider/model env binding
``ROLE_SCHEMA_REGISTRY`` adapter.role_registry — structured output schema
``PROMPT_CONTRACTS``     prompts — system instruction and include/exclude contract
``_ROLE_TIMEOUT_SECONDS`` sidecar_clients — wrapper timeout

A role present in some but not all of these is not a bug by itself, but it is a fact
the inventory must state rather than smooth over.

Posture is a function of configuration, not a constant
------------------------------------------------------
The thing usually described as "the allowlist that blocks the reasoners" is
``sidecar_clients._REASONING_ALLOWED_ROLES``, and it does not block a role directly.
``sidecar_governance.resolve_sidecar_role_status`` rejects a role only when its
*governance-resolved* provider/model is the reasoning assignment AND the role is not
in that frozenset. So a reasoning-preferring role is blocked when the reasoning
provider is configured, and simply falls back to another provider when it is not.

``BLOCKED_BY_ALLOWLIST`` below therefore means "blocked whenever its preferred
reasoning provider resolves", which is the posture that matters for a deployment that
configures one. It is recorded as a conditional, not as an unconditional truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.llm.adapter.role_registry import ROLE_SCHEMA_REGISTRY
from app.llm.prompts import PROMPT_CONTRACTS
from app.llm.registry_settings import ROLE_DEFAULTS, ROLE_ENV_MAP
from app.llm.sidecar_clients import _REASONING_ALLOWED_ROLES, _ROLE_TIMEOUT_SECONDS

INVENTORY_VERSION = "role_inventory_v1"

Posture = Literal[
    "PRODUCTION_REACHABLE",
    "BLOCKED_BY_ALLOWLIST",
    "DORMANT",
    "TEST_ONLY",
    "LEGACY_DEAD",
]

_REASONING_PROVIDER_ATTR = "ai_soc_llm_reasoning_provider"


@dataclass(frozen=True)
class RoleFacts:
    """What the live namespaces actually say about one role."""

    role_id: str
    in_role_defaults: bool
    in_env_map: bool
    has_output_schema: bool
    has_prompt_contract: bool
    has_sidecar_timeout: bool
    prefers_reasoning_provider: bool
    reasoning_allowlisted: bool
    posture: Posture
    posture_evidence: str


#: Roles that exist at runtime but appear in none of the registry namespaces.
#: Each entry names the call site that proves the role is real. These are the
#: inventory's genuine hardcoded facts; the reachability test re-proves each one.
OFF_REGISTRY_ROLES: dict[str, str] = {
    # Timeout-only roles: a wrapper timeout exists, but no ROLE_DEFAULTS entry, no
    # provider binding, no output schema and no prompt contract.
    "governed_composer": (
        "app/llm/hybrid_role_graph.py (synthesize node) and app/llm/llm_call_context.py "
        "(CALL_PURPOSE_COMPOSER); timeout in sidecar_clients._ROLE_TIMEOUT_SECONDS"
    ),
    "remediation_planner": (
        "app/chat/remediation_plan_reasoner.py::REMEDIATION_PLAN_ROLE, invoked from "
        "app/chat/remediation_runtime.py; timeout in sidecar_clients._ROLE_TIMEOUT_SECONDS"
    ),
    # Bypasses the sidecar registry entirely: resolves an endpoint and builds its own
    # prompt inline, so no registry namespace knows it exists.
    "semantic_t4": (
        "app/chat/semantic_t4_understanding.py::_build_semantic_t4_user_prompt via "
        "resolve_local_primary_endpoint + LocalChatClient; no registry entry of any kind"
    ),
    # OPTIONAL_PHASE_S Layer 3. Builds the synthesis client directly, so it has no
    # ROLE_DEFAULTS row and deliberately no sidecar timeout: a _ROLE_TIMEOUT_SECONDS
    # entry would claim a wrapper bound that never applies to this call path.
    "spl_optimization_llm": (
        "app/spl/spl_optimization_llm.py::SPL_OPTIMIZATION_LLM_ROLE, invoked from "
        "apply_optimization_llm via build_synthesis_client_from_settings; reached from "
        "app/spl/spl_optimization_chain.py under ai_soc_spl_optimization_llm_enabled "
        "(default false); no registry entry of any kind"
    ),
    # The second pass of SPL authoring. Shares spl_advisory_generator's registry entry
    # but has a distinct prompt payload and a hard one-attempt bound (P2-owned).
    "spl_repair": (
        "app/spl/utility_spl_authoring.py generation_mode 'utility_llm_spl_repair'; "
        "shares the spl_advisory_generator registry row, distinct prompt contract"
    ),
}

#: Canonical role id -> alias(es) seen elsewhere in code, config or the plan.
#: An alias is never counted as a separate role.
ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "intent_shadow_classifier": ("intent_advisor",),
    "spl_advisory_generator": ("spl_generation",),
}


def _registry_role_ids() -> set[str]:
    return {str(item["role"]) for item in ROLE_DEFAULTS}


def _prefers_reasoning_provider(role_id: str) -> bool:
    binding = ROLE_ENV_MAP.get(role_id)
    return bool(binding and binding[0] == _REASONING_PROVIDER_ATTR)


def _posture_for(role_id: str, *, prefers_reasoning: bool, allowlisted: bool) -> tuple[Posture, str]:
    if role_id in OFF_REGISTRY_ROLES:
        return "PRODUCTION_REACHABLE", f"off-registry call site: {OFF_REGISTRY_ROLES[role_id]}"
    if prefers_reasoning and not allowlisted:
        return (
            "BLOCKED_BY_ALLOWLIST",
            "prefers ai_soc_llm_reasoning_provider and is absent from "
            "sidecar_clients._REASONING_ALLOWED_ROLES, so resolve_sidecar_role_status "
            "rejects it whenever the reasoning assignment resolves",
        )
    if prefers_reasoning and allowlisted:
        return (
            "PRODUCTION_REACHABLE",
            "prefers the reasoning provider and is explicitly reasoning-allowlisted",
        )
    return "PRODUCTION_REACHABLE", "registry role with a non-reasoning provider binding"


def role_facts() -> tuple[RoleFacts, ...]:
    """Compute the inventory from live namespaces. No cached or written-down state."""
    registry_ids = _registry_role_ids()
    all_ids = sorted(
        registry_ids
        | set(ROLE_ENV_MAP)
        | set(ROLE_SCHEMA_REGISTRY)
        | set(PROMPT_CONTRACTS)
        | set(_ROLE_TIMEOUT_SECONDS)
        | set(OFF_REGISTRY_ROLES)
    )
    facts: list[RoleFacts] = []
    for role_id in all_ids:
        prefers_reasoning = _prefers_reasoning_provider(role_id)
        allowlisted = role_id in _REASONING_ALLOWED_ROLES
        posture, evidence = _posture_for(
            role_id, prefers_reasoning=prefers_reasoning, allowlisted=allowlisted
        )
        facts.append(
            RoleFacts(
                role_id=role_id,
                in_role_defaults=role_id in registry_ids,
                in_env_map=role_id in ROLE_ENV_MAP,
                has_output_schema=role_id in ROLE_SCHEMA_REGISTRY,
                has_prompt_contract=role_id in PROMPT_CONTRACTS,
                has_sidecar_timeout=role_id in _ROLE_TIMEOUT_SECONDS,
                prefers_reasoning_provider=prefers_reasoning,
                reasoning_allowlisted=allowlisted,
                posture=posture,
                posture_evidence=evidence,
            )
        )
    return tuple(facts)


def role_ids() -> tuple[str, ...]:
    return tuple(fact.role_id for fact in role_facts())


def facts_for(role_id: str) -> RoleFacts:
    for fact in role_facts():
        if fact.role_id == role_id:
            return fact
    raise KeyError(f"unknown role: {role_id}")


def roles_with_posture(posture: Posture) -> tuple[str, ...]:
    return tuple(fact.role_id for fact in role_facts() if fact.posture == posture)


def blocked_role_ids() -> tuple[str, ...]:
    return roles_with_posture("BLOCKED_BY_ALLOWLIST")


def canonical_for_alias(alias: str) -> str | None:
    for canonical, aliases in ROLE_ALIASES.items():
        if alias == canonical or alias in aliases:
            return canonical
    return None
