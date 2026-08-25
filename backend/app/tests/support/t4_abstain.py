"""Shared test helper: force a real ABSTAIN gap so T4 is permitted.

Production complete-or-abstain ACCEPTs fully resolved T4-lane contracts and
skips T4. Neighbour tests that exercise the hop must pin a genuine
``semantic_referent`` unresolved field — not invent ``semantic_goal``.
"""

from __future__ import annotations

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.contracts.staged_sufficiency import from_understanding_state
from app.chat.resolved_query_builder import attach_understanding_authority


def force_t4_abstain(contract: ResolvedQueryContract) -> ResolvedQueryContract:
    """Return a contract that ABSTAINs with ``semantic_referent`` so T4 may run."""
    attached = attach_understanding_authority(
        contract.model_copy(
            update={
                "clarification_required": True,
                "clarification_reason": "which event this refers to",
                "ambiguity_state": "clarification_required",
                "qualification_tier": "T4",
                "understanding_sufficiency": None,
                "locked_fields": {},
                "unresolved_fields": [],
                "provenance": {
                    **(contract.provenance or {}),
                    "match_path": str(
                        (contract.provenance or {}).get("match_path")
                        or contract.qualification_source
                        or "out_of_registry"
                    ),
                    "deterministic_match_path": str(
                        (contract.provenance or {}).get("deterministic_match_path")
                        or contract.qualification_source
                        or "out_of_registry"
                    ),
                },
            }
        )
    )
    locked = dict(attached.locked_fields or {})
    for key, value in (contract.locked_fields or {}).items():
        if key.startswith("entities.") or key in {
            "time_scope",
            "intent_family",
            "answer_goal",
            "normalized_goal",
        }:
            locked[key] = value
    for key, value in (contract.entities or {}).items():
        if value not in (None, "", [], {}):
            locked.setdefault(f"entities.{key}", value)
    if contract.time_scope:
        locked.setdefault("time_scope", contract.time_scope)
    sufficiency = from_understanding_state(
        required=["semantic_referent"],
        available=sorted(locked.keys()),
        missing=[],
        locked=sorted(locked.keys()),
        unresolved=["semantic_referent"],
        clarification_required=False,
        policy_blocked=False,
    )
    return attached.model_copy(
        update={
            "entities": dict(contract.entities or attached.entities or {}),
            "time_scope": contract.time_scope or attached.time_scope,
            "locked_fields": locked,
            "clarification_required": False,
            "clarification_reason": None,
            "ambiguity_state": "unambiguous",
            "unresolved_fields": ["semantic_referent"],
            "understanding_sufficiency": sufficiency.model_dump(mode="json"),
            "provenance": {
                **(attached.provenance or {}),
                "t4_owns_unresolved_semantic_referent": True,
                "explicit_user_constraints": (contract.provenance or {}).get(
                    "explicit_user_constraints"
                )
                or (attached.provenance or {}).get("explicit_user_constraints"),
            },
        }
    )
