"""Explicit user literal constraints — the generic, family-agnostic core.

Frozen ``architecture.md`` "Explicit user literals vs derived observations":
facts stated **directly and unambiguously by the user** remain **binding DET
validation constraints** even when T1-T3 abstains from semantic authority. They
originate from USER_INTENT, not from a T1-T3 semantic commit, so they are *not*
a partial semantic contract and must not be treated as locked fields for
field-level T4 patching.

T4 may receive them for grounding. T4 **MUST NOT** materially contradict them.
DET **MUST reject** a proposal that does (see :meth:`ExplicitUserConstraints.material_contradictions`).

Scope discipline (P2-A):

* This carries **literals only** — what the user actually said. The architecture
  names exactly these: IP/domain/hash, username/hostname/asset identifier,
  explicit index, explicit sourcetype, explicit time expression, explicit
  requested output form, explicit execution constraint, explicit action
  prohibition or scope limitation.
* It deliberately carries **no SPL semantic judgement** — no
  ``sufficient_for_spl_authoring``, no SPL ``response_shape``, no inferred
  source family, no guessed investigation family. Those stay in the SPL domain
  contract, which *composes* this core.
* Derived observations are **not** constraints and never appear here.

This is a projection, not an authority: no LLM, no route, no capability grant,
no execution decision, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

#: Entity dimensions carried as literals.
ENTITY_DIMENSIONS = ("host", "user", "src_ip", "dest_ip", "cidr", "domain", "file_hash")

#: Non-entity match predicates the user stated explicitly.
PREDICATE_DIMENSIONS = ("port", "service", "protocol", "action", "zone", "lookup", "event_code")

#: Where the user explicitly scoped the data. Named as the architecture names
#: them ("explicit index", "explicit sourcetype"); these are user-stated literals,
#: not an inferred source family.
DATA_SCOPE_DIMENSIONS = ("index", "sourcetype")


def _clean(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        items: list[Any] = [values]
    elif isinstance(values, Mapping):
        items = list(values.values())
    elif isinstance(values, (list, tuple, set, frozenset)):
        items = list(values)
    else:
        items = [values]
    out: list[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return tuple(out)


_TIME_UNITS = {
    "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "m": "m", "min": "m", "mins": "m", "minute": "m", "minutes": "m",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "d": "d", "day": "d", "days": "d",
    "w": "w", "week": "w", "weeks": "w",
    "mon": "mon", "month": "mon", "months": "mon",
    "y": "y", "year": "y", "years": "y",
}

_TIME_TOKEN = re.compile(r"(\d+)\s*([a-z]+)")


def time_signature(value: Any) -> tuple[str, int] | None:
    """Canonical (unit, amount) for a time expression, or None if not comparable.

    Deliberately notation-agnostic: ``last 2 hours``, ``2h`` and
    ``earliest=-2h latest=now`` all yield ``("h", 2)``. Returning ``None`` means
    "cannot be compared", which callers must treat as *not* a contradiction —
    a contradiction has to be provable, never presumed from differing notation.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    for amount, unit in _TIME_TOKEN.findall(text):
        canonical = _TIME_UNITS.get(unit)
        if canonical:
            try:
                return (canonical, int(amount))
            except ValueError:  # pragma: no cover - regex guarantees digits
                return None
    return None


