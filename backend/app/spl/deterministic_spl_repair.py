"""Deterministic SPL repair for T1 SPL-native review-only drafts.

LLM SPL is candidate-quality only.  Rather than trust arbitrary model output,
we rebuild a safe, bounded SPL from the resolved :class:`SplShape` for the two
operations we have canonical patterns for (``threshold_anomaly``,
``lookup_correlation``), and we *block* any candidate carrying unsafe commands or
known-invalid syntax (e.g. ``stdev(x) over entity``).

Every result is review-only: ``execution_eligible`` is always ``False``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.spl.t2_pre_parse import UNSAFE_SPL_COMMANDS
from app.spl.t2_shape import SplShape

# `stdev(field) over entity` is not valid SPL — eventstats uses `by`, not `over`.
_INVALID_OVER_RE = re.compile(r"\b(?:stdev|avg|count|sum|max|min)\s*\([^)]*\)\s+over\s+\w+", re.IGNORECASE)
_UNBOUNDED_INDEX_RE = re.compile(r"\bindex\s*=\s*\*", re.IGNORECASE)


@dataclass
class RepairedSpl:
    runtime_operation: str
    candidate_spl: str
    execution_eligible: bool = False  # always false — review only
    review_required: bool = True
    repaired: bool = False
    blocked: bool = False
    repairs: list[str] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)


def _detect_unsafe(candidate_spl: str) -> list[str]:
    lowered = candidate_spl.lower()
    reasons = [cmd for cmd in sorted(UNSAFE_SPL_COMMANDS) if re.search(rf"\b{cmd}\b", lowered)]
    if _UNBOUNDED_INDEX_RE.search(candidate_spl):
        reasons.append("unbounded_index")
    return reasons


def repair_spl_candidate(shape: SplShape, *, llm_candidate_spl: str | None = None) -> RepairedSpl:
    """Repair or block a candidate, rebuilding canonical SPL from the shape."""
    operation = shape.runtime_operation
    repairs: list[str] = []
    notes: list[str] = []

    if llm_candidate_spl:
        unsafe = _detect_unsafe(llm_candidate_spl)
        if unsafe:
            return RepairedSpl(
                runtime_operation=operation,
                candidate_spl="",
                blocked=True,
                block_reasons=unsafe,
                validation_notes=[f"Candidate blocked: unsafe constructs {unsafe}."],
            )
        if _INVALID_OVER_RE.search(llm_candidate_spl):
            repairs.append("rewrote_invalid_over_to_eventstats_by")
            notes.append("LLM used `stat(...) over entity`; rebuilt with `eventstats ... by entity`.")

    if operation == "threshold_anomaly":
        spl = _build_threshold_anomaly(shape, notes)
    elif operation == "lookup_correlation":
        spl = _build_lookup_correlation(shape, notes)
    else:
        return RepairedSpl(
            runtime_operation=operation,
            candidate_spl="",
            blocked=False,
            validation_notes=[
                f"No canonical repair pattern for runtime_operation={operation}; "
                "draft remains review-only and needs analyst authoring."
            ],
        )

    if spl is None:
        return RepairedSpl(
            runtime_operation=operation,
            candidate_spl="",
            blocked=False,
            validation_notes=[
                *notes,
                f"Insufficient resolved fields for {operation}; missing {shape.missing_fields}.",
            ],
        )

    # The rebuild always counts as a repair when an LLM candidate was supplied.
    if llm_candidate_spl is not None:
        repairs.append(f"rebuilt_from_shape:{operation}")
    return RepairedSpl(
        runtime_operation=operation,
        candidate_spl=spl,
        repaired=bool(repairs),
        repairs=repairs,
        validation_notes=notes,
    )


def _build_threshold_anomaly(shape: SplShape, notes: list[str]) -> str | None:
    if not (shape.source_profile and shape.entity_fields and shape.metric_fields):
        return None
    index = shape.source_profile
    entity = shape.entity_fields[0]
    metric = shape.metric_fields[0]
    baseline = shape.baseline_window or "30d"
    detection = shape.detection_window or "24h"
    if not shape.detection_window:
        notes.append("detection_window defaulted to 24h.")
    return (
        f"index={index} earliest=-{baseline} latest=now() {entity}=* {metric}=*\n"
        "| bin _time span=1h\n"
        f"| stats avg({metric}) as hourly_metric by _time {entity}\n"
        f'| eval is_recent=if(_time>=relative_time(now(), "-{detection}"), 1, 0)\n'
        "| eventstats avg(eval(if(is_recent=0, hourly_metric, null()))) as baseline_avg "
        f"stdev(eval(if(is_recent=0, hourly_metric, null()))) as baseline_stdev by {entity}\n"
        "| eval z_score=if(baseline_stdev>0, (hourly_metric-baseline_avg)/baseline_stdev, null())\n"
        "| where is_recent=1 AND z_score>=3\n"
        f"| table _time {entity} hourly_metric baseline_avg baseline_stdev z_score\n"
        "| sort -z_score"
    )


def _build_lookup_correlation(shape: SplShape, notes: list[str]) -> str | None:
    if not (shape.source_profile and shape.lookup_name):
        return None
    index = shape.source_profile
    detection = shape.detection_window or "24h"
    if not shape.detection_window:
        notes.append("detection_window defaulted to 24h.")
    log_field = shape.log_match_field or "dest_ip"
    lookup_field = shape.lookup_match_field or "indicator_ip"
    # `values(action) as actions` must table `actions`, not `action` — alias-correct.
    return (
        f"index={index} earliest=-{detection} latest=now() {log_field}=*\n"
        f"| lookup {shape.lookup_name} {lookup_field} as {log_field} OUTPUT {lookup_field} as matched_ioc\n"
        "| where isnotnull(matched_ioc)\n"
        "| stats count as event_count values(action) as actions by src_ip dest_ip matched_ioc\n"
        "| table src_ip dest_ip actions event_count matched_ioc\n"
        "| sort -event_count"
    )
