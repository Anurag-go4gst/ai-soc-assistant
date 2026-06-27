"""Operation-aware SOC review checklists for T1 SPL-native (T2) review-only drafts."""

from __future__ import annotations

from typing import Any

from app.spl.runtime_source_profiles import RUNTIME_OPERATIONS, resolve_profile_for_index
from app.spl.t2_pre_parse import pre_parse_spl_tokens


def is_t2_spl_native_candidate(candidate_spl: dict[str, Any] | None) -> bool:
    return isinstance(candidate_spl, dict) and candidate_spl.get("generation_mode") == "t2_spl_native_review"


def t2_spl_native_block(candidate_spl: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(candidate_spl, dict):
        return {}
    block = candidate_spl.get("t2_spl_native")
    return dict(block) if isinstance(block, dict) else {}


def build_t2_review_checklist(t2_block: dict[str, Any] | None) -> list[str]:
    """Build checklist lines from the finalized T2 shape artifact."""
    block = dict(t2_block or {})
    operation = str(block.get("runtime_operation") or "unknown")
    if operation not in RUNTIME_OPERATIONS:
        operation = "unknown"

    if operation == "threshold_anomaly":
        return _threshold_anomaly_checklist(block)
    if operation == "lookup_correlation":
        return _lookup_correlation_checklist(block)
    if operation == "aggregate_and_rank":
        return _aggregate_and_rank_checklist(block)
    if operation == "entity_timeline":
        return _entity_timeline_checklist(block)
    if operation == "sequence_detection":
        return _sequence_detection_checklist(block)
    return list(_GENERIC_T2_CHECKLIST)


def t2_card_overlays(candidate_spl: dict[str, Any] | None) -> dict[str, Any]:
    """Optional analyst-card overlays (limitations / missing_evidence) for T2 drafts."""
    if not is_t2_spl_native_candidate(candidate_spl):
        return {}
    block = t2_spl_native_block(candidate_spl)
    if (
        block.get("runtime_operation") == "threshold_anomaly"
        and block.get("source_profile") == "scada_perf"
    ):
        return {
            "limitations": list(_SCADA_THRESHOLD_ANOMALY_GAP_LABELS),
            "missing_evidence": list(_SCADA_THRESHOLD_ANOMALY_GAP_KEYS),
        }
    return {}


def query_resolves_t2_source_profile(query: str) -> bool:
    """True when the query names an index with a T2 runtime source profile."""
    tokens = pre_parse_spl_tokens(query)
    for index in tokens.indexes:
        if resolve_profile_for_index(index) is not None:
            return True
    return False


_GENERIC_T2_CHECKLIST: tuple[str, ...] = (
    "Confirm index, sourcetype, and field mappings against your source profile.",
    "Validate time window and filters before any execution.",
    "Validate any lookup or correlation fields named in the draft SPL.",
    "Review result volume and limits before execution.",
    "Treat output as review-only until analyst approval.",
)

_SCADA_THRESHOLD_ANOMALY_GAP_LABELS: tuple[str, ...] = (
    "Metric field validation missing",
    "Source index/sourcetype validation missing",
    "RTU asset cohort missing",
    "Operational baseline sign-off missing",
    "Z-score/threshold policy missing",
)

_SCADA_THRESHOLD_ANOMALY_GAP_KEYS: tuple[str, ...] = (
    "metric_field_validation",
    "source_index_sourcetype_validation",
    "rtu_asset_cohort",
    "operational_baseline_signoff",
    "zscore_threshold_policy",
)


def _join_fields(values: list[str] | None) -> str:
    items = [str(v).strip() for v in (values or []) if str(v).strip()]
    return ", ".join(items) if items else "the requested fields"


def _window_phrase(baseline: str | None, detection: str | None) -> str:
    parts: list[str] = []
    if baseline:
        parts.append(f"baseline {baseline}")
    if detection:
        parts.append(f"detection {detection}")
    return " and ".join(parts) if parts else "baseline and detection windows"


def _threshold_anomaly_checklist(block: dict[str, Any]) -> list[str]:
    profile = str(block.get("source_profile") or "the named index")
    metrics = _join_fields(list(block.get("metric_fields") or []))
    entities = _join_fields(list(block.get("entity_fields") or []))
    windows = _window_phrase(block.get("baseline_window"), block.get("detection_window"))

    items = [
        f"Confirm index and sourcetype against the {profile} source profile.",
        f"Validate metric and entity field mappings ({metrics}; {entities}).",
        f"Define the asset cohort included in the {windows}.",
        "Confirm threshold or z-score policy with operations before any detection use.",
        (
            "Treat output as review-only anomaly ranking until baseline and threshold "
            "are approved."
        ),
    ]
    if profile == "scada_perf":
        items[1] = (
            "Validate transmission_error_count and rtu_id field mappings in telemetry."
        )
        items[2] = "Define the RTU asset cohort included in the baseline window."
    return items


def _lookup_correlation_checklist(block: dict[str, Any]) -> list[str]:
    profile = str(block.get("source_profile") or "the named index")
    lookup = str(block.get("lookup_name") or "the named lookup")
    lookup_field = str(block.get("lookup_match_field") or "indicator_ip")
    log_field = str(block.get("log_match_field") or "dest_ip")
    detection = str(block.get("detection_window") or "24h")
    entities = _join_fields(list(block.get("entity_fields") or []))

    items = [
        f"Confirm index={profile} and validate field mappings ({entities or 'src_ip, dest_ip, action, _time'}).",
        f"Confirm lookup {lookup} exists and contains {lookup_field}.",
        f"Validate {lookup_field} is matched against {log_field} as intended.",
        f"Review the {detection} time window, aggregation, and result count before execution.",
        "Treat matched IOC hits as investigation leads, not proof of compromise.",
    ]
    if profile == "cisco_asa":
        items[0] = (
            "Confirm index=cisco_asa and Cisco ASA field mappings: src_ip, dest_ip, action, _time."
        )
    return items


def _aggregate_and_rank_checklist(block: dict[str, Any]) -> list[str]:
    profile = str(block.get("source_profile") or "the named index")
    entities = _join_fields(list(block.get("entity_fields") or []))
    metrics = _join_fields(list(block.get("metric_fields") or []))
    return [
        f"Confirm source index/profile ({profile}) and sourcetype mappings.",
        f"Validate grouping fields ({entities}).",
        f"Validate count/volume metric fields ({metrics}).",
        "Confirm top-N or threshold semantics before execution.",
        "Do not infer incident severity from ranking alone.",
    ]


def _entity_timeline_checklist(block: dict[str, Any]) -> list[str]:
    entities = _join_fields(list(block.get("entity_fields") or []))
    detection = str(block.get("detection_window") or "the requested window")
    return [
        f"Validate entity identifier fields ({entities}).",
        "Confirm event ordering and included event types.",
        f"Review the {detection} observation window.",
        "Avoid causal claims without supporting evidence across sources.",
    ]


def _sequence_detection_checklist(block: dict[str, Any]) -> list[str]:
    entities = _join_fields(list(block.get("entity_fields") or []))
    detection = str(block.get("detection_window") or "the requested window")
    return [
        "Validate each sequence step and ordering logic in the draft SPL.",
        f"Confirm correlation/join keys ({entities}).",
        f"Review the {detection} time window for sequence completeness.",
        "Do not declare an attack chain without corroborating evidence.",
    ]
