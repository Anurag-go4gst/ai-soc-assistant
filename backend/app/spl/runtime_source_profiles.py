"""Runtime source profiles for T1 SPL-native generation.

A runtime source profile declares, for a Splunk index, the entity/metric fields
an analyst-grade SPL draft may reference and which runtime operations are valid
against it.  These profiles let the deterministic validator accept a review-only
SPL draft for a known source (e.g. ``index=scada_perf``) without applying an
unrelated relevance check (e.g. a DNS hunt heuristic) to an OT performance query.

These are review-only metadata.  They never make any SPL executable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Canonical runtime operation enum (mirrors the LLM/T2 contract).
RUNTIME_OPERATIONS: frozenset[str] = frozenset(
    {
        "threshold_anomaly",
        "lookup_correlation",
        "aggregate_and_rank",
        "entity_timeline",
        "sequence_detection",
        "unknown",
    }
)


@dataclass(frozen=True)
class RuntimeSourceProfile:
    source_profile_id: str
    allowed_indexes: tuple[str, ...]
    entity_fields: tuple[str, ...]
    metric_fields: tuple[str, ...]
    allowed_runtime_operations: tuple[str, ...]
    validator_profile: str
    lookup_fields: tuple[str, ...] = field(default_factory=tuple)


_RUNTIME_SOURCE_PROFILES: dict[str, RuntimeSourceProfile] = {
    "scada_perf": RuntimeSourceProfile(
        source_profile_id="scada_perf",
        allowed_indexes=("scada_perf",),
        entity_fields=("rtu_id", "asset_id", "device_id"),
        metric_fields=(
            "transmission_error_count",
            "transmission_error",
            "error_count",
            "latency",
            "packet_loss",
        ),
        allowed_runtime_operations=(
            "threshold_anomaly",
            "aggregate_and_rank",
            "entity_timeline",
        ),
        validator_profile="ot_scada_performance",
    ),
    "cisco_asa": RuntimeSourceProfile(
        source_profile_id="cisco_asa",
        allowed_indexes=("cisco_asa",),
        entity_fields=("src_ip", "dest_ip", "src_port", "dest_port"),
        metric_fields=("count", "bytes", "packets"),
        allowed_runtime_operations=(
            "lookup_correlation",
            "aggregate_and_rank",
            "entity_timeline",
        ),
        validator_profile="network_firewall",
        lookup_fields=("indicator_ip", "src_ip", "dest_ip"),
    ),
}

# Reverse index from a Splunk index name to its owning profile.
_INDEX_TO_PROFILE: dict[str, str] = {
    index: profile_id
    for profile_id, profile in _RUNTIME_SOURCE_PROFILES.items()
    for index in profile.allowed_indexes
}


def get_runtime_source_profile(profile_id: str | None) -> RuntimeSourceProfile | None:
    if not profile_id:
        return None
    return _RUNTIME_SOURCE_PROFILES.get(str(profile_id).strip().lower())


def resolve_profile_for_index(index_name: str | None) -> RuntimeSourceProfile | None:
    """Return the runtime profile that owns ``index_name`` (case-insensitive)."""
    if not index_name:
        return None
    profile_id = _INDEX_TO_PROFILE.get(str(index_name).strip().lower())
    return _RUNTIME_SOURCE_PROFILES.get(profile_id) if profile_id else None


def known_runtime_index(index_name: str | None) -> bool:
    return resolve_profile_for_index(index_name) is not None


def list_runtime_source_profiles() -> list[RuntimeSourceProfile]:
    return list(_RUNTIME_SOURCE_PROFILES.values())
