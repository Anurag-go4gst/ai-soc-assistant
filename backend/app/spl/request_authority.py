"""Deterministic request authority checks for SPL authoring paths.

This module consumes existing T1-T3 artifacts (query understanding, query
signals, and user constraint bindings). It does not route, parse user intent, or
choose a plan; it decides whether a catalog/template candidate adds material
semantics that the already-resolved user contract did not authorize.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re

from app.chat.contracts.explicit_user_constraints import (
    ExplicitUserConstraints,
    build_explicit_user_constraints,
)
from app.query_understanding.models import QueryUnderstandingResult, RequestedOutputType
from app.spl.template_registry import SplTemplateDefinition
from app.spl.user_constraint_bindings import UserConstraintBindings


_MATERIAL_FIELD_RE = re.compile(
    r"\b(?P<field>index|sourcetype|source|dest_port|src_port|app|protocol|tag)\s*=\s*"
    r"(?P<value>\"[^\"]+\"|'[^']+'|[A-Za-z0-9_.:<>-]+)",
    re.IGNORECASE,
)
_TIME_RE = re.compile(r"\bearliest=([^\s|\\]]+)(?:\s+latest=([^\s|\\]]+))?", re.IGNORECASE)
_SUBSEARCH_RE = re.compile(r"\[\s*search\b", re.IGNORECASE)
_LOOKUP_RE = re.compile(r"\|\s*lookup\s+([A-Za-z0-9_.:-]+)", re.IGNORECASE)


@dataclass(frozen=True)
class DeterministicRequestContract:
    operation: str
    requested_output_type: str
    execution_intent: str
    index: tuple[str, ...] = ()
    sourcetype: tuple[str, ...] = ()
    time_window: str | None = None
    entities: dict[str, tuple[str, ...]] = field(default_factory=dict)
    explicit_predicates: dict[str, tuple[str, ...]] = field(default_factory=dict)
    response_shape: str = "default"
    sufficient_for_spl_authoring: bool = False
    unresolved_dimensions: tuple[str, ...] = ()
    t4_allowed_dimensions: tuple[str, ...] = ()
    # P2-A: the generic, family-agnostic literal core this SPL contract composes.
    # SPL-specific judgement (sufficient_for_spl_authoring, response_shape) stays
    # above and is deliberately absent from the shared core.
    explicit_constraints: ExplicitUserConstraints | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "requested_output_type": self.requested_output_type,
            "execution_intent": self.execution_intent,
            "index": list(self.index),
            "sourcetype": list(self.sourcetype),
            "time_window": self.time_window,
            "entities": {key: list(value) for key, value in self.entities.items()},
            "explicit_predicates": {key: list(value) for key, value in self.explicit_predicates.items()},
            "response_shape": self.response_shape,
            "sufficient_for_spl_authoring": self.sufficient_for_spl_authoring,
            "unresolved_dimensions": list(self.unresolved_dimensions),
            "t4_allowed_dimensions": list(self.t4_allowed_dimensions),
            "explicit_constraints": (
                self.explicit_constraints.to_dict() if self.explicit_constraints is not None else None
            ),
        }


@dataclass(frozen=True)
class SemanticElementDecision:
    dimension: str
    value: str
    status: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "dimension": self.dimension,
            "value": self.value,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SemanticFidelityDecision:
    compatible: bool
    rejected_reasons: tuple[str, ...] = ()
    elements: tuple[SemanticElementDecision, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "rejected_reasons": list(self.rejected_reasons),
            "elements": [item.to_dict() for item in self.elements],
        }


def build_deterministic_request_contract(
    *,
    query_understanding: QueryUnderstandingResult | None,
    query_signals: dict[str, Any] | None,
    bindings: UserConstraintBindings,
) -> DeterministicRequestContract:
    signals = query_signals if isinstance(query_signals, dict) else {}
    qu = query_understanding
    output_type = str(getattr(qu, "requested_output_type", "") or "")
    if output_type.startswith("RequestedOutputType."):
        output_type = output_type.rsplit(".", 1)[-1].lower()
    explicit_spl = bool(signals.get("explicit_spl_authoring") or signals.get("review_only_spl")) or (
        getattr(qu, "requested_output_type", None) == RequestedOutputType.SPL
    )
    execution_intent = "execute" if signals.get("run_spl") or signals.get("run_execution") else "do_not_execute"
    if signals.get("review_only_spl"):
        execution_intent = "do_not_execute"

    indexes = tuple(_dedupe([*bindings.explicit_indexes, bindings.normalized_slots.get("index")]))
    sourcetypes = tuple(_dedupe([*bindings.explicit_sourcetypes, bindings.normalized_slots.get("sourcetype")]))
    time_window = (
        bindings.explicit_time_window
        or bindings.normalized_slots.get("time_window")
        or _time_window_from_qu(qu)
    )
    explicit_predicates = {
        "port": tuple(str(item) for item in bindings.explicit_ports),
        "service": tuple(bindings.explicit_services),
        "protocol": tuple(bindings.explicit_protocols),
        "lookup": tuple(bindings.explicit_lookups),
        "action": tuple(bindings.explicit_action_semantics),
        "zone": tuple([*bindings.explicit_src_zones, *bindings.explicit_dest_zones]),
        "protocol": tuple(bindings.explicit_protocols),
    }
    explicit_predicates = {key: value for key, value in explicit_predicates.items() if value}
    entities = {
        "host": tuple(bindings.explicit_hosts),
        "user": tuple(bindings.explicit_users),
        "src_ip": tuple(bindings.explicit_src_ips),
        "dest_ip": tuple(bindings.explicit_dest_ips),
        "cidr": tuple(bindings.explicit_cidrs),
    }
    entities = {key: value for key, value in entities.items() if value}
    response_shape = "spl_only" if explicit_spl and signals.get("review_only_spl") else "default"
    sufficient = bool(explicit_spl and execution_intent == "do_not_execute" and indexes and sourcetypes and time_window)
    unresolved: list[str] = []
    if explicit_spl and not indexes:
        unresolved.append("index")
    if explicit_spl and not sourcetypes:
        unresolved.append("sourcetype")
    if explicit_spl and not time_window:
        unresolved.append("time_window")
    if not explicit_spl and not signals.get("explicit_log_search") and not signals.get("live_data_request"):
        unresolved.append("operation")
    return DeterministicRequestContract(
        operation="spl_authoring" if explicit_spl else "search_or_investigate",
        requested_output_type=output_type or "unknown",
        execution_intent=execution_intent,
        index=indexes,
        sourcetype=sourcetypes,
        time_window=time_window,
        entities=entities,
        explicit_predicates=explicit_predicates,
        response_shape=response_shape,
        sufficient_for_spl_authoring=sufficient,
        unresolved_dimensions=tuple(unresolved),
        t4_allowed_dimensions=tuple(unresolved),
        explicit_constraints=build_explicit_user_constraints(
            query_understanding=qu,
            query_signals=signals,
            bindings=bindings,
        ),
    )


def check_template_semantic_fidelity(
    *,
    contract: DeterministicRequestContract,
    template: SplTemplateDefinition | None,
    rendered_spl: str | None = None,
) -> SemanticFidelityDecision:
    """Reject material candidate semantics unsupported by T1-T3 or T4 gaps."""

    text = " ".join(part for part in ((template.spl_text if template else ""), rendered_spl or "") if part)
    if not text:
        return SemanticFidelityDecision(compatible=True)

    elements: list[SemanticElementDecision] = []
    reasons: list[str] = []

    for match in _MATERIAL_FIELD_RE.finditer(text):
        field = match.group("field").lower()
        value = _clean_value(match.group("value"))
        if not value or value.startswith("<"):
            continue
        status, reason = _classify_field(field, value, contract)
        elements.append(SemanticElementDecision(field, value, status, reason))
        if status == "UNSUPPORTED_MATERIAL_ADDITION":
            reasons.append(f"{field}:{value}")

    for earliest, latest in _TIME_RE.findall(text):
        value = f"earliest={earliest}" + (f" latest={latest}" if latest else "")
        status = "SUPPORTED_EXPLICITLY" if _same_time(value, contract.time_window) else "UNSUPPORTED_MATERIAL_ADDITION"
        reason = "matches_user_time_window" if status == "SUPPORTED_EXPLICITLY" else "candidate_introduces_different_time_window"
        elements.append(SemanticElementDecision("time_window", value, status, reason))
        if status == "UNSUPPORTED_MATERIAL_ADDITION" and contract.time_window:
            reasons.append(f"time_window:{value}")

    if _SUBSEARCH_RE.search(text):
        status = "SUPPORTED_EXPLICITLY" if _secondary_scope_supported(contract) else "UNSUPPORTED_MATERIAL_ADDITION"
        elements.append(SemanticElementDecision("subsearch", "search", status, "subsearch_requires_user_supported_secondary_scope"))
        if status == "UNSUPPORTED_MATERIAL_ADDITION":
            reasons.append("subsearch:search")

    for lookup in _LOOKUP_RE.findall(text):
        lookup_text = lookup.strip()
        status = (
            "SUPPORTED_EXPLICITLY"
            if lookup_text.lower() in {item.lower() for item in contract.explicit_predicates.get("lookup", ())}
            else "UNSUPPORTED_MATERIAL_ADDITION"
        )
        elements.append(SemanticElementDecision("lookup", lookup_text, status, "lookup_requires_explicit_or_t4_gap_support"))
        if status == "UNSUPPORTED_MATERIAL_ADDITION":
            reasons.append(f"lookup:{lookup_text}")

    rejected = tuple(sorted(set(reasons)))
    return SemanticFidelityDecision(compatible=not rejected, rejected_reasons=rejected, elements=tuple(elements))


def _classify_field(
    field: str,
    value: str,
    contract: DeterministicRequestContract,
) -> tuple[str, str]:
    value_l = value.lower()
    if field == "index":
        if value_l in {item.lower() for item in contract.index}:
            return "SUPPORTED_EXPLICITLY", "matches_user_index"
        return "UNSUPPORTED_MATERIAL_ADDITION", "candidate_introduces_new_index"
    if field == "sourcetype":
        if value_l in {item.lower() for item in contract.sourcetype}:
            return "SUPPORTED_EXPLICITLY", "matches_user_sourcetype"
        return "UNSUPPORTED_MATERIAL_ADDITION", "candidate_introduces_new_sourcetype"
    if field in {"dest_port", "src_port"}:
        if value_l in {str(item).lower() for item in contract.explicit_predicates.get("port", ())}:
            return "SUPPORTED_EXPLICITLY", "matches_user_port"
        return "UNSUPPORTED_MATERIAL_ADDITION", "candidate_introduces_new_port"
    if field in {"app", "protocol"}:
        supported = {
            *{item.lower() for item in contract.explicit_predicates.get("service", ())},
            *{item.lower() for item in contract.explicit_predicates.get("protocol", ())},
        }
        if value_l in supported:
            return "SUPPORTED_EXPLICITLY", "matches_user_protocol_or_app"
        return "UNSUPPORTED_MATERIAL_ADDITION", "candidate_introduces_new_protocol_or_app"
    if field == "tag":
        if value_l in {item.lower() for item in contract.explicit_predicates.get("tag", ())}:
            return "SUPPORTED_EXPLICITLY", "matches_user_asset_tag"
        return "UNSUPPORTED_MATERIAL_ADDITION", "candidate_introduces_new_asset_tag"
    return "STRUCTURAL_ONLY", "not_a_material_authority_dimension"


def _time_window_from_qu(qu: QueryUnderstandingResult | None) -> str | None:
    entities = getattr(qu, "entities", None)
    return getattr(entities, "time_window", None) if entities is not None else None


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _clean_value(value: str) -> str:
    return str(value or "").strip().strip("\"'")


def _same_time(candidate: str, user_time: str | None) -> bool:
    if not user_time:
        return False
    return " ".join(candidate.lower().split()) == " ".join(user_time.lower().split())


def _secondary_scope_supported(contract: DeterministicRequestContract) -> bool:
    return bool(contract.explicit_predicates.get("lookup") or contract.entities or contract.t4_allowed_dimensions)
