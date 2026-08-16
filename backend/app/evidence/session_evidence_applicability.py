"""Plan 8 O1A — prior-evidence applicability against a follow-up's final RQC.

Not a store. Classifies existing EvidenceState keys so only REUSABLE evidence
can satisfy EVIDENCE sufficiency. Historical unusable keys stay for provenance.
"""

from __future__ import annotations

from typing import Any, Literal

from app.evidence.minimal_evidence_state import (
    EvidenceStateItem,
    MinimalEvidenceState,
    _unique,
)

ApplicabilityStatus = Literal[
    "REUSABLE",
    "STALE",
    "OUT_OF_SCOPE",
    "SUPERSEDED",
    "INVALIDATED",
    "BLOCKED",
]

_ACCOUNT_CLASS_ALIASES = (
    ("service account", "service_account"),
    ("service-account", "service_account"),
    ("privileged", "privileged"),
    ("administrator", "administrator"),
    ("admin", "administrator"),
)
_GEO_KEYS = ("geo", "geography", "country", "src_country")
_HOST_KEYS = ("host", "hostname", "device", "asset")
_IP_KEYS = ("source_ip", "src", "ip", "destination_ip", "dest", "domain")
_INDEX_KEYS = ("index", "sourcetype")


def session_applicability_inputs(state: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Read prior scope/refs from Phase 11 pins when this turn is a scope delta."""
    resolution = state.get("session_context_resolution")
    follow_up = getattr(resolution, "follow_up_kind", None)
    pins = getattr(resolution, "pins", None)
    if pins is None:
        pins = state.get("session_pins")
    if follow_up != "scope_delta" or pins is None:
        return None, []
    if isinstance(pins, dict):
        scope = pins.get("last_evidence_scope") or pins.get("last_rqc_redacted")
        refs = [str(item) for item in (pins.get("last_evidence_refs") or []) if item]
        return (scope if isinstance(scope, dict) else None), refs
    scope = getattr(pins, "last_evidence_scope", None) or getattr(pins, "last_rqc_redacted", None)
    refs = [str(item) for item in (getattr(pins, "last_evidence_refs", None) or []) if item]
    return (scope if isinstance(scope, dict) else None), refs


def account_class_from_value(value: Any) -> str | None:
    tokens = _as_text_list(value)
    if not tokens:
        return None
    blob = " ".join(tokens).lower()
    for needle, mapped in _ACCOUNT_CLASS_ALIASES:
        if needle in blob:
            return mapped
    return None


def evaluate_evidence_applicability(
    *,
    item_scope: dict[str, Any] | None,
    new_rqc: dict[str, Any],
    prior_scope: dict[str, Any] | None = None,
    lifecycle: str | None = None,
) -> tuple[ApplicabilityStatus, list[str]]:
    """Deterministic applicability of one evidence item against the new final RQC."""
    if lifecycle == "blocked":
        return "BLOCKED", ["lifecycle_blocked"]
    if lifecycle == "invalidated":
        return "INVALIDATED", ["lifecycle_invalidated"]
    if lifecycle == "stale":
        return "STALE", ["lifecycle_stale"]

    new_entities = new_rqc.get("entities") if isinstance(new_rqc.get("entities"), dict) else {}
    prior_entities = {}
    if isinstance(prior_scope, dict) and isinstance(prior_scope.get("entities"), dict):
        prior_entities = dict(prior_scope["entities"])
    item_entities = {}
    if isinstance(item_scope, dict) and isinstance(item_scope.get("entities"), dict):
        item_entities = dict(item_scope["entities"])
    merged = {**prior_entities, **item_entities}
    if isinstance(item_scope, dict):
        for key, value in item_scope.items():
            if key != "entities" and value not in (None, "", [], {}):
                merged.setdefault(key, value)
    if isinstance(prior_scope, dict):
        for key in ("time_scope", "intent_family"):
            if key not in merged and prior_scope.get(key) not in (None, "", [], {}):
                merged[key] = prior_scope[key]

    reasons: list[str] = []

    new_account = new_entities.get("account_type") or account_class_from_value(new_entities.get("user"))
    item_account = merged.get("account_type") or account_class_from_value(merged.get("user"))
    if new_account and item_account and str(new_account) != str(item_account):
        return "OUT_OF_SCOPE", ["account_scope"]

    if _discrete_conflict(new_entities.get("user"), merged.get("user"), class_aware=True):
        return "OUT_OF_SCOPE", ["user_scope"]
    for key in _HOST_KEYS:
        if _discrete_conflict(new_entities.get(key), merged.get(key)):
            return "OUT_OF_SCOPE", ["host_scope"]
    for key in _IP_KEYS:
        if _discrete_conflict(new_entities.get(key), merged.get(key)):
            return "OUT_OF_SCOPE", ["network_scope"]
    for key in _GEO_KEYS:
        new_geo = new_entities.get(key)
        item_geo = merged.get(key)
        if new_geo and item_geo and _normalize_token(new_geo) != _normalize_token(item_geo):
            return "OUT_OF_SCOPE", ["geo_scope"]
    for key in _INDEX_KEYS:
        if _discrete_conflict(new_entities.get(key), merged.get(key)):
            return "OUT_OF_SCOPE", ["source_scope"]

    new_time = new_rqc.get("time_scope") or new_entities.get("time_window")
    item_time = merged.get("time_scope") or merged.get("time_range") or merged.get("time_window")
    if new_time and item_time and str(new_time) != str(item_time):
        reasons.append("time_scope")
        return "OUT_OF_SCOPE", reasons

    new_purpose = new_rqc.get("intent_family")
    item_purpose = merged.get("intent_family") or (prior_scope or {}).get("intent_family")
    if (
        isinstance(new_purpose, str)
        and isinstance(item_purpose, str)
        and new_purpose
        and item_purpose
        and new_purpose != item_purpose
        and {new_purpose, item_purpose} & {"knowledge_only", "policy_knowledge", "sop_or_playbook"}
    ):
        return "SUPERSEDED", ["investigation_purpose"]

    if new_rqc.get("ambiguity_state") == "policy_blocked" or new_rqc.get("clarification_required") is True:
        if new_rqc.get("ambiguity_state") == "policy_blocked":
            return "BLOCKED", ["policy_blocked"]

    return "REUSABLE", reasons


def apply_session_evidence_applicability(
    evidence: MinimalEvidenceState | dict[str, Any],
    *,
    resolved_query_contract: dict[str, Any] | None,
    prior_scope: dict[str, Any] | None,
    prior_refs: list[str] | None = None,
) -> MinimalEvidenceState:
    """Mark prior evidence applicability; drop non-REUSABLE keys from obtained."""
    if hasattr(evidence, "model_copy"):
        state = evidence
    else:
        state = MinimalEvidenceState.model_validate(evidence)
    rqc = resolved_query_contract if isinstance(resolved_query_contract, dict) else {}
    if not prior_scope and not prior_refs:
        return state

    items_by_key = {item.key: item for item in state.items}
    for ref in prior_refs or []:
        if ref not in items_by_key:
            items_by_key[ref] = EvidenceStateItem(
                key=ref,
                status="obtained",
                provenance="session_prior_evidence",
                trust_class="untrusted_evidence",
                scope={"entities": (prior_scope or {}).get("entities") or {}, "historical": True},
            )

    out_of_scope: list[str] = []
    historical: list[dict[str, Any]] = []
    reusable_obtained: list[str] = []
    updated_items: list[EvidenceStateItem] = []
    original_obtained = set(state.obtained)
    prior_ref_set = set(prior_refs or [])
    for key, item in items_by_key.items():
        historical_item = bool(item.scope.get("historical") or item.provenance == "session_prior_evidence")
        collected_this_turn = key in original_obtained and not historical_item
        use_prior = (historical_item or key in prior_ref_set) and not collected_this_turn
        status, reasons = evaluate_evidence_applicability(
            item_scope=item.scope,
            new_rqc=rqc,
            prior_scope=prior_scope if use_prior else None,
            lifecycle=item.status,
        )
        updated = item.model_copy(
            update={
                "applicability": status,
                "scope": {**item.scope, "applicability_reasons": reasons},
            }
        )
        updated_items.append(updated)
        if status != "REUSABLE":
            historical.append({"key": key, "applicability": status, "reasons": reasons})
            if status == "OUT_OF_SCOPE":
                out_of_scope.append(key)
        elif item.status == "obtained":
            reusable_obtained.append(key)

    obtained = _unique(
        [
            key
            for key in reusable_obtained
            if key in original_obtained or key in set(prior_refs or [])
        ]
    )
    usable = set(obtained) - set(state.stale) - set(state.invalidated) - set(state.blocked) - set(out_of_scope)
    missing = [key for key in state.required if key not in usable]
    provenance = dict(state.provenance or {})
    provenance["historical_unusable"] = historical
    provenance["applicability_evaluated"] = True
    return state.model_copy(
        update={
            "obtained": obtained,
            "missing": missing,
            "out_of_scope": _unique(out_of_scope),
            "items": updated_items,
            "provenance": provenance,
        }
    )


def _as_text_list(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _normalize_token(value: Any) -> str:
    return " ".join(_as_text_list(value)).lower()


def _discrete_conflict(new_value: Any, item_value: Any, *, class_aware: bool = False) -> bool:
    new_items = {item.lower() for item in _as_text_list(new_value)}
    old_items = {item.lower() for item in _as_text_list(item_value)}
    if not new_items or not old_items:
        return False
    if class_aware:
        new_class = account_class_from_value(new_value)
        old_class = account_class_from_value(item_value)
        if new_class or old_class:
            return False
    return new_items.isdisjoint(old_items)
