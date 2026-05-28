"""Stage 3K-Q3 deterministic detection binding by family."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings
from app.detections.detection_models import DetectionBindingResult, DetectionRecord, VettingStatus
from app.detections.detection_registry import _LoadedDetectionRegistry, load_detection_registry

_DEFAULT_DETECTION_REGISTRY_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "detection_registry.sample.json"
)

REASON_UNKNOWN_FAMILY = "unknown_family"
REASON_UNVETTED_ONLY = "unvetted_only"
REASON_AMBIGUOUS_FAMILY = "ambiguous_family_binding"


def bind_detection(
    family: str,
    parameters: dict[str, Any] | None = None,
    *,
    registry_path: str | Path | None = None,
) -> DetectionBindingResult:
    """Resolve an approved detection_ref for a behavioral detection family."""
    normalized_family = family.strip().lower()
    if not normalized_family:
        return DetectionBindingResult(
            bound=False,
            family=family,
            unbound_reason=REASON_UNKNOWN_FAMILY,
            reasons=[REASON_UNKNOWN_FAMILY],
        )

    registry = load_detection_registry(_resolve_registry_path(registry_path))
    candidates = registry.by_family.get(normalized_family, [])
    if not candidates:
        return DetectionBindingResult(
            bound=False,
            family=normalized_family,
            unbound_reason=REASON_UNKNOWN_FAMILY,
            reasons=[REASON_UNKNOWN_FAMILY],
        )

    approved = [record for record in candidates if record.vetting_status == VettingStatus.APPROVED]
    if not approved:
        worst = candidates[0].vetting_status
        return DetectionBindingResult(
            bound=False,
            family=normalized_family,
            vetting_status=worst,
            unbound_reason=REASON_UNVETTED_ONLY,
            reasons=[REASON_UNVETTED_ONLY, f"vetting_status:{worst.value}"],
        )

    selected = _select_approved(approved, parameters or {})
    if selected is None:
        return DetectionBindingResult(
            bound=False,
            family=normalized_family,
            unbound_reason=REASON_AMBIGUOUS_FAMILY,
            reasons=[REASON_AMBIGUOUS_FAMILY],
        )

    return DetectionBindingResult(
        bound=True,
        detection_ref=selected.detection_ref,
        family=normalized_family,
        vetting_status=selected.vetting_status,
        requires_human_validation=selected.requires_human_validation,
        reasons=[f"bound:{selected.detection_ref}"],
    )


def preflight_detection_requirements(
    *,
    detection_required: bool,
    family: str | None = None,
    registry_path: str | Path | None = None,
) -> DetectionBindingResult | None:
    """Return unbound result when a detection dependency cannot be satisfied."""
    if not detection_required and not family:
        return None

    if not settings.detection_registry_enabled:
        if detection_required or family:
            return DetectionBindingResult(
                bound=False,
                family=family,
                unbound_reason="missing_configured_detection",
                reasons=["missing_configured_detection"],
            )
        return None

    if not family:
        return DetectionBindingResult(
            bound=False,
            unbound_reason=REASON_UNKNOWN_FAMILY,
            reasons=[REASON_UNKNOWN_FAMILY],
        )

    result = bind_detection(family, registry_path=registry_path)
    if not result.bound:
        return result
    return None


def _select_approved(approved: list[DetectionRecord], parameters: dict[str, Any]) -> DetectionRecord | None:
    if len(approved) == 1:
        return approved[0]

    param_keys = {key for key, value in parameters.items() if value not in (None, "", [])}
    matches = [
        record
        for record in approved
        if not record.required_inputs or set(record.required_inputs).issubset(param_keys)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return None
    return None


def _resolve_registry_path(registry_path: str | Path | None) -> Path:
    if registry_path:
        return Path(registry_path)
    configured = settings.detection_registry_path.strip()
    if configured:
        return Path(configured)
    return _DEFAULT_DETECTION_REGISTRY_PATH
