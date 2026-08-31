"""Deterministic semantic fidelity checks for review-only SPL candidates."""

from __future__ import annotations

import re
from typing import Any

_DENIED_SPL_RE = re.compile(
    # The deterministic compiler emits filters in the quoted form (action="denied"),
    # so the optional quote is needed to credit a filter that IS present. A query
    # with no denied/blocked filter at all still reports the loss.
    r"(action\s*=\s*[\"']?(?:denied|deny|blocked|block|drop|reject)|"
    r"like\s*\(\s*action[^)]*(?:denied|deny|blocked|drop|reject)|"
    r"%denied%|%deny%|%blocked%)",
    re.I,
)
_STATS_RE = re.compile(r"\bstats\b|\btstats\b|\btimechart\b", re.I)
_SORT_DESC_RE = re.compile(r"\|\s*sort\s+-", re.I)
_SRC_GROUP_RE = re.compile(r"\b(by\s+)?src[_\s]?ip|src_ip_norm", re.I)
_HEAD_RE = re.compile(r"\|\s*head\s+(\d+)", re.I)
_EARLIEST_RE = re.compile(r"earliest\s*=\s*(-?\d+[smhdwy]+)", re.I)
_THRESHOLD_WHERE_RE = re.compile(r"\|\s*where\s+[^|]*?(?:>=?|<=?)\s*(\d+)", re.I)
_STREAMSTATS_WINDOW_RE = re.compile(r"streamstats[^|\n]*time_window\s*=\s*(\d+[smhd])", re.I)
_TIMECHART_SPAN_RE = re.compile(r"timechart[^|\n]*span\s*=\s*(\d+[smhd])", re.I)
_DC_RE = re.compile(r"\bdc\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", re.I)
_EVENT_SET_TOKENS = {
    "failed_login": ("4625", "action=failure", "action=failed", "failed"),
    "successful_login": ("4624", "action=success", "successful_login"),
    "password_change": ("4723", "4724", "password_change", "password"),
    "account_lockout": ("4740", "lockout"),
    "privilege_change": ("4728", "4732", "4756", "privilege_change"),
    "denied_traffic": ("action=denied", "action=blocked", "action=drop"),
}


_TOKEN_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def _window_token(spec_window: str | None) -> str | None:
    if not spec_window:
        return None
    match = _EARLIEST_RE.search(spec_window)
    if match:
        return match.group(1).lstrip("-")
    match = _EARLIEST_RE.search(spec_window.replace(" ", ""))
    return match.group(1).lstrip("-") if match else None


def _token_seconds(token: str | None) -> int | None:
    match = re.fullmatch(r"(\d+)([smhdw])", str(token or "").strip().lower())
    if not match:
        return None
    return int(match.group(1)) * _TOKEN_SECONDS[match.group(2)]


def _spl_search_lookback_seconds(spl: str) -> int | None:
    match = _EARLIEST_RE.search(str(spl or ""))
    if not match:
        return None
    return _token_seconds(match.group(1).lstrip("-"))


def _baseline_retrieval_reachable(spec: dict[str, Any], spl: str) -> bool:
    observation = str(spec.get("observation_window") or "").strip()
    baseline = str(spec.get("baseline_window") or "").strip()
    obs_sec = _token_seconds(observation)
    base_sec = _token_seconds(baseline)
    if obs_sec is None or base_sec is None:
        return True
    required = obs_sec + base_sec
    got = _spl_search_lookback_seconds(spl)
    return got is not None and got >= required


def _quoted_string_contains_newline(text: str, quote: str) -> bool:
    i = 0
    n = len(text)
    while i < n:
        if text[i] != quote:
            i += 1
            continue
        i += 1
        while i < n:
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                break
            if ch == "\n":
                return True
            i += 1
        i += 1
    return False


