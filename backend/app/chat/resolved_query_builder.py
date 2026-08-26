"""Build ResolvedQueryContract from deterministic inputs — no provisional route."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.canonical_planning_input import CatalogueTier
from app.chat.contracts.explicit_user_constraints import build_explicit_user_constraints
from app.chat.contracts.intent_classification import IntentClassification, QueryToIntentResult
from app.chat.contracts.resolved_query import (
    AmbiguityState,
    AnswerGoal,
    RequestedConditionalAction,
    ResolvedQueryContract,
    UnderstandingSource,
)
from app.chat.contracts.staged_sufficiency import from_understanding_state
from app.chat.intent_classifier import build_query_to_intent
from app.chat.query_signals import extract_query_signals
from app.chat.skill_intent_compatibility import (
    CAPABILITY_MCP,
    CAPABILITY_SPL,
    _INTENT_NO_CAPABILITY,
    _INTENT_REQUIRED_CAPABILITIES,
)
from app.spl.user_constraint_bindings import build_user_constraint_bindings

_FAMILY_TO_ANSWER_GOAL: dict[str, AnswerGoal] = {
    "alert_summary": "severity_assessment",
    "knowledge_only": "policy_citation",
    "reference_knowledge": "reference_explanation",
    "clarification_required": "clarification",
    "spl_generation_only": "spl_artifact",
    "live_investigation": "live_results",
    "guided_investigation": "procedural_steps",
    "mitre_explanation": "mitre_explanation",
    "mitre_mapping": "mitre_mapping",
    "hybrid_alert_review": "live_results",
    "hybrid_investigation_plus_policy": "analyst_action_guidance",
    "policy_knowledge": "policy_citation",
    "sop_or_playbook": "procedural_steps",
    "cve_investigation": "reference_lookup",
    "github_investigation": "procedural_steps",
}


def capabilities_for_intent_family(intent_family: str) -> tuple[frozenset[str], frozenset[str]]:
    """Required and prohibited capabilities implied by an intent family.

    Reuses Plan 3 B2 tables — not a second capability authority.
    """
    if intent_family in _INTENT_REQUIRED_CAPABILITIES:
        return _INTENT_REQUIRED_CAPABILITIES[intent_family], frozenset()
    if intent_family in _INTENT_NO_CAPABILITY:
        return frozenset(), frozenset({CAPABILITY_SPL, CAPABILITY_MCP})
    return frozenset(), frozenset()


def _capabilities_for_family(intent_family: str) -> tuple[frozenset[str], frozenset[str]]:
    return capabilities_for_intent_family(intent_family)


def _ambiguity_state(intent: IntentClassification) -> AmbiguityState:
    if intent.requires_clarification:
        if intent.primary_intent == "human_review":
            return "policy_blocked" if intent.intent_family == "clarification_required" else "clarification_required"
        return "clarification_required"
    if intent.intent_family == "clarification_required":
        return "clarification_required"
    return "unambiguous"


_VALID_ANSWER_GOALS = frozenset(
    {
        "live_results",
        "analyst_action_guidance",
        "policy_citation",
        "spl_artifact",
        "mitre_mapping",
        "mitre_explanation",
        "severity_assessment",
        "procedural_steps",
        "clarification",
        "reference_lookup",
        "reference_explanation",
    }
)


def _answer_goal(intent: IntentClassification) -> AnswerGoal:
    primary = getattr(intent, "answer_goal_primary", None)
    if isinstance(primary, str) and primary in _VALID_ANSWER_GOALS:
        return primary  # type: ignore[return-value]
    goals = intent.answer_goal or []
    if goals and str(goals[0]) in _VALID_ANSWER_GOALS:
        return str(goals[0])  # type: ignore[return-value]
    return _FAMILY_TO_ANSWER_GOAL.get(intent.intent_family, "analyst_action_guidance")


def _extract_requested_conditional_actions(query: str) -> list[RequestedConditionalAction]:
    """Deterministic preservation of user-requested conditional actions on Final RQC.

    Does **not** grant eligibility, authorize writes/sends, or place actions on ResourcePlan.
    Lifecycle starts at REQUESTED (or PENDING_CONDITION when a governed predicate is present).
    """
    text = (query or "").lower()
    actions: list[RequestedConditionalAction] = []

    # Governed predicate ids only — free-text conditions are never action authority.
    predicate_id: str | None = None
    if "if the evidence confirms" in text or "if compromise" in text or "compromise is confirmed" in text:
        predicate_id = "account_compromise_confirmed"
    elif "if the evidence confirms malicious" in text or "confirms malicious activity" in text:
        predicate_id = "account_compromise_confirmed"

    lifecycle = "PENDING_CONDITION" if predicate_id else "REQUESTED"

    if any(tok in text for tok in ("remediat", "containment action", "prepare the remediation")):
        actions.append(
            RequestedConditionalAction(
                action_kind="remediation",
                lifecycle_state=lifecycle,  # type: ignore[arg-type]
                predicate_id=predicate_id,
            )
        )

    if "draft an email" in text or ("email to the" in text and "draft" in text) or (
        "email to the" in text and "summarizing" in text
    ):
        roles: list[str] = []
        if "firewall" in text:
            roles.append("firewall_team")
        if "identity" in text:
            roles.append("identity_team")
        if "incident commander" in text:
            roles.append("incident_commander")
        if "system owner" in text:
            roles.append("system_owner")
        actions.append(
            RequestedConditionalAction(
                action_kind="email_draft",
                lifecycle_state=lifecycle,  # type: ignore[arg-type]
                predicate_id=predicate_id,
                recipient_roles=roles,
            )
        )

    return actions


def _requested_outputs_from_actions(
    actions: list[RequestedConditionalAction],
) -> list[str]:
    outputs: list[str] = []
    for action in actions:
        if action.action_kind == "remediation" and "remediation_plan" not in outputs:
            outputs.append("remediation_plan")
        if action.action_kind == "email_draft" and "email_draft" not in outputs:
            outputs.append("email_draft")
    return outputs


def build_resolved_query_contract(
    *,
    query: str,
    query_understanding: Any | None = None,
    qualification_tier: CatalogueTier,
    qualification_source: str,
    understanding_source: UnderstandingSource = "deterministic_qualification",
    query_to_intent: QueryToIntentResult | dict[str, Any] | None = None,
    evidence_requirements: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
) -> ResolvedQueryContract:
    """Produce pre-route understanding without reading the provisional routed skill."""
    if query_to_intent is None:
        q2i = build_query_to_intent(
            query=query,
            query_understanding=query_understanding,
            routed_skill=None,
            routing_provenance=None,
        )
    elif isinstance(query_to_intent, QueryToIntentResult):
        q2i = query_to_intent
    else:
        q2i = QueryToIntentResult.model_validate(query_to_intent)

    intent = q2i.intent_classification
    required, prohibited = _capabilities_for_family(intent.intent_family)
    entities: dict[str, Any] = {}
    time_scope: str | None = None
    if query_understanding is not None:
        entities = _entities_map(query_understanding)
        time_scope = getattr(query_understanding, "time_window", None) or entities.get("time_window")

    ambiguity = _ambiguity_state(intent)
    # Extract explicit user literals once at the deterministic understanding seam.
    # Same object is carried into T4 grounding, DET validation, and Final RQC
    # checks via provenance — T4 must not re-parse as authority.
    explicit_constraints = build_explicit_user_constraints(
        query_understanding=query_understanding,
        query_signals=extract_query_signals(query, query_understanding),
        bindings=build_user_constraint_bindings(
            query, query_understanding=query_understanding
        ),
    )
    match_path = (q2i.candidate_mappings or {}).get("match_path") or qualification_source
    requested_actions = _extract_requested_conditional_actions(query)
    contract = ResolvedQueryContract(
        normalized_goal=query.strip(),
        intent_family=intent.intent_family,
        answer_goal=_answer_goal(intent),
        ambiguity_state=ambiguity,
        clarification_required=bool(intent.requires_clarification),
        clarification_reason=intent.reason if intent.requires_clarification else None,
        required_capabilities=required,
        prohibited_capabilities=prohibited,
        evidence_requirements=list(evidence_requirements or []),
        entities=entities,
        time_scope=time_scope if isinstance(time_scope, str) else None,
        qualification_tier=qualification_tier,
        qualification_source=qualification_source,
        confidence=float(intent.confidence),
        provenance={
            **(provenance or {}),
            "match_path": match_path,
            "deterministic_match_path": match_path,
            "observed_match_path": match_path,
            "llm_intent_assist_status": q2i.llm_intent_assist_status,
            "explicit_user_constraints": explicit_constraints.to_dict(),
            "explicit_constraint_authority_path": (
                "build_resolved_query_contract→provenance.explicit_user_constraints"
            ),
        },
        understanding_source=understanding_source,
        requested_conditional_actions=requested_actions,
        requested_outputs=_requested_outputs_from_actions(requested_actions),
    )
    return attach_understanding_authority(contract)


_ACCOUNT_CLASS_ALIASES = (
    ("service account", "service_account"),
    ("service-account", "service_account"),
    ("privileged", "privileged"),
    ("administrator", "administrator"),
    ("admin", "administrator"),
)
_ACCOUNT_CLASS_USERS = frozenset({"admin", "administrator", "privileged", "service", "service_account"})


def _account_type_from_delta(remainder: str) -> str | None:
    text = remainder.lower().strip()
    for needle, value in _ACCOUNT_CLASS_ALIASES:
        if needle in text:
            return value
    return None


def apply_session_continuity(
    contract: ResolvedQueryContract,
    *,
    prior_rqc: dict[str, Any] | None,
    delta_remainder: str | None = None,
    follow_up_kind: str | None = None,
) -> ResolvedQueryContract:
    """Fold redacted prior RQC into Phase 1 understanding for generic scope deltas.

    Retains prior entity/time pins the new message does not replace. Does not
    rewrite the follow-up into a catalogue phrase. Capabilities stay derived.
    """
    if follow_up_kind != "scope_delta" or not isinstance(prior_rqc, dict):
        return contract

    prior_entities = prior_rqc.get("entities") if isinstance(prior_rqc.get("entities"), dict) else {}
    merged_entities = {
        key: value
        for key, value in prior_entities.items()
        if _is_concrete(value)
    }
    for key, value in (contract.entities or {}).items():
        if _is_concrete(value):
            merged_entities[key] = value

    remainder = (delta_remainder or "").strip()
    if remainder:
        merged_entities["scope_delta"] = remainder
        account_type = _account_type_from_delta(remainder)
        if account_type:
            merged_entities["account_type"] = account_type
            users = merged_entities.get("user")
            if isinstance(users, list):
                kept = [
                    item
                    for item in users
                    if str(item).strip().lower() not in _ACCOUNT_CLASS_USERS
                ]
                if kept:
                    merged_entities["user"] = kept
                else:
                    merged_entities.pop("user", None)
            elif isinstance(users, str) and users.strip().lower() in _ACCOUNT_CLASS_USERS:
                merged_entities.pop("user", None)

    time_scope = contract.time_scope or (
        prior_rqc.get("time_scope") if isinstance(prior_rqc.get("time_scope"), str) else None
    )
    if not time_scope:
        prior_window = prior_entities.get("time_window")
        time_scope = prior_window if isinstance(prior_window, str) else None
    if contract.time_scope:
        merged_entities["time_window"] = contract.time_scope

    intent_family = contract.intent_family
    answer_goal = contract.answer_goal
    clarification_required = contract.clarification_required
    clarification_reason = contract.clarification_reason
    ambiguity_state = contract.ambiguity_state
    prior_family = prior_rqc.get("intent_family")
    prior_goal = prior_rqc.get("answer_goal")
    if (
        ambiguity_state != "policy_blocked"
        and isinstance(prior_family, str)
        and prior_family not in {"clarification_required", ""}
        and (
            clarification_required
            or intent_family in {"clarification_required"}
            or ambiguity_state in {"clarification_required", "insufficient_signals"}
        )
    ):
        intent_family = prior_family
        if isinstance(prior_goal, str) and prior_goal in _VALID_ANSWER_GOALS:
            answer_goal = prior_goal  # type: ignore[assignment]
        clarification_required = False
        clarification_reason = None
        ambiguity_state = "unambiguous"

    required, prohibited = capabilities_for_intent_family(intent_family)
    provenance = dict(contract.provenance or {})
    provenance["session_continuity"] = "scope_delta"
    updated = contract.model_copy(
        update={
            "intent_family": intent_family,
            "answer_goal": answer_goal,
            "ambiguity_state": ambiguity_state,
            "clarification_required": clarification_required,
            "clarification_reason": clarification_reason,
            "required_capabilities": required,
            "prohibited_capabilities": prohibited,
            "entities": merged_entities,
            "time_scope": time_scope,
            "provenance": provenance,
        }
    )
    return attach_understanding_authority(updated)


_DERIVED_FIELD_NAMES = (
    "required_capabilities",
    "prohibited_capabilities",
    "evidence_requirements",
)

_GENERIC_ENTITY_VALUES = frozenset({"multiple", "all", "any", "several", "various", "unknown"})


def _entities_map(query_understanding: Any) -> dict[str, Any]:
    raw = getattr(query_understanding, "entities", None)
    if raw is None:
        return {}
    if hasattr(raw, "model_dump"):
        dumped = raw.model_dump()
    elif isinstance(raw, dict):
        dumped = dict(raw)
    else:
        return {}
    return {key: value for key, value in dumped.items() if value not in (None, "", [], {})}


def _is_concrete(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_is_concrete(item) for item in value)
    text = str(value).strip().lower()
    return bool(text) and text not in _GENERIC_ENTITY_VALUES


def _keep_deterministic_clarification(contract: ResolvedQueryContract) -> bool:
    """True for policy/scope/unsafe facts T1–T3 must not hand to T4."""
    if contract.ambiguity_state == "policy_blocked":
        return True
    reason = str(contract.clarification_reason or "").lower()
    if "out of soc scope" in reason:
        return True
    if "unsafe" in reason or "blocked_by_policy" in reason:
        return True
    return False


def _has_exact_structured_binding(contract: ResolvedQueryContract) -> bool:
    """Exact T1–T3 entity binding, not a semantic guess."""
    for key, value in (contract.entities or {}).items():
        if key == "time_window":
            continue
        if _is_concrete(value):
            return True
    return False


def attach_understanding_authority(contract: ResolvedQueryContract) -> ResolvedQueryContract:
    """Classify T1–T3 locked vs unresolved semantic fields; mark derived fields.

    Does not create a second understanding system. Capabilities and evidence
    requirements stay derived from intent family / later deterministic recompute.
    """
    locked: dict[str, Any] = {
        "intent_family": contract.intent_family,
        "answer_goal": contract.answer_goal,
        "qualification_tier": contract.qualification_tier,
        "qualification_source": contract.qualification_source,
        "ambiguity_state": contract.ambiguity_state,
    }
    if contract.clarification_required:
        locked["clarification_required"] = True
        if contract.clarification_reason:
            locked["clarification_reason"] = contract.clarification_reason
    if contract.prohibited_capabilities:
        locked["prohibited_capabilities"] = sorted(contract.prohibited_capabilities)
    if contract.time_scope:
        locked["time_scope"] = contract.time_scope
    for key, value in (contract.entities or {}).items():
        if key == "time_window" and value and "time_scope" not in locked:
            locked["time_scope"] = value
            continue
        if _is_concrete(value):
            locked[f"entities.{key}"] = value
    if contract.qualification_tier != "T4":
        locked["normalized_goal"] = contract.normalized_goal

    clarification_required = contract.clarification_required
    clarification_reason = contract.clarification_reason
    ambiguity_state = contract.ambiguity_state
    exact_binding = _has_exact_structured_binding(contract)
    deferred_semantic_referent = False
    if (
        contract.qualification_tier == "T4"
        and clarification_required
        and not _keep_deterministic_clarification(contract)
    ):
        # Unresolved semantic interpretation is T4's job. Exact structured
        # bindings may resolve a referent without converting it into CLARIFY.
        clarification_required = False
        clarification_reason = None
        if ambiguity_state == "clarification_required":
            ambiguity_state = "unambiguous"
        locked.pop("clarification_required", None)
        locked.pop("clarification_reason", None)
        locked["ambiguity_state"] = ambiguity_state
        deferred_semantic_referent = not exact_binding

    # Architecture 2.2: do NOT invent unresolved semantic slots merely because
    # qualification_tier is T4 / out_of_registry. That recreated the forbidden
    # partial-contract patch list and forced T4 onto already-complete
    # deterministic happy paths (utility SPL authoring, fully-specified
    # review-only searches). Unresolved fields are only real semantic gaps.
    unresolved: list[str] = []
    if deferred_semantic_referent:
        unresolved.append("semantic_referent")

    sufficiency = from_understanding_state(
        required=["semantic_referent"] if deferred_semantic_referent else [],
        available=sorted(locked.keys()),
        missing=[],
        locked=sorted(locked.keys()),
        unresolved=unresolved,
        clarification_required=clarification_required,
        policy_blocked=ambiguity_state == "policy_blocked",
    )
    provenance = dict(contract.provenance or {})
    if deferred_semantic_referent:
        provenance["t4_owns_unresolved_semantic_referent"] = True
    return contract.model_copy(
        update={
            "ambiguity_state": ambiguity_state,
            "clarification_required": clarification_required,
            "clarification_reason": clarification_reason,
            "locked_fields": locked,
            "unresolved_fields": unresolved,
            "derived_field_names": list(_DERIVED_FIELD_NAMES),
            "understanding_sufficiency": sufficiency.model_dump(mode="json"),
            "provenance": provenance,
        }
    )
