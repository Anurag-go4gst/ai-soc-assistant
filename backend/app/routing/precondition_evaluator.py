"""Stage 3L-S7.1: Pure hard-precondition evaluator (no live registry reads).

Evaluates a route plan against explicitly supplied dependency state. Not wired to /chat.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Final

from app.routing.route_plan_models import RouteStatus

# Stable S7 precondition identifiers (S7.1 core).
PRECONDITION_TEMPLATE_AVAILABLE: Final[str] = "template_available"
PRECONDITION_EVIDENCE_CONTRACT_AVAILABLE: Final[str] = "evidence_contract_available"
PRECONDITION_LOOKUP_AVAILABLE: Final[str] = "lookup_available"
PRECONDITION_LOOKUP_FRESH: Final[str] = "lookup_fresh"
PRECONDITION_DETECTION_REGISTERED: Final[str] = "detection_registered"
PRECONDITION_DETECTION_VETTED: Final[str] = "detection_vetted"
PRECONDITION_SOURCE_CLASS_SUPPORTED: Final[str] = "source_class_supported"
PRECONDITION_THRESHOLD_POLICY_PRESENT: Final[str] = "threshold_policy_present"
PRECONDITION_TIME_WINDOW_PRESENT: Final[str] = "time_window_present"
PRECONDITION_PRIMARY_FIXTURE_AVAILABLE: Final[str] = "primary_fixture_available"

HARD_PRECONDITION_IDS: Final[tuple[str, ...]] = (
    PRECONDITION_TEMPLATE_AVAILABLE,
    PRECONDITION_EVIDENCE_CONTRACT_AVAILABLE,
    PRECONDITION_LOOKUP_AVAILABLE,
    PRECONDITION_LOOKUP_FRESH,
    PRECONDITION_DETECTION_REGISTERED,
    PRECONDITION_DETECTION_VETTED,
    PRECONDITION_SOURCE_CLASS_SUPPORTED,
    PRECONDITION_THRESHOLD_POLICY_PRESENT,
    PRECONDITION_TIME_WINDOW_PRESENT,
    PRECONDITION_PRIMARY_FIXTURE_AVAILABLE,
)

# Blocking finding tokens (stable strings for tests and future shadow wiring).
FINDING_MISSING_TEMPLATE: Final[str] = "missing_template"
FINDING_MISSING_EVIDENCE_CONTRACT: Final[str] = "missing_evidence_contract"
FINDING_MISSING_CONFIGURED_LOOKUP: Final[str] = "missing_configured_lookup"
FINDING_LOOKUP_STALE: Final[str] = "lookup_stale"
FINDING_MISSING_CONFIGURED_DETECTION: Final[str] = "missing_configured_detection"
FINDING_DETECTION_UNVETTED: Final[str] = "detection_unvetted"
FINDING_UNSUPPORTED_SOURCE_CLASS: Final[str] = "unsupported_source_class"
FINDING_MISSING_REQUIRED_THRESHOLD_REF: Final[str] = "missing_required_threshold_ref"
FINDING_MISSING_REQUIRED_TIME_WINDOW: Final[str] = "missing_required_time_window"
FINDING_MISSING_PRIMARY_FIXTURE: Final[str] = "missing_primary_fixture"

# Aggregate route_status priority when multiple preconditions fail (first match wins).
_ROUTE_STATUS_PRIORITY: Final[tuple[RouteStatus, ...]] = (
    RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE,
    RouteStatus.CANNOT_ROUTE_MISSING_EVIDENCE_CONTRACT,
    RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP,
    RouteStatus.CANNOT_ROUTE_LOOKUP_STALE,
    RouteStatus.CANNOT_ROUTE_MISSING_DETECTION,
    RouteStatus.CANNOT_ROUTE_UNVETTED_DETECTION,
    RouteStatus.CANNOT_ROUTE_UNSUPPORTED_SOURCE,
    RouteStatus.CANNOT_ROUTE_MISSING_PRIMARY_FIXTURE,
    RouteStatus.CLARIFICATION_REQUIRED,
    RouteStatus.ROUTE_READY,
)


@dataclass(frozen=True)
class HardPreconditionDependencyState:
    """Explicit dependency snapshot passed by the caller — no registry I/O."""

    require_template: bool = False
    require_evidence_contract: bool = False
    require_lookup: bool = False
    require_detection: bool = False
    require_source_class: bool = False
    require_threshold_policy: bool = False
    require_time_window: bool = False
    require_primary_fixture: bool = False

    template_available: bool = True
    template_sample_only: bool = False
    evidence_contract_available: bool = True
    lookup_available: bool = True
    lookup_fresh: bool = True
    detection_registered: bool = True
    detection_vetted: bool = True
    source_class_supported: bool = True
    threshold_policy_present: bool = True
    time_window_present: bool = True
    primary_fixture_available: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> HardPreconditionDependencyState:
        if not data:
            return cls()
        known = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in data.items() if key in known})


@dataclass(frozen=True)
class PreconditionFailure:
    precondition_id: str
    route_status: str
    blocking_finding: str


@dataclass
class HardPreconditionEvaluationResult:
    preconditions_checked: list[str] = field(default_factory=list)
    preconditions_passed: list[str] = field(default_factory=list)
    preconditions_failed: list[str] = field(default_factory=list)
    dependency_readiness: str = "ready"
    route_status: str = RouteStatus.ROUTE_READY.value
    blocking_findings: list[str] = field(default_factory=list)
    failures: list[PreconditionFailure] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["failures"] = [asdict(item) for item in self.failures]
        return payload


def evaluate_hard_preconditions(
    route_plan: dict[str, Any] | None,
    dependency_state: HardPreconditionDependencyState | dict[str, Any] | None = None,
    *,
    runtime_skill_contract: dict[str, Any] | None = None,
) -> HardPreconditionEvaluationResult:
    """Evaluate hard preconditions for a route plan using explicit dependency state only."""
    del runtime_skill_contract  # reserved for S7.2 catalog-driven applicability
    state = (
        dependency_state
        if isinstance(dependency_state, HardPreconditionDependencyState)
        else HardPreconditionDependencyState.from_mapping(
            dependency_state if isinstance(dependency_state, dict) else None,
        )
    )
    plan = route_plan if isinstance(route_plan, dict) else {}

    failures: list[PreconditionFailure] = []
    checked: list[str] = []

    if state.require_template:
        checked.append(PRECONDITION_TEMPLATE_AVAILABLE)
        if not state.template_available or state.template_sample_only:
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_TEMPLATE_AVAILABLE,
                    route_status=RouteStatus.CANNOT_ROUTE_MISSING_TEMPLATE.value,
                    blocking_finding=FINDING_MISSING_TEMPLATE,
                )
            )

    if state.require_evidence_contract:
        checked.append(PRECONDITION_EVIDENCE_CONTRACT_AVAILABLE)
        if not state.evidence_contract_available:
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_EVIDENCE_CONTRACT_AVAILABLE,
                    route_status=RouteStatus.CANNOT_ROUTE_MISSING_EVIDENCE_CONTRACT.value,
                    blocking_finding=FINDING_MISSING_EVIDENCE_CONTRACT,
                )
            )

    if state.require_lookup:
        checked.append(PRECONDITION_LOOKUP_AVAILABLE)
        if not state.lookup_available:
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_LOOKUP_AVAILABLE,
                    route_status=RouteStatus.CANNOT_ROUTE_MISSING_LOOKUP.value,
                    blocking_finding=FINDING_MISSING_CONFIGURED_LOOKUP,
                )
            )
        checked.append(PRECONDITION_LOOKUP_FRESH)
        if not state.lookup_fresh:
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_LOOKUP_FRESH,
                    route_status=RouteStatus.CANNOT_ROUTE_LOOKUP_STALE.value,
                    blocking_finding=FINDING_LOOKUP_STALE,
                )
            )

    if state.require_detection:
        checked.append(PRECONDITION_DETECTION_REGISTERED)
        if not state.detection_registered:
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_DETECTION_REGISTERED,
                    route_status=RouteStatus.CANNOT_ROUTE_MISSING_DETECTION.value,
                    blocking_finding=FINDING_MISSING_CONFIGURED_DETECTION,
                )
            )
        checked.append(PRECONDITION_DETECTION_VETTED)
        if not state.detection_vetted:
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_DETECTION_VETTED,
                    route_status=RouteStatus.CANNOT_ROUTE_UNVETTED_DETECTION.value,
                    blocking_finding=FINDING_DETECTION_UNVETTED,
                )
            )

    if state.require_source_class:
        checked.append(PRECONDITION_SOURCE_CLASS_SUPPORTED)
        if not state.source_class_supported:
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_SOURCE_CLASS_SUPPORTED,
                    route_status=RouteStatus.CANNOT_ROUTE_UNSUPPORTED_SOURCE.value,
                    blocking_finding=FINDING_UNSUPPORTED_SOURCE_CLASS,
                )
            )

    if state.require_threshold_policy:
        checked.append(PRECONDITION_THRESHOLD_POLICY_PRESENT)
        if not state.threshold_policy_present or not _plan_has_threshold_ref(plan):
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_THRESHOLD_POLICY_PRESENT,
                    route_status=RouteStatus.CLARIFICATION_REQUIRED.value,
                    blocking_finding=FINDING_MISSING_REQUIRED_THRESHOLD_REF,
                )
            )

    if state.require_time_window:
        checked.append(PRECONDITION_TIME_WINDOW_PRESENT)
        if not (state.time_window_present or _plan_has_time_window(plan)):
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_TIME_WINDOW_PRESENT,
                    route_status=RouteStatus.CLARIFICATION_REQUIRED.value,
                    blocking_finding=FINDING_MISSING_REQUIRED_TIME_WINDOW,
                )
            )

    if state.require_primary_fixture:
        checked.append(PRECONDITION_PRIMARY_FIXTURE_AVAILABLE)
        if not state.primary_fixture_available:
            failures.append(
                PreconditionFailure(
                    precondition_id=PRECONDITION_PRIMARY_FIXTURE_AVAILABLE,
                    route_status=RouteStatus.CANNOT_ROUTE_MISSING_PRIMARY_FIXTURE.value,
                    blocking_finding=FINDING_MISSING_PRIMARY_FIXTURE,
                )
            )

    failed_ids = [item.precondition_id for item in failures]
    passed_ids = [item for item in checked if item not in failed_ids]
    blocking = sorted({item.blocking_finding for item in failures})
    route_status = _aggregate_route_status(failures)
    readiness = _dependency_readiness(failures)

    return HardPreconditionEvaluationResult(
        preconditions_checked=checked,
        preconditions_passed=passed_ids,
        preconditions_failed=failed_ids,
        dependency_readiness=readiness,
        route_status=route_status,
        blocking_findings=blocking,
        failures=failures,
    )


def _plan_has_time_window(plan: dict[str, Any]) -> bool:
    time_window = plan.get("time_window")
    if isinstance(time_window, dict):
        earliest = time_window.get("earliest")
        latest = time_window.get("latest")
        if isinstance(earliest, str) and earliest.strip() and isinstance(latest, str) and latest.strip():
            return True
    parameters = plan.get("parameters")
    if isinstance(parameters, dict) and parameters.get("time_window"):
        return True
    return False


def _plan_has_threshold_ref(plan: dict[str, Any]) -> bool:
    parameters = plan.get("parameters")
    if isinstance(parameters, dict) and parameters.get("threshold_ref"):
        return True
    return bool(plan.get("threshold_ref"))


def _aggregate_route_status(failures: list[PreconditionFailure]) -> str:
    if not failures:
        return RouteStatus.ROUTE_READY.value
    failure_statuses = {RouteStatus(item.route_status) for item in failures}
    for status in _ROUTE_STATUS_PRIORITY:
        if status in failure_statuses:
            return status.value
    return failures[0].route_status


def _dependency_readiness(failures: list[PreconditionFailure]) -> str:
    if not failures:
        return "ready"
    clarification_only = all(
        item.route_status == RouteStatus.CLARIFICATION_REQUIRED.value for item in failures
    )
    if clarification_only:
        return "clarification_required"
    return "blocked"
