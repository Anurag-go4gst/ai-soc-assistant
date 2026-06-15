"""Stage 3K-Q2 deterministic local IOC lookup (no external HTTP)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.config import settings

_DEFAULT_IOC_REGISTRY_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "ioc_registry.sample.json"
)
from app.intel.ioc_models import IocLookupResult, IocType, StalenessStatus
from app.intel.ioc_registry import (
    _LoadedIocRegistry,
    _normalize_ioc_value,
    get_ioc_record,
    get_source,
    infer_ioc_type,
    load_ioc_registry,
)

BLOCK_CANNOT_ROUTE_LOOKUP_STALE = "cannot_route_lookup_stale"
BLOCK_LOOKUP_STALE = "lookup_stale"
BLOCK_MISSING_CONFIGURED_LOOKUP = "missing_configured_lookup"


def lookup_ioc(
    value: str,
    ioc_type: IocType | str,
    *,
    registry_path: str | Path | None = None,
) -> IocLookupResult:
    """Look up a normalized IOC value in the local registry."""
    if not settings.ioc_registry_enabled:
        return IocLookupResult(
            match=False,
            blocking_reason=f"{BLOCK_MISSING_CONFIGURED_LOOKUP}:registry_disabled",
        )

    path = _resolve_registry_path(registry_path)
    try:
        registry = load_ioc_registry(path)
    except (OSError, ValueError) as exc:
        return IocLookupResult(match=False, blocking_reason=f"{BLOCK_MISSING_CONFIGURED_LOOKUP}:{exc}")

    typed = IocType(ioc_type) if not isinstance(ioc_type, IocType) else ioc_type
    normalized = _normalize_ioc_value(value, typed)
    record = get_ioc_record(registry, normalized, typed)
    if record is None:
        return IocLookupResult(
            match=False,
            normalized_value=normalized,
            ioc_type=typed,
            blocking_reason=f"{BLOCK_MISSING_CONFIGURED_LOOKUP}:{typed.value}:{normalized}",
        )

    source = get_source(registry, record.source_id)
    if source is None:
        return IocLookupResult(
            match=False,
            normalized_value=normalized,
            ioc_type=typed,
            blocking_reason=f"{BLOCK_MISSING_CONFIGURED_LOOKUP}:unknown_source:{record.source_id}",
        )

    staleness = evaluate_source_staleness(source.last_refreshed, source.max_staleness_hours, record.expiry)
    if staleness in {StalenessStatus.STALE, StalenessStatus.EXPIRED}:
        return IocLookupResult(
            match=False,
            normalized_value=normalized,
            ioc_type=typed,
            confidence=record.confidence,
            staleness_status=staleness,
            tlp=record.tlp,
            redacted_provenance=_redacted_provenance(source, record),
            lookup_name=record.lookup_name or source.lookup_name,
            source_id=source.source_id,
            blocking_reason=BLOCK_CANNOT_ROUTE_LOOKUP_STALE if staleness == StalenessStatus.STALE else "lookup_expired",
        )

    return IocLookupResult(
        match=True,
        normalized_value=normalized,
        ioc_type=typed,
        confidence=record.confidence,
        staleness_status=staleness,
        tlp=record.tlp,
        redacted_provenance=_redacted_provenance(source, record),
        lookup_name=record.lookup_name or source.lookup_name,
        source_id=source.source_id,
    )


def evaluate_registry_staleness(registry_path: str | Path | None = None) -> StalenessStatus:
    """Return worst-case staleness across registry sources.

    Fails closed: if the registry file is missing or unreadable, treat it as
    EXPIRED (the IOC lookup is blocked) rather than raising into the pipeline.
    """
    path = _resolve_registry_path(registry_path)
    try:
        registry = load_ioc_registry(path)
    except (FileNotFoundError, OSError, ValueError, ValidationError):
        return StalenessStatus.EXPIRED
    statuses = [
        evaluate_source_staleness(source.last_refreshed, source.max_staleness_hours, None)
        for source in registry.document.sources
    ]
    if StalenessStatus.EXPIRED in statuses:
        return StalenessStatus.EXPIRED
    if StalenessStatus.STALE in statuses:
        return StalenessStatus.STALE
    return StalenessStatus.FRESH


def evaluate_source_staleness(
    last_refreshed: datetime,
    max_staleness_hours: int,
    expiry: datetime | None,
) -> StalenessStatus:
    now = datetime.now(timezone.utc)
    refreshed = last_refreshed if last_refreshed.tzinfo else last_refreshed.replace(tzinfo=timezone.utc)
    if expiry is not None:
        expiry_dt = expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)
        if now >= expiry_dt:
            return StalenessStatus.EXPIRED
    age_hours = (now - refreshed).total_seconds() / 3600.0
    if age_hours > max_staleness_hours:
        return StalenessStatus.STALE
    return StalenessStatus.FRESH


def lookup_ioc_from_text(value: str, *, registry_path: str | Path | None = None) -> IocLookupResult:
    """Infer IOC type and perform lookup."""
    inferred = infer_ioc_type(value)
    if inferred is None:
        return IocLookupResult(match=False, blocking_reason=f"{BLOCK_MISSING_CONFIGURED_LOOKUP}:unknown_ioc_type")
    return lookup_ioc(value, inferred, registry_path=registry_path)


def preflight_ioc_requirements(
    *,
    lookup_required: bool,
    ioc_values: list[str] | None = None,
    legacy_lookup_name: str | None = None,
    registry_path: str | Path | None = None,
) -> IocLookupResult | None:
    """Return blocking lookup result when IOC dependency cannot be satisfied."""
    if not settings.ioc_registry_enabled:
        if lookup_required or legacy_lookup_name:
            return IocLookupResult(
                match=False,
                blocking_reason=f"{BLOCK_MISSING_CONFIGURED_LOOKUP}:{legacy_lookup_name or 'ioc'}",
            )
        return None

    path = _resolve_registry_path(registry_path)
    registry_staleness = evaluate_registry_staleness(path)
    if registry_staleness == StalenessStatus.STALE:
        return IocLookupResult(match=False, staleness_status=registry_staleness, blocking_reason=BLOCK_CANNOT_ROUTE_LOOKUP_STALE)
    if registry_staleness == StalenessStatus.EXPIRED:
        return IocLookupResult(match=False, staleness_status=registry_staleness, blocking_reason="lookup_expired")

    if ioc_values:
        for raw in ioc_values:
            result = lookup_ioc_from_text(raw, registry_path=path)
            if not result.match:
                return result
        return IocLookupResult(match=True, staleness_status=StalenessStatus.FRESH)

    if lookup_required or legacy_lookup_name:
        return IocLookupResult(match=True, staleness_status=StalenessStatus.FRESH, lookup_name=legacy_lookup_name or "ioc")

    return None


def _resolve_registry_path(registry_path: str | Path | None) -> Path:
    if registry_path:
        return Path(registry_path)
    configured = settings.ioc_registry_path.strip()
    if configured:
        candidate = Path(configured)
        # A configured path is often relative to the repo root, but the backend
        # runs from backend/. Fall back to the packaged default when it is missing
        # so a misconfigured path never crashes the lookup.
        if candidate.exists():
            return candidate
        return _DEFAULT_IOC_REGISTRY_PATH
    return _DEFAULT_IOC_REGISTRY_PATH


def _redacted_provenance(source: object, record: object) -> str:
    from app.intel.ioc_models import IocRecord, IocSourceRecord

    assert isinstance(source, IocSourceRecord)
    assert isinstance(record, IocRecord)
    provenance = record.provenance or source.provenance
    return f"source={source.source_id}; kind={source.source_kind}; owner={source.source_owner}; label={provenance}"
