"""Hunt pattern_type sets shared by intent classification and query signals."""

from __future__ import annotations

from functools import lru_cache

from app.coverage.question_runtime_map import list_cisco_question_runtime_entries

# Exact-105 hunt/detection/lookup pattern classes that map to review-only SPL.
EXACT_105_HUNT_PATTERNS = frozenset(
    {
        "ioc_correlation",
        "dns_beaconing_dga_behavior",
        "multi_signal_correlation",
        "new_or_unusual_source",
        "threshold_anomaly",
        "lateral_movement",
        "suspicious_process_powershell",
        "dlp_exfiltration",
        "persistence_scheduled_task_service",
        "success_after_failure",
        "other_or_unclear",
        "notable_risk_lookup",
        "data_source_health",
        "threat_intel_enrichment",
        "asset_identity_context",
    }
)


@lru_cache(maxsize=1)
def cisco_hunt_pattern_types() -> frozenset[str]:
    """Cisco hunt pattern_types from cisco_question_runtime_map_v1 (excl. metadata)."""
    patterns: set[str] = set()
    for entry in list_cisco_question_runtime_entries():
        pattern_type = str(entry.get("pattern_type") or "").strip()
        if pattern_type and pattern_type != "environment_hygiene":
            patterns.add(pattern_type)
    return frozenset(patterns)
