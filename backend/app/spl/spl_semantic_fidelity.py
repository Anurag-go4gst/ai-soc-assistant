"""Deterministic semantic fidelity checks for review-only SPL candidates."""

from __future__ import annotations

import re
from typing import Any

_DENIED_SPL_RE = re.compile(
    r"(action\s*=\s*(?:denied|deny|blocked|block|drop|reject)|"
    r"like\s*\(\s*action[^)]*(?:denied|deny|blocked|drop|reject)|"
    r"%denied%|%deny%|%blocked%)",
    re.I,
)
_STATS_RE = re.compile(r"\bstats\b|\btstats\b|\btimechart\b", re.I)
_SORT_DESC_RE = re.compile(r"\|\s*sort\s+-", re.I)
_SRC_GROUP_RE = re.compile(r"\b(by\s+)?src[_\s]?ip|src_ip_norm", re.I)
_HEAD_RE = re.compile(r"\|\s*head\s+(\d+)", re.I)
_EARLIEST_RE = re.compile(r"earliest\s*=\s*(-?\d+[smhdwy]+)", re.I)


def _window_token(spec_window: str | None) -> str | None:
    if not spec_window:
        return None
    match = _EARLIEST_RE.search(spec_window)
    if match:
        return match.group(1).lstrip("-")
    match = _EARLIEST_RE.search(spec_window.replace(" ", ""))
    return match.group(1).lstrip("-") if match else None


def validate_semantic_fidelity(
    spec: dict[str, Any],
    spl: str,
) -> dict[str, Any]:
    """Return preserved/lost requirements and repair feedback (not safety validation)."""
    text = str(spl or "")
    lowered = text.lower()
    losses: list[str] = []
    preserved: list[str] = []
    repair_feedback: list[str] = []

    filters = spec.get("filters") or []
    if "denied_traffic" in filters:
        if _DENIED_SPL_RE.search(text):
            preserved.append("denied_traffic")
        else:
            losses.append("denied_traffic")
            repair_feedback.append("semantic_loss:denied_traffic_filter_missing")

    if "firewall" == spec.get("event_domain"):
        if (
            "firewall" in lowered
            or "firepower" in lowered
            or "<firewall" in lowered
            or "asa" in lowered
            or (
                "denied_traffic" in filters
                and ("src" in lowered or "src_ip" in lowered)
                and _DENIED_SPL_RE.search(text)
            )
        ):
            preserved.append("firewall_domain")
        elif not (spec.get("source_constraints") or {}).get("sourcetype"):
            losses.append("firewall_domain")
            repair_feedback.append("semantic_loss:firewall_source_not_reflected")

    group_by = spec.get("group_by") or []
    if group_by and "src_ip" in group_by:
        if _SRC_GROUP_RE.search(text) or "by src" in lowered:
            preserved.append("group_by_src_ip")
        else:
            losses.append("group_by_src_ip")
            repair_feedback.append("semantic_loss:missing_source_ip_grouping")

    aggregations = spec.get("aggregations") or []
    ordering = spec.get("ordering") or []
    if aggregations or ordering or spec.get("operation_hints"):
        if _STATS_RE.search(text):
            preserved.append("aggregation")
        else:
            losses.append("aggregation")
            repair_feedback.append("semantic_loss:missing_aggregation")
        if ordering and "descending" in ordering:
            if _SORT_DESC_RE.search(text):
                preserved.append("ranking_desc")
            else:
                losses.append("ranking_desc")
                repair_feedback.append("semantic_loss:missing_descending_rank")

    spec_window = spec.get("time_window")
    window_token = _window_token(spec_window)
    if window_token:
        if f"-{window_token}" in lowered or f"earliest=-{window_token}" in lowered.replace(" ", ""):
            preserved.append("time_window")
        else:
            losses.append("time_window")
            repair_feedback.append(f"semantic_loss:time_window_must_be_{window_token}")

    literals = spec.get("explicit_literals") if isinstance(spec.get("explicit_literals"), dict) else {}
    for index_value in literals.get("indexes") or []:
        token = str(index_value or "").strip()
        if not token:
            continue
        if f"index={token}" in text.replace(" ", "") or f"index={token}" in text:
            preserved.append(f"explicit_index:{token}")
        else:
            losses.append(f"explicit_index:{token}")
            repair_feedback.append(f"semantic_loss:explicit_index_{token}_missing")
    for st_value in literals.get("sourcetypes") or []:
        token = str(st_value or "").strip()
        if not token:
            continue
        if f"sourcetype={token}" in text.replace(" ", "") or token.lower() in lowered:
            preserved.append(f"explicit_sourcetype:{token}")
        else:
            losses.append(f"explicit_sourcetype:{token}")
            repair_feedback.append(f"semantic_loss:explicit_sourcetype_{token}_missing")

    result_limit = spec.get("result_limit")
    all_logs = "all_events_no_action_filter" in filters
    head_match = _HEAD_RE.search(text)
    if result_limit is not None:
        if head_match and int(head_match.group(1)) <= result_limit:
            preserved.append("result_limit")
        else:
            losses.append("result_limit")
            repair_feedback.append(f"semantic_loss:result_limit_must_be_{result_limit}")
    elif all_logs and head_match and int(head_match.group(1)) == 100:
        losses.append("arbitrary_head_100")
        repair_feedback.append("semantic_loss:do_not_arbitrarily_head_100_for_all_logs_request")

    passed = not losses
    return {
        "passed": passed,
        "preserved": preserved,
        "losses": losses,
        "repair_feedback": repair_feedback,
    }