def _prune(mapping: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    return {key: _clean(value) for key, value in mapping.items() if _clean(value)}


@dataclass(frozen=True)
class ExplicitUserConstraints:
    """Literal user-stated constraints. Binding for DET validation."""

    entities: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    predicates: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    data_scope: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    time_window: str | None = None
    requested_output_type: str | None = None
    execution_prohibited: bool = False
    prohibitions: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (
            self.entities
            or self.predicates
            or self.data_scope
            or self.time_window
            or self.requested_output_type
            or self.execution_prohibited
            or self.prohibitions
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": {k: list(v) for k, v in self.entities.items()},
            "predicates": {k: list(v) for k, v in self.predicates.items()},
            "data_scope": {k: list(v) for k, v in self.data_scope.items()},
            "time_window": self.time_window,
            "requested_output_type": self.requested_output_type,
            "execution_prohibited": self.execution_prohibited,
            "prohibitions": list(self.prohibitions),
        }

    def to_grounding_payload(self) -> dict[str, Any]:
        """Structured form handed to T4 for grounding.

        Labelled EXPLICIT_USER_LITERAL_CONSTRAINTS at the prompt boundary. T4 may
        use these to understand the request; it may not contradict them.
        """
        payload = self.to_dict()
        return {key: value for key, value in payload.items() if value not in (None, {}, [], False)}

    def material_contradictions(self, proposal: Mapping[str, Any] | None) -> tuple[str, ...]:
        """Return contradiction codes where ``proposal`` materially conflicts.

        "Material" means the proposal asserts a *different* value on a dimension
        the user pinned — not merely that it omitted one. Omission is not
        contradiction: T4 is allowed to say less than the user did.
        """
        if not proposal:
            return ()
        found: list[str] = []

        proposed_entities = proposal.get("entities")
        if isinstance(proposed_entities, Mapping):
            for dimension, pinned in self.entities.items():
                proposed = _clean(proposed_entities.get(dimension))
                if proposed and not set(proposed) & set(pinned):
                    found.append(f"entity_contradiction:{dimension}")

        proposed_scope = proposal.get("data_scope")
        if isinstance(proposed_scope, Mapping):
            for dimension, pinned in self.data_scope.items():
                proposed = _clean(proposed_scope.get(dimension))
                if proposed and not set(proposed) & set(pinned):
                    found.append(f"data_scope_contradiction:{dimension}")

        if self.time_window:
            proposed_time = proposal.get("time_scope") or proposal.get("time_window")
            pinned_signature = time_signature(self.time_window)
            proposed_signature = time_signature(proposed_time)
            # Only a *provable* difference counts. "last 2 hours" and
            # "earliest=-2h latest=now" are the same window in different notations
            # and must not be rejected; 2h vs 24h must be.
            if (
                proposed_signature is not None
                and pinned_signature is not None
                and proposed_signature != pinned_signature
            ):
                found.append("time_window_contradiction")

        if self.execution_prohibited:
            execute = proposal.get("execute")
            intent = str(proposal.get("execution_intent") or "").strip().lower()
            if execute is True or intent == "execute":
                found.append("execution_prohibition_contradiction")

        if self.requested_output_type:
            proposed_output = proposal.get("requested_output_type")
            if proposed_output and str(proposed_output).strip().lower() != self.requested_output_type.strip().lower():
                found.append("requested_output_contradiction")

        for prohibition in self.prohibitions:
            requested = _clean(proposal.get("requested_actions"))
            if prohibition in {item.lower() for item in requested}:
                found.append(f"action_prohibition_contradiction:{prohibition}")

        return tuple(sorted(set(found)))


def build_explicit_user_constraints(
    *,
    query_understanding: Any | None = None,
    query_signals: Mapping[str, Any] | None = None,
    bindings: Any | None = None,
) -> ExplicitUserConstraints:
    """Extract the generic literal core from the existing extraction primitives.

    Reuses ``UserConstraintBindings`` (the single existing entity/time extractor)
    rather than introducing a second parser. Callers that already built bindings
    for SPL pass them straight through, so extraction happens once per turn.
    """
    signals: Mapping[str, Any] = query_signals if isinstance(query_signals, Mapping) else {}
    b = bindings

    def bound(name: str) -> Any:
        return getattr(b, name, None) if b is not None else None

    entities = _prune(
        {
            "host": bound("explicit_hosts"),
            "user": bound("explicit_users"),
            "src_ip": bound("explicit_src_ips"),
            "dest_ip": bound("explicit_dest_ips"),
            "cidr": bound("explicit_cidrs"),
        }
    )
    predicates = _prune(
        {
            "port": bound("explicit_ports"),
            "service": bound("explicit_services"),
            "protocol": bound("explicit_protocols"),
            "action": bound("explicit_action_semantics"),
            "lookup": bound("explicit_lookups"),
            "event_code": bound("explicit_event_codes"),
            "zone": tuple([*_clean(bound("explicit_src_zones")), *_clean(bound("explicit_dest_zones"))]),
        }
    )

    normalized = bound("normalized_slots") or {}
    normalized = normalized if isinstance(normalized, Mapping) else {}
    data_scope = _prune(
        {
            "index": tuple([*_clean(bound("explicit_indexes")), *_clean(normalized.get("index"))]),
            "sourcetype": tuple(
                [*_clean(bound("explicit_sourcetypes")), *_clean(normalized.get("sourcetype"))]
            ),
        }
    )

    time_window = bound("explicit_time_window") or normalized.get("time_window") or None
    time_window = str(time_window).strip() if time_window else None

    output_type = str(getattr(query_understanding, "requested_output_type", "") or "")
    if output_type.startswith("RequestedOutputType."):
        output_type = output_type.rsplit(".", 1)[-1]
    output_type = output_type.strip().lower() or None

    # An explicit "do not execute" / review-only ask is an execution prohibition.
    # Absence of a run request is NOT a prohibition — only an explicit one counts.
    execution_prohibited = bool(signals.get("review_only_spl") or signals.get("do_not_execute"))

    prohibitions: list[str] = []
    if execution_prohibited:
        prohibitions.append("do_not_execute")
    for key in ("prohibited_actions", "explicit_prohibitions"):
        prohibitions.extend(item.lower() for item in _clean(signals.get(key)))

    return ExplicitUserConstraints(
        entities=entities,
        predicates=predicates,
        data_scope=data_scope,
        time_window=time_window,
        requested_output_type=output_type,
        execution_prohibited=execution_prohibited,
        prohibitions=tuple(sorted(set(prohibitions))),
    )
