"""T2 SPL shape extraction for T1 SPL-native rows.

Produces a structured, review-only ``SplShape`` describing what kind of SPL the
analyst is asking for (runtime operation, source profile, entity/metric fields,
windows, lookup binding).  The shape is derived deterministically from the query
and the pre-parsed hard tokens; an optional LLM-proposed shape can be merged on
top but is normalised and constrained — it can only fill gaps, never override a
hard token the analyst wrote.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.spl.runtime_source_profiles import (
    RUNTIME_OPERATIONS,
    RuntimeSourceProfile,
    resolve_profile_for_index,
)
from app.spl.t2_pre_parse import PreParsedSplTokens, pre_parse_spl_tokens

# Normalisation of common LLM operation labels to the fixed enum.
_OPERATION_LABEL_NORMALIZATION: dict[str, str] = {
    "anomaly detection": "threshold_anomaly",
    "baseline anomaly": "threshold_anomaly",
    "stdev anomaly": "threshold_anomaly",
    "outlier detection": "threshold_anomaly",
    "threshold anomaly": "threshold_anomaly",
    "ioc match": "lookup_correlation",
    "threat feed correlation": "lookup_correlation",
    "lookup match": "lookup_correlation",
    "lookup correlation": "lookup_correlation",
    "top talkers": "aggregate_and_rank",
    "highest volume": "aggregate_and_rank",
    "most frequent": "aggregate_and_rank",
    "aggregate and rank": "aggregate_and_rank",
    "timeline": "entity_timeline",
    "entity timeline": "entity_timeline",
    "sequence over time": "sequence_detection",
    "sequence detection": "sequence_detection",
}


def normalize_runtime_operation(label: str | None) -> str:
    if not label:
        return "unknown"
    key = " ".join(str(label).strip().lower().replace("_", " ").split())
    if key in _OPERATION_LABEL_NORMALIZATION:
        return _OPERATION_LABEL_NORMALIZATION[key]
    canonical = key.replace(" ", "_")
    if canonical in RUNTIME_OPERATIONS:
        return canonical
    return "unknown"


@dataclass
class SplShape:
    runtime_operation: str = "unknown"
    source_profile: str | None = None
    entity_fields: list[str] = field(default_factory=list)
    metric_fields: list[str] = field(default_factory=list)
    baseline_window: str | None = None
    detection_window: str | None = None
    lookup_name: str | None = None
    lookup_match_field: str | None = None
    log_match_field: str | None = None
    assumptions: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    missing_constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_operation": self.runtime_operation,
            "source_profile": self.source_profile,
            "entity_fields": self.entity_fields,
            "metric_fields": self.metric_fields,
            "baseline_window": self.baseline_window,
            "detection_window": self.detection_window,
            "lookup_name": self.lookup_name,
            "lookup_match_field": self.lookup_match_field,
            "log_match_field": self.log_match_field,
            "assumptions": self.assumptions,
            "missing_fields": self.missing_fields,
            "constraints": self.constraints,
            "missing_constraints": self.missing_constraints,
        }


def extract_spl_shape(
    query: str,
    *,
    tokens: PreParsedSplTokens | None = None,
    llm_shape: dict[str, Any] | None = None,
) -> SplShape:
    """Build a review-only SPL shape from the query, hard tokens, and (optional)
    an LLM-proposed shape.  Hard tokens win; the LLM shape only fills gaps."""
    tokens = tokens or pre_parse_spl_tokens(query)
    profile = resolve_profile_for_index(tokens.indexes[0] if tokens.indexes else None)

    shape = SplShape()
    shape.source_profile = profile.source_profile_id if profile else None

    # Runtime operation: deterministic hint first, then normalised LLM label.
    if tokens.operation_hints:
        shape.runtime_operation = tokens.operation_hints[0]
    elif llm_shape and llm_shape.get("runtime_operation"):
        shape.runtime_operation = normalize_runtime_operation(llm_shape.get("runtime_operation"))

    shape.entity_fields = _select_fields(tokens, profile, kind="entity")
    shape.metric_fields = _select_fields(tokens, profile, kind="metric")

    # Time windows.  ``earliest=-30d`` -> baseline; "last 24h" -> detection.
    if tokens.earliest:
        shape.baseline_window = tokens.earliest.lstrip("-")
    if tokens.relative_windows:
        shape.detection_window = tokens.relative_windows[0]

    # Lookup binding for correlation shapes.
    if tokens.lookup_files:
        shape.lookup_name = tokens.lookup_files[0]
        shape.lookup_match_field = _first_present(tokens.fields, ("indicator_ip",)) or (
            profile.lookup_fields[0] if profile and profile.lookup_fields else None
        )
        shape.log_match_field = _first_present(tokens.fields, ("dest_ip", "src_ip"))

    # Lookup-correlation groups by the source/destination correlation keys, so the
    # entity set is both src_ip and dest_ip when the profile defines them (the
    # repaired SPL stats-by uses both), not only the field named in the query.
    if shape.runtime_operation == "lookup_correlation" and profile is not None:
        correlation_keys = [f for f in ("src_ip", "dest_ip") if f in profile.entity_fields]
        if correlation_keys:
            shape.entity_fields = correlation_keys

    # Merge LLM-proposed gap-fillers (never override hard tokens).
    if llm_shape:
        _merge_llm_gaps(shape, llm_shape)

    shape.constraints = [dict(item) for item in tokens.semantic_constraints]
    shape.missing_constraints = list(tokens.missing_constraint_bindings)
    shape.missing_fields = _missing_fields(shape)
    shape.assumptions = _assumptions(shape, profile)
    return shape


def _select_fields(
    tokens: PreParsedSplTokens, profile: RuntimeSourceProfile | None, *, kind: str
) -> list[str]:
    pool = set(profile.entity_fields if kind == "entity" else profile.metric_fields) if profile else set()
    named = [f for f in tokens.fields if f in pool]
    if named:
        return named
    # Fall back to generic entity/metric heuristics when no profile is known.
    if profile:
        return []
    if kind == "entity":
        return [f for f in tokens.fields if f.endswith(("_id", "_ip"))]
    return [f for f in tokens.fields if "count" in f or f in ("bytes", "packets", "latency")]


def _first_present(values: list[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in values:
            return candidate
    return None


def _merge_llm_gaps(shape: SplShape, llm_shape: dict[str, Any]) -> None:
    if shape.runtime_operation == "unknown" and llm_shape.get("runtime_operation"):
        shape.runtime_operation = normalize_runtime_operation(llm_shape["runtime_operation"])
    if not shape.entity_fields and isinstance(llm_shape.get("entity_fields"), list):
        shape.entity_fields = [str(v) for v in llm_shape["entity_fields"] if v]
    if not shape.metric_fields and isinstance(llm_shape.get("metric_fields"), list):
        shape.metric_fields = [str(v) for v in llm_shape["metric_fields"] if v]
    if not shape.baseline_window and llm_shape.get("baseline_window"):
        shape.baseline_window = str(llm_shape["baseline_window"]).lstrip("-")
    if not shape.detection_window and llm_shape.get("detection_window"):
        shape.detection_window = str(llm_shape["detection_window"]).lstrip("-")


def _missing_fields(shape: SplShape) -> list[str]:
    missing: list[str] = []
    if shape.runtime_operation == "threshold_anomaly":
        if not shape.entity_fields:
            missing.append("entity_fields")
        if not shape.metric_fields:
            missing.append("metric_fields")
        if not shape.baseline_window:
            missing.append("baseline_window")
        if not shape.detection_window:
            missing.append("detection_window")
    elif shape.runtime_operation == "lookup_correlation":
        if not shape.lookup_name:
            missing.append("lookup_name")
        if not shape.log_match_field:
            missing.append("log_match_field")
    return missing


def _assumptions(shape: SplShape, profile: RuntimeSourceProfile | None) -> list[str]:
    notes: list[str] = []
    if profile is None and shape.source_profile is None:
        notes.append("No runtime source profile resolved; index/sourcetype need analyst validation.")
    if profile and shape.runtime_operation not in (*profile.allowed_runtime_operations, "unknown"):
        notes.append(
            f"Operation {shape.runtime_operation} is not in the {profile.source_profile_id} "
            "profile allow-list; analyst must confirm."
        )
    return notes
