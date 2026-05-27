from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class RouteStatus(StrEnum):
    ROUTE_READY = "route_ready"
    CLARIFICATION_REQUIRED = "clarification_required"
    CANNOT_ROUTE_MISSING_LOOKUP = "cannot_route_missing_lookup"
    CANNOT_ROUTE_MISSING_DETECTION = "cannot_route_missing_detection"
    CANNOT_ROUTE_MISSING_SOURCE = "cannot_route_missing_source"
    BLOCKED_INVALID_COMPOSITION = "blocked_invalid_composition"
    BLOCKED_INVALID_PARAMETERS = "blocked_invalid_parameters"


class RuntimeSkill(StrEnum):
    AGGREGATE_AND_RANK = "aggregate_and_rank"
    THRESHOLD_ANOMALY = "threshold_anomaly"
    SEQUENCE_DETECTION = "sequence_detection"
    LOOKUP_CORRELATION = "lookup_correlation"
    BEHAVIORAL_DETECTION_BINDING = "behavioral_detection_binding"
    METADATA_DISCOVERY = "metadata_discovery"
    ENTITY_CONTEXT_LOOKUP = "entity_context_lookup"
    NOTABLE_RISK_LOOKUP = "notable_risk_lookup"
    MULTI_SIGNAL_CORRELATION = "multi_signal_correlation"
    ENTITY_TIMELINE = "entity_timeline"


class MetricType(StrEnum):
    COUNT = "count"
    SUM = "sum"
    DISTINCT_COUNT = "distinct_count"
    ENUMERATE = "enumerate"
    LATEST = "latest"
    EARLIEST = "earliest"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class LookupStatus(StrEnum):
    APPROVED = "approved"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


ROUTE_PLAN_GENERATOR_ROLE = "route_plan_candidate_generator"
ROUTE_PLAN_GENERATOR_MODEL_FAMILY = "instruct"
ROUTE_PLAN_REASONING_MODEL_ALLOWED = False


@dataclass
class RoutePlanValidationResult:
    is_valid: bool
    normalized_route_plan: dict[str, Any] | None = None
    validation_findings: list[str] = field(default_factory=list)
    blocking_findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreflightContext:
    has_prior_context: bool = False
    explicit_entities: dict[str, str] = field(default_factory=dict)
    configured_lookups: set[str] = field(default_factory=set)
    configured_detections: set[str] = field(default_factory=set)
    unavailable_sources: set[str] = field(default_factory=set)
    threshold_policy_configured: bool = False
    baseline_policy_configured: bool = False


@dataclass
class RoutePlanPreflightResult:
    route_status: RouteStatus | None
    missing_slots: list[str] = field(default_factory=list)
    blocking_findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return self.route_status is not None

    def model_dump(self) -> dict[str, Any]:
        data = asdict(self)
        data["route_status"] = self.route_status.value if self.route_status else None
        return data


def runtime_skill_values() -> set[str]:
    return {skill.value for skill in RuntimeSkill}


def route_status_values() -> set[str]:
    return {status.value for status in RouteStatus}
