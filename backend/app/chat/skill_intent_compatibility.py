"""Deterministic routed-skill × intent-family capability compatibility (Plan 3 B2).

Two planning surfaces used to disagree about the same turn: the intent classifier
could demand SPL/MCP work while the routed skill's capability contract forbade it.
The composer honored the contract (empty plan); Phase Policy honored the intent
(full SPL lane). Nothing reconciled them, so the disagreement surfaced only as a
scheduler downgrade.

This module is the single reconciliation point. It resolves the *capability*
constraints both surfaces must obey, and it **fails closed**: a contradiction
never widens capability. A turn whose intent wants SPL but whose skill forbids it
resolves to "SPL not permitted" — it does not rescue the route by granting SPL.

Failing closed here means the **capability decision** fails closed, not that the
turn errors. Measured on the 105-question golden set, 14 turns are already in the
contradiction class and none of their accepted answers contains SPL: the lane runs
today and contributes nothing. Denying the capability removes wasted work;
erroring the turn would regress 14 accepted answers for no safety gain.

Boundaries:
- Pure and deterministic. No settings, I/O, LLM, or state mutation.
- It constrains capability only. It never selects a route, never overrides an
  operator/COE value, and never relaxes the MCP execution gate, HIL, RBAC, or SPL
  validation — those remain authoritative downstream.
- Composer/validator vetoes stay in place as defense-in-depth; this is an
  additional, earlier enforcement point, not a replacement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "compatible"
    CAPABILITY_CONTRADICTION = "capability_contradiction"
    #: Contradictions with their own pre-existing protected handling (e.g. the
    #: alert_summary + SPL goal rule in `canonical_answer_mode_policy`). Reported
    #: distinctly so this module never silently supersedes that policy.
    PROTECTED_CONTRADICTION = "protected_contradiction"
    #: Intent family or contract not known well enough to assert compatibility.
    UNRESOLVED = "unresolved"


#: Capabilities this contract reasons about. Deliberately small: these are the two
#: that change *execution* authority.
CAPABILITY_SPL = "spl"
CAPABILITY_MCP = "mcp"

#: Intent families that require a capability to do their job. Generic table, not a
#: special case for any one query shape.
_INTENT_REQUIRED_CAPABILITIES: dict[str, frozenset[str]] = {
    "spl_generation_only": frozenset({CAPABILITY_SPL}),
    "spl_artifact": frozenset({CAPABILITY_SPL}),
    "live_investigation": frozenset({CAPABILITY_SPL, CAPABILITY_MCP}),
}

#: Intent families that need no execution capability.
_INTENT_NO_CAPABILITY: frozenset[str] = frozenset(
    {
        "knowledge_only",
        "clarification_required",
        "alert_summary",
        "mitre_explanation",
        "reference_knowledge",
        "cve_investigation",
    }
)

#: Pre-existing protected contradiction: owned by `canonical_answer_mode_policy`
#: (`alert_summary_spl_contradiction`). Kept as a distinct status so this module
#: reports it without competing with that rule.
_PROTECTED_PAIRS: frozenset[tuple[str, str]] = frozenset({("alert_summary", "alert_summary")})


@dataclass(frozen=True)
class CompatibilityResolution:
    status: CompatibilityStatus
    routed_skill: str
    intent_family: str
    required_capabilities: frozenset[str] = frozenset()
    granted_capabilities: frozenset[str] = frozenset()
    #: Required by the intent but denied by the contract — the contradiction itself.
    denied_capabilities: frozenset[str] = frozenset()
    reasons: list[str] = field(default_factory=list)

    @property
    def spl_permitted(self) -> bool:
        return CAPABILITY_SPL in self.granted_capabilities

    @property
    def mcp_permitted(self) -> bool:
        return CAPABILITY_MCP in self.granted_capabilities

    @property
    def is_contradiction(self) -> bool:
        return self.status in {
            CompatibilityStatus.CAPABILITY_CONTRADICTION,
            CompatibilityStatus.PROTECTED_CONTRADICTION,
        }


def _contract_grants(contract: Mapping[str, Any] | None, capability: str) -> bool:
    """Delegate to the composer's own permit logic.

    Reused rather than reimplemented so Phase Policy and ResourcePlan composition
    provably answer "does this skill allow SPL/MCP?" from one implementation. A
    second copy of the hint table would be a second authority by another name.
    """
    if not isinstance(contract, Mapping):
        return False
    from app.planner.composer import _skill_permits

    return bool(_skill_permits(dict(contract), capability))


def resolve_capability_compatibility(
    *,
    routed_skill: str | None,
    intent_family: str | None,
    skill_contract: Mapping[str, Any] | None,
) -> CompatibilityResolution:
    """Resolve the capability constraints both Phase Policy and composition obey."""
    skill = str(routed_skill or "")
    family = str(intent_family or "")

    granted = frozenset(
        capability
        for capability in (CAPABILITY_SPL, CAPABILITY_MCP)
        if _contract_grants(skill_contract, capability)
    )

    if not skill or not family or skill_contract is None:
        return CompatibilityResolution(
            status=CompatibilityStatus.UNRESOLVED,
            routed_skill=skill,
            intent_family=family,
            granted_capabilities=granted,
            reasons=["missing_skill_intent_or_contract"],
        )

    if family in _INTENT_REQUIRED_CAPABILITIES:
        required = _INTENT_REQUIRED_CAPABILITIES[family]
    elif family in _INTENT_NO_CAPABILITY:
        required = frozenset()
    else:
        return CompatibilityResolution(
            status=CompatibilityStatus.UNRESOLVED,
            routed_skill=skill,
            intent_family=family,
            granted_capabilities=granted,
            reasons=[f"unknown_intent_family:{family}"],
        )

    denied = frozenset(required - granted)
    if not denied:
        return CompatibilityResolution(
            status=CompatibilityStatus.COMPATIBLE,
            routed_skill=skill,
            intent_family=family,
            required_capabilities=required,
            granted_capabilities=granted,
            reasons=["capabilities_satisfied"],
        )

    status = (
        CompatibilityStatus.PROTECTED_CONTRADICTION
        if (skill, family) in _PROTECTED_PAIRS
        else CompatibilityStatus.CAPABILITY_CONTRADICTION
    )
    return CompatibilityResolution(
        status=status,
        routed_skill=skill,
        intent_family=family,
        required_capabilities=required,
        # Fail closed: the contract wins. Capability is never widened to satisfy intent.
        granted_capabilities=granted,
        denied_capabilities=denied,
        reasons=[f"{skill}_contract_forbids:{','.join(sorted(denied))}"],
    )


def skill_contract_for(routed_skill: str | None) -> Mapping[str, Any] | None:
    """Look up a routed skill's capability contract — the composer's exact lookup."""
    if not routed_skill:
        return None
    from app.planner.composer import _skill_contract
    from app.planner.resource_registry import load_resource_registry

    return _skill_contract(str(routed_skill), load_resource_registry())