def validate_spl_structure(spl: str) -> list[str]:
    """Lightweight structural hazards — not a Splunk parser."""
    text = str(spl or "")
    errors: list[str] = []
    if text.count('"') % 2 != 0:
        errors.append("unbalanced_quotes")
    if text.count("'") % 2 != 0:
        errors.append("unbalanced_single_quotes")
    if text.count("(") != text.count(")"):
        errors.append("unbalanced_parentheses")
    if re.search(r"\|\s*\|", text) or re.search(r"^\s*\|", text, re.M) and not re.search(r"\S\s*\|", text):
        if re.search(r"\|\s*\|", text):
            errors.append("invalid_pipeline_boundary")
    if _quoted_string_contains_newline(text, '"') or _quoted_string_contains_newline(text, "'"):
        errors.append("broken_multiline_expression")
    if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\(\s*\|", text):
        errors.append("malformed_function_call")
    return errors


def validate_semantic_fidelity(
    spec: dict[str, Any],
    spl: str,
) -> dict[str, Any]:
    """Return preserved/lost requirements and repair feedback (not safety validation)."""
    text = str(spl or "")
    lowered = text.lower()
    # Quote-stripped view for `field=value` token checks. The compiler writes
    # every filter quoted, so 'action="failure"' must satisfy the bare token
    # 'action=failure'. Used only for token presence, never for safety checks.
    _unquoted = lowered.replace('"', "").replace("'", "")
    losses: list[str] = []
    preserved: list[str] = []
    repair_feedback: list[str] = []
    shape = str(spec.get("analysis_shape") or "")

    structural = validate_spl_structure(text)
    if structural:
        losses.append("malformed_structure")
        repair_feedback.extend(f"structural:{item}" for item in structural)

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
    roles = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
    subject = (roles.get("subject") or ([group_by[0]] if group_by else []))
    if group_by and "src_ip" in group_by:
        if _SRC_GROUP_RE.search(text) or "by src" in lowered:
            preserved.append("group_by_src_ip")
        else:
            losses.append("group_by_src_ip")
            losses.append("wrong_grouping_entity")
            repair_feedback.append("semantic_loss:missing_source_ip_grouping")
    elif subject:
        token = str(subject[0])
        if token.lower() not in lowered and f"{token}_norm".lower() not in lowered:
            losses.append("wrong_grouping_entity")
            repair_feedback.append(f"semantic_loss:missing_grouping_entity_{token}")

    aggregations = spec.get("aggregations") or []
    ordering = spec.get("ordering") or []
    require_aggregation = shape in {"aggregation", "ranking", "trend"} or (
        not shape and (aggregations or ordering or spec.get("operation_hints"))
    )
    if require_aggregation and shape != "raw":
        if _STATS_RE.search(text) or (shape == "rolling" and "streamstats" in lowered):
            preserved.append("aggregation")
        else:
            losses.append("aggregation")
            repair_feedback.append("semantic_loss:missing_aggregation")
        if ordering and "descending" in ordering and shape == "ranking":
            if _SORT_DESC_RE.search(text):
                preserved.append("ranking_desc")
            else:
                losses.append("ranking_desc")
                repair_feedback.append("semantic_loss:missing_descending_rank")

    spec_window = spec.get("search_horizon") or spec.get("time_window")
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
    prohibitions = {str(item) for item in (spec.get("prohibitions") or [])}
    if result_limit is not None:
        if head_match and int(head_match.group(1)) <= result_limit:
            preserved.append("result_limit")
        else:
            losses.append("result_limit")
            repair_feedback.append(f"semantic_loss:result_limit_must_be_{result_limit}")
    elif (all_logs or "arbitrary_head_100" in prohibitions) and head_match and int(head_match.group(1)) == 100:
        losses.append("arbitrary_head_100")
        losses.append("arbitrary_truncation")
        repair_feedback.append("semantic_loss:do_not_arbitrarily_head_100_for_all_logs_request")
    elif "arbitrary_truncation" in prohibitions and head_match:
        losses.append("arbitrary_truncation")
        repair_feedback.append("semantic_loss:arbitrary_truncation")

    window = spec.get("analytical_window") if isinstance(spec.get("analytical_window"), dict) else {}
    if shape == "rolling" or (window.get("kind") == "rolling"):
        size = str(window.get("size") or "")
        stream_match = _STREAMSTATS_WINDOW_RE.search(text)
        if stream_match and (not size or stream_match.group(1).lower() == size.lower()):
            preserved.append("rolling_window")
        else:
            losses.append("rolling_window_missing")
            repair_feedback.append("semantic_loss:rolling_window_missing")

    if spec.get("distinct_by"):
        dc_fields = {item.lower() for item in _DC_RE.findall(text)}
        expected = {str(item).lower() for item in spec["distinct_by"]}
        expected_norm = {f"{item}_norm" for item in expected}
        if dc_fields & (expected | expected_norm):
            preserved.append("distinct_count")
        else:
            losses.append("distinct_count_missing")
            repair_feedback.append("semantic_loss:distinct_count_missing")

    for event_name in spec.get("required_event_sets") or []:
        tokens = _EVENT_SET_TOKENS.get(str(event_name), (str(event_name),))
        # The compiler emits filters quoted (action="failure"), so a bare
        # `field=value` token must also be matched in its quoted spelling.
        # Presence still has to be real: a query with no such filter still fails.
        if any(token.lower() in _unquoted for token in tokens):
            preserved.append(f"event_set:{event_name}")
        else:
            losses.append("required_event_type_missing")
            repair_feedback.append(f"semantic_loss:required_event_type_missing:{event_name}")

    if shape == "sequence" or spec.get("ordered_sequence"):
        ordered = [str(item) for item in (spec.get("ordered_sequence") or [])]
        if ordered:
            positions = [lowered.find(item.lower()) for item in ordered]
            if any(pos < 0 for pos in positions) or positions != sorted(positions):
                losses.append("sequence_ordering_missing")
                repair_feedback.append("semantic_loss:sequence_ordering_missing")
            else:
                preserved.append("sequence_ordering")
        if spec.get("sequence_max_gap"):
            gap = str(spec["sequence_max_gap"]).lower()
            seconds = None
            match = re.fullmatch(r"(\d+)([smhd])", gap)
            if match:
                seconds = int(match.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
            if gap in lowered or (seconds is not None and str(seconds) in text) or f"maxspan={gap}" in lowered:
                preserved.append("sequence_gap")
            else:
                losses.append("sequence_gap_missing")
                repair_feedback.append("semantic_loss:sequence_gap_missing")
        analytical = spec.get("analytical_window") if isinstance(spec.get("analytical_window"), dict) else {}
        agg_window = str(analytical.get("size") or "").strip().lower()
        if analytical.get("kind") == "sequence" and agg_window and agg_window != str(spec.get("sequence_max_gap") or "").strip().lower():
            if agg_window in lowered.replace(" ", "") or f"time_window={agg_window}" in lowered.replace(" ", ""):
                preserved.append("sequence_aggregation_window")
            else:
                losses.append("sequence_aggregation_window_missing")
                repair_feedback.append("semantic_loss:sequence_aggregation_window_missing")
        correlate = []
        roles_for_seq = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
        correlate.extend(str(item) for item in (roles_for_seq.get("correlate_by") or []))
        correlate.extend(str(item) for item in (spec.get("group_by") or []))
        if "src_ip" in correlate and not re.search(r"\bby\b[^|\n]*src_ip", lowered):
            losses.append("same_source_correlation_missing")
            repair_feedback.append("semantic_loss:same_source_correlation_missing")

    if shape == "trend":
        grain = str(spec.get("temporal_grain") or "")
        span = _TIMECHART_SPAN_RE.search(text)
        if "timechart" not in lowered:
            losses.append("time_series_shape_missing")
            repair_feedback.append("semantic_loss:time_series_shape_missing")
        else:
            preserved.append("time_series_shape")
        if grain and (not span or span.group(1).lower() != grain.lower()) and f"span={grain}" not in lowered:
            losses.append("time_bucket_missing")
            repair_feedback.append("semantic_loss:time_bucket_missing")
        elif grain:
            preserved.append("temporal_grain")

    if not spec.get("explicit_threshold_present"):
        for where_clause in re.findall(r"\|\s*where\s+([^|]+)", text, re.I):
            if "_time" in where_clause.lower() or "prev_time" in where_clause.lower():
                continue
            amount = re.search(r"(?:>=?|<=?)\s*(\d+)", where_clause)
            if amount and int(amount.group(1)) > 1:
                losses.append("unexpected_threshold")
                repair_feedback.append("semantic_loss:unexpected_threshold")
                break

    for item in spec.get("normalization_requirements") or []:
        if not isinstance(item, dict):
            continue
        alias = str(item.get("alias") or "").strip()
        if not alias:
            continue
        created = bool(re.search(rf"\b{re.escape(alias)}\s*=", text, re.I))
        if not created:
            continue
        after_eval = lowered.split(alias.lower(), 1)[-1]
        consumed = bool(
            re.search(
                rf"\b(by|dc\s*\(|where|streamstats|timechart|stats)\b[^|]*\b{re.escape(alias.lower())}\b",
                after_eval,
            )
            or f"dc({alias.lower()})" in after_eval
        )
        if not consumed:
            losses.append("normalized_field_unused")
            repair_feedback.append(f"semantic_loss:normalized_alias_unused:{alias}")
        else:
            preserved.append(f"normalized:{alias}")

    if spec.get("actor_patterns"):
        for pattern in spec["actor_patterns"]:
            token = str(pattern).rstrip("*").lower()
            if token and token not in lowered:
                losses.append("actor_pattern_missing")
                repair_feedback.append(f"semantic_loss:actor_pattern_missing:{pattern}")
            else:
                preserved.append(f"actor:{pattern}")

    observation = str(spec.get("observation_window") or "").strip()
    baseline = str(spec.get("baseline_window") or "").strip()
    if observation:
        obs_compact = lowered.replace(" ", "")
        if f"-{observation}" in obs_compact or f'relative_time(now(),"-{observation}")' in obs_compact:
            preserved.append("observation_window")
        else:
            losses.append("observation_window_missing")
            repair_feedback.append(f"semantic_loss:observation_window_missing:{observation}")
    if baseline:
        compact = lowered.replace(" ", "")
        has_period = "baseline" in lowered or "period=" in lowered
        reachable = _baseline_retrieval_reachable(spec, text)
        if (f"-{baseline}" in compact or has_period) and reachable:
            preserved.append("baseline_window")
        elif not reachable:
            losses.append("baseline_data_unreachable")
            repair_feedback.append(
                "semantic_loss:baseline_data_unreachable:"
                "search_envelope_must_cover_observation_plus_baseline"
            )
        else:
            losses.append("baseline_window_missing")
            repair_feedback.append(f"semantic_loss:baseline_window_missing:{baseline}")
        if (
            observation
            and f"-{observation}" in compact
            and f"-{baseline}" not in compact
            and not has_period
            and reachable
        ):
            losses.append("baseline_window_missing")

    first_seen_rel = any(
        isinstance(item, dict) and item.get("type") == "first_seen"
        for item in (spec.get("relationships") or [])
    )
    if shape == "first_seen" or first_seen_rel:
        exclusion_tokens = ("mvfind", "baseline", "isnull", "new_host", "first_seen", "absent")
        if any(token in lowered for token in exclusion_tokens):
            preserved.append("first_seen_relation")
        else:
            losses.append("first_seen_relation_missing")
            repair_feedback.append("semantic_loss:first_seen_relation_missing")
        subject = ""
        if isinstance(roles, dict) and roles.get("subject"):
            subject = str(roles["subject"][0])
        if subject == "user" and not any(
            token in lowered for token in ("by user", "by user_norm", "by account")
        ):
            losses.append("same_account_comparison_missing")
            repair_feedback.append("semantic_loss:same_account_comparison_missing")

    output_aliases = {
        "user": ("user", "account", "user_norm"),
        "host": ("host", "dest", "new_host", "dest_host", "host_norm"),
        "src_ip": ("src_ip", "source_ip", "src", "src_ip_norm"),
        "distinct_new_host_count": ("dc(", "distinct_new", "distinct_count"),
        "domain": ("domain", "query", "domain_norm"),
        "first_seen": ("first_seen", "earliest(_time)"),
        "last_seen": ("last_seen", "latest(_time)"),
        "command_line": ("command_line", "commandline", "process_command_line"),
        "parent_process": ("parent", "parentimage", "parent_process"),
        "child_process": ("powershell", "image", "child", "new_process_name"),
        "failure_count": ("failure_count",),
        "first_failure_time": ("first_failure", "first_match", "min(first_failure"),
        "success_time": ("success_time", "last_match"),
        "event_count": ("event_count", "count as event_count"),
        "connection_count": ("connection_count", "count as connection_count"),
    }
    for output_name in spec.get("required_outputs") or []:
        aliases = output_aliases.get(str(output_name), (str(output_name),))
        if str(output_name) in {"event_count", "connection_count"}:
            has_count = bool(re.search(r"\bcount\s+as\s+\w+", lowered)) or "event_count" in lowered or "connection_count" in lowered
            if has_count:
                preserved.append(f"output:{output_name}")
            else:
                losses.append(f"output_missing:{output_name}")
                repair_feedback.append(f"semantic_loss:output_missing:{output_name}")
            continue
        if any(alias.lower() in lowered for alias in aliases):
            preserved.append(f"output:{output_name}")
        else:
            losses.append(f"output_missing:{output_name}")
            repair_feedback.append(f"semantic_loss:output_missing:{output_name}")

    if spec.get("explicit_threshold_present") and spec.get("explicit_threshold_value") is not None:
        token = str(spec["explicit_threshold_value"])
        if token not in lowered.replace(" ", ""):
            losses.append("threshold_missing")
            repair_feedback.append(f"semantic_loss:threshold_missing:{token}")
        else:
            preserved.append(f"threshold:{token}")

    for field_name in spec.get("unresolved_required_fields") or []:
        token = str(field_name)
        if token.lower() not in lowered:
            losses.append("unresolved_field_mapping")
            repair_feedback.append(f"semantic_loss:unresolved_field_mapping:{token}")

    if spec.get("process_constraints") and isinstance(spec.get("process_constraints"), dict):
        child = spec["process_constraints"].get("child") or []
        parent = spec["process_constraints"].get("parent") or []
        for item in child:
            if str(item).lower().replace(".exe", "") not in lowered:
                losses.append("process_child_missing")
                repair_feedback.append(f"semantic_loss:process_child_missing:{item}")
        for item in parent:
            if str(item).lower().replace(".exe", "") not in lowered:
                losses.append("process_parent_missing")
                repair_feedback.append(f"semantic_loss:process_parent_missing:{item}")
        if parent and child:
            relation_tokens = ("parentimage", "parent_process", "parent_process_name")
            if not any(token in lowered.replace(" ", "") for token in relation_tokens):
                losses.append("parent_child_relation_missing")
                repair_feedback.append("semantic_loss:parent_child_relation_missing")

    if spec.get("support_status") == "unsupported":
        losses.append(str(spec.get("degrade_reason") or "unsupported_analysis_shape"))
        repair_feedback.append("semantic_loss:unsupported_shape_fail_closed")

    losses = list(dict.fromkeys(losses))
    passed = not losses
    return {
        "passed": passed,
        "preserved": preserved,
        "losses": losses,
        "repair_feedback": repair_feedback,
        "structural_errors": structural,
    }
