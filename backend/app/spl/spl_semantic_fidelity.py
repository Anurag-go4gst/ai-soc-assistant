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


_EVAL_ONLY_CALL_RE = re.compile(
    r"\b(?:like|match|case|coalesce|mvfind|mvfilter|mvmap|mvcount|relative_time|"
    r"strftime|isnull|isnotnull|cidrmatch|typeof|tonumber|tostring|if)\s*\(",
    re.I,
)
_MVFIND_RE = re.compile(r"\bmvfind\s*\(", re.I)
_MVFILTER_CROSS_FIELD_RE = re.compile(
    r"mvfilter\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\s*==\s*[A-Za-z_][A-Za-z0-9_]*\s*\)",
    re.I,
)
_MVMAP_EXACT_RE = re.compile(
    r"mvmap\s*\(\s*([A-Za-z_][\w]*)\s*,\s*if\s*\(\s*\1\s*==\s*[A-Za-z_][\w]*\s*,\s*1\s*,\s*0\s*\)\s*\)",
    re.I,
)
_SEEN_BEFORE_MAX_RE = re.compile(
    r"seen_before\s*=\s*coalesce\s*\(\s*max\s*\(\s*exact_matches\s*\)\s*,\s*0\s*\)",
    re.I,
)
_WHERE_SEEN_BEFORE_ZERO_RE = re.compile(r"\|\s*where\s+seen_before\s*=\s*0\b", re.I)
_MVFILTER_CROSS_FIELD_REPAIR = (
    "mvfilter() may reference only one field. Use "
    "mvmap(baseline_objects, if(baseline_objects==<object>,1,0)), then "
    "seen_before=coalesce(max(exact_matches),0) and keep rows where seen_before=0."
)
_AS_NEW_HOST_RE = re.compile(r"\bas\s+new_host\b", re.I)
_TOKEN_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
_BASELINE_PERIOD_ASSIGN_RE = re.compile(
    r"eval\s+([A-Za-z_][\w]*)\s*=\s*if\s*\(\s*period\s*==?\s*[\"']baseline[\"']\s*,\s*([A-Za-z_][\w]*)",
    re.I,
)
_STREAMSTATS_VALUES_BY_RE = re.compile(
    r"streamstats\s+values\(\s*([A-Za-z_][\w]*)\s*\)(?:\s+as\s+[A-Za-z_][\w]*)?\s+by\s+([^|\n]+)",
    re.I,
)
_BIN_TIME_RE = re.compile(r"\bbin\s+_time\b|\btimechart\b", re.I)
_STATS_CMD_RE = re.compile(r"\b(?:stats|tstats)\b", re.I)
_SUBJECT_ALIASES = {
    "user": ("user", "user_norm", "account", "username", "src_user", "account_name", "targetusername"),
    "host": ("host", "host_norm", "dest_host", "dvc", "computername"),
    "src_ip": ("src_ip", "src_ip_norm", "src", "source_ip"),
}
_OBJECT_ALIASES = {
    "host": ("host", "host_norm", "dest_host", "dest", "dvc", "computername", "object_norm", "new_host"),
    "domain": ("domain", "domain_norm", "query", "object_norm", "dest_domain"),
}
_EXTRA_CORRELATION_REPAIR = (
    "The historical host baseline must be accumulated separately per account. "
    "Source IP is an output field and must not partition the historical baseline. "
    "Use the subject specified by the semantic contract only."
)
_LATE_BIN_REPAIR = (
    "The request requires one-hour windows. _time must still exist when the "
    "hourly bin is applied. Do not aggregate away _time before bin _time span=1h."
)
_SEQUENCE_HOST_REPAIR = (
    "The failure burst and later successful login must be correlated by user and "
    "source IP only. Destination host is an output from the success event and must "
    "not partition the sequence."
)
_SEQUENCE_BURST_REPAIR = (
    "Qualify the failure burst inside the requested window first, snapshot the "
    "count and first/last failure times, then correlate a later successful login. "
    "Do not count failures inside a window that ends at the success timestamp."
)
_SEQUENCE_AFTER_REPAIR = (
    "The successful login must occur after the last failure in the qualified burst, "
    "not before it."
)
_PARENT_CHILD_CMD_REPAIR = (
    "powershell in command_line must not satisfy the child-process constraint. "
    "Bind the child to Image / New_Process_Name / child_process."
)
_PARENT_CHILD_PARENT_REPAIR = (
    "winword or excel in the child process must not satisfy the parent. "
    "Bind the parent to ParentImage / Parent_Process_Name / parent_process."
)
_PARENT_CHILD_DIRECTION_REPAIR = (
    "Parent to child direction must be explicit: parent fields constrain the "
    "launcher, child fields constrain the launched process."
)
_CHILD_ROLE_FIELDS = (
    "Image",
    "New_Process_Name",
    "child_process",
    "process_name",
)
_PARENT_ROLE_FIELDS = (
    "ParentImage",
    "Parent_Process_Name",
    "parent_process",
    "parent_process_name",
)
_COMMAND_LINE_FIELDS = (
    "CommandLine",
    "command_line",
    "process_command_line",
)
_JOIN_APPEND_RE = re.compile(r"\|\s*(?:join|append)\b|\[\s*search\b", re.I)
_FIELDS_AFTER_RE = re.compile(r"\|\s*(?:fields|table)\s+([^|]+)", re.I)


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


def _has_exact_mvmap_membership(text: str) -> bool:
    return bool(
        _MVMAP_EXACT_RE.search(text)
        and _SEEN_BEFORE_MAX_RE.search(text)
        and _WHERE_SEEN_BEFORE_ZERO_RE.search(text)
    )


def _spl_search_lookback_seconds(spl: str) -> int | None:
    match = _EARLIEST_RE.search(str(spl or ""))
    if not match:
        return None
    return _token_seconds(match.group(1).lstrip("-"))


def _observation_baseline_overlap(spec: dict[str, Any], text: str) -> bool:
    """True when baseline membership is taken from events that include observation."""
    observation = str(spec.get("observation_window") or "").strip()
    baseline = str(spec.get("baseline_window") or "").strip()
    if not observation or not baseline:
        return False
    assign = re.search(
        r"baseline_object\s*=\s*if\s*\(\s*([^,]+)\s*,",
        text,
        re.I,
    )
    if not assign:
        return bool(re.search(r"baseline_object\s*=", text, re.I)) and (
            'period="baseline"' not in text.lower().replace(" ", "")
        )
    cond = assign.group(1).lower().replace(" ", "").replace("'", '"')
    if 'period="baseline"' in cond:
        return False
    if 'period="observation"' in cond:
        return True
    if f'-{baseline.lower()}' in cond:
        return True
    return True


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


def _rel_field(spec: dict[str, Any], rel_type: str, key: str, fallback: str) -> str:
    for item in spec.get("relationships") or []:
        if isinstance(item, dict) and item.get("type") == rel_type and item.get(key):
            return str(item.get(key))
    roles = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
    values = roles.get("subject" if key == "subject" else "target") or []
    if values:
        return str(values[0])
    return fallback


def _alias_match(token: str, aliases: tuple[str, ...]) -> bool:
    compact = str(token or "").strip().lower()
    return compact in {item.lower() for item in aliases}


def _first_seen_accumulation(spec: dict[str, Any], text: str) -> dict[str, Any]:
    """Semantic streamstats accumulation: baseline-only object field, by subject only."""
    subject = _rel_field(spec, "first_seen", "subject", "user")
    obj = _rel_field(spec, "first_seen", "object", "host")
    subject_aliases = _SUBJECT_ALIASES.get(subject, (subject, f"{subject}_norm"))
    object_aliases = _OBJECT_ALIASES.get(obj, (obj, f"{obj}_norm", "object_norm"))
    assigns = {
        match.group(1).lower(): match.group(2).lower()
        for match in _BASELINE_PERIOD_ASSIGN_RE.finditer(text)
    }
    stream = _STREAMSTATS_VALUES_BY_RE.search(text)
    by_keys: list[str] = []
    extra_keys: list[str] = []
    accumulated = False
    if stream:
        src_field = stream.group(1).lower()
        by_keys = [part.strip().lower() for part in stream.group(2).split(",") if part.strip()]
        extra_keys = [key for key in by_keys if not _alias_match(key, subject_aliases)]
        object_field = assigns.get(src_field)
        accumulated = bool(object_field and _alias_match(object_field, object_aliases))
    return {
        "accumulated": accumulated,
        "has_streamstats": "streamstats" in text.lower(),
        "by_keys": by_keys,
        "extra_keys": extra_keys,
        "subject": subject,
        "object": obj,
    }


def _grain_bin_reachable(spl: str, grain: str) -> tuple[bool, bool]:
    """Return (has_matching_bin, time_reachable_at_bin)."""
    commands = [part.strip() for part in re.split(r"\s*\|\s*", str(spl or "")) if part.strip()]
    grain_l = grain.strip().lower()
    bin_idx: int | None = None
    has_matching_bin = False
    for index, command in enumerate(commands):
        if not _BIN_TIME_RE.search(command):
            continue
        bin_idx = index
        has_matching_bin = (not grain_l) or f"span={grain_l}" in command.lower().replace(" ", "")
        if has_matching_bin:
            break
    if bin_idx is None:
        return False, False
    for command in commands[:bin_idx]:
        if not _STATS_CMD_RE.search(command):
            continue
        by_match = re.search(r"\bby\s+(.+)$", command, re.I)
        by_clause = by_match.group(1) if by_match else ""
        if not re.search(r"\b_time\b", by_clause):
            return has_matching_bin, False
    return has_matching_bin, True


def _sequence_burst_then_follow(text: str) -> dict[str, bool]:
    """EVENT_A burst in WINDOW_A, carried forward, EVENT_B after last EVENT_A."""
    windowed = bool(re.search(r"streamstats[^|]*time_window\s*=", text, re.I))
    carry = bool(re.search(r"\|\s*streamstats[^|]*\blast\s*\(", text, re.I))
    after = bool(
        re.search(
            r"_time\s*>\s*(burst_last|last_failure|event_a_last|prev_time)",
            text,
            re.I,
        )
    )
    return {
        "windowed_burst": windowed,
        "burst_carried": carry,
        "success_after_burst": after,
        "established": windowed and carry and after,
    }


def _assignment_haystack(text: str, fields: tuple[str, ...]) -> str:
    chunks: list[str] = []
    for field in fields:
        escaped = re.escape(field)
        assign = re.compile(rf"(?<![A-Za-z0-9_]){escaped}\s*=\s*([^\s|,]+)", re.I)
        chunks.extend(match.group(1) for match in assign.finditer(text))
        like = re.compile(
            rf"like\s*\(\s*{escaped}\s*,\s*[\"']([^\"']+)[\"']",
            re.I,
        )
        chunks.extend(match.group(1) for match in like.finditer(text))
    return " ".join(chunks).lower()


def _process_token_present(token: str, haystack: str) -> bool:
    needle = str(token).lower().replace(".exe", "")
    return bool(needle) and needle in haystack


def _any_process_token(tokens: list[Any], haystack: str) -> bool:
    return any(_process_token_present(str(item), haystack) for item in tokens)


def _parent_child_repair_child(spec: dict[str, Any]) -> str:
    process = spec.get("process_constraints") if isinstance(spec.get("process_constraints"), dict) else {}
    child = " or ".join(str(item) for item in (process.get("child") or []) if str(item).strip()) or "the child process"
    parent = " or ".join(str(item) for item in (process.get("parent") or []) if str(item).strip()) or "the parent process"
    return (
        f"The requested relationship is {parent} launching {child}. "
        f"{child} must be proven in the child-process semantic field, "
        "not merely present in command-line text."
    )


def _parent_child_repair_lineage() -> str:
    return (
        "parent_process, child_process and command_line are requested outputs but are "
        "removed by the current stats command. Preserve them through aggregation."
    )


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

    search_command = text.split("|", 1)[0]
    if _EVAL_ONLY_CALL_RE.search(search_command):
        losses.append("eval_function_in_search_command")
        losses.append("command_context_invalid")
        repair_feedback.append("semantic_loss:eval_function_in_search_command")
    else:
        preserved.append("search_command_predicates_only")

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
        elif shape == "first_seen" and (
            _has_exact_mvmap_membership(text) or "seen_before" in lowered
        ):
            # First-seen distinctness is exact baseline exclusion, not a dc() column.
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
        elif "src_ip" in correlate:
            preserved.append("group_by_src_ip")
        event_sets = [str(item) for item in (spec.get("required_event_sets") or []) if str(item).strip()]
        if len(event_sets) >= 2:
            base = text.split("|", 1)[0]
            if re.search(r"\)\s+\(", base):
                losses.append("sequence_event_union_missing")
                repair_feedback.append("semantic_loss:sequence_event_union_missing")
            else:
                preserved.append("sequence_event_union")
        correlate_keys = {str(item).lower() for item in (roles_for_seq.get("correlate_by") or [])}
        if "host" not in correlate_keys:
            overcorrelated = False
            for match in re.finditer(r"\|\s*(?:streamstats|stats)[^|]*\bby\s+([^|]+)", lowered):
                if re.search(r"\bhost(?:_norm)?\b", match.group(1)):
                    overcorrelated = True
                    break
            if overcorrelated:
                losses.append("sequence_host_overcorrelation")
                repair_feedback.append(_SEQUENCE_HOST_REPAIR)
            else:
                preserved.append("sequence_host_not_correlation_key")
        burst = _sequence_burst_then_follow(text)
        threshold_n = spec.get("explicit_threshold_value")
        comparison = str(spec.get("explicit_threshold_comparison") or "greater_than").strip().lower()
        if threshold_n is not None and comparison in {"", "greater_than", "gt", ">"}:
            compact_ops = re.sub(r"\s+", "", lowered)
            names = ("failure_count", "burst_count", "event_a_count", "lockout_count")
            inclusive = any(f"{name}>={int(threshold_n)}" in compact_ops for name in names)
            exclusive = any(
                f"{name}>{int(threshold_n)}" in compact_ops
                and f"{name}>={int(threshold_n)}" not in compact_ops
                for name in names
            )
            if inclusive and not exclusive:
                losses.append("sequence_threshold_inclusive")
                repair_feedback.append(
                    f"semantic_loss:failure_burst_must_be_greater_than_{threshold_n}_not_at_least"
                )
        if spec.get("explicit_threshold_present") and analytical.get("kind") == "sequence":
            if burst["established"]:
                preserved.append("sequence_burst_then_follow")
            else:
                losses.append("sequence_burst_not_established_before_follow")
                repair_feedback.append(_SEQUENCE_BURST_REPAIR)
            if burst["success_after_burst"]:
                preserved.append("sequence_success_after_burst")
            else:
                losses.append("sequence_success_before_failure")
                repair_feedback.append(_SEQUENCE_AFTER_REPAIR)

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
            losses.append("baseline_unreachable")
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
        exclusion_tokens = (
            "mvmap",
            "seen_before",
            "exact_matches",
            "mvfilter",
            "mvfind",
            "baseline",
            "isnull",
            "new_host",
            "new_object",
            "first_seen",
            "absent",
        )
        if any(token in lowered for token in exclusion_tokens):
            preserved.append("first_seen_relation")
        else:
            losses.append("first_seen_relation_missing")
            repair_feedback.append("semantic_loss:first_seen_relation_missing")
        if _MVFILTER_CROSS_FIELD_RE.search(text):
            losses.append("mvfilter_cross_field")
            losses.append("exact_membership_missing")
            repair_feedback.append(_MVFILTER_CROSS_FIELD_REPAIR)
        elif _MVFIND_RE.search(text) or (
            "mvfind" in lowered and not _has_exact_mvmap_membership(text)
        ):
            losses.append("regex_membership")
            losses.append("exact_membership_missing")
            repair_feedback.append("semantic_loss:exact_membership_required_not_regex")
        elif _has_exact_mvmap_membership(text):
            preserved.append("exact_membership")
        else:
            losses.append("exact_membership_missing")
            repair_feedback.append("semantic_loss:exact_membership_missing")
        if _observation_baseline_overlap(spec, text):
            losses.append("observation_baseline_overlap")
            repair_feedback.append(
                "The baseline window must immediately precede the observation window "
                "and must not include observation events."
            )
        accumulation = _first_seen_accumulation(spec, text)
        if accumulation["accumulated"]:
            preserved.append("first_seen_subject_accumulation")
        else:
            losses.append("first_seen_subject_accumulation_missing")
            repair_feedback.append(
                "semantic_loss:first_seen_must_accumulate_baseline_objects_by_subject_via_streamstats"
            )
        extra_keys = list(accumulation.get("extra_keys") or [])
        if extra_keys:
            losses.append("first_seen_extra_correlation_key")
            repair_feedback.append(_EXTRA_CORRELATION_REPAIR)
        subject = str(accumulation.get("subject") or "")
        by_keys = [str(item) for item in (accumulation.get("by_keys") or [])]
        subject_aliases = _SUBJECT_ALIASES.get(subject, (subject, f"{subject}_norm"))
        if by_keys and not any(_alias_match(key, subject_aliases) for key in by_keys):
            losses.append("first_seen_subject_wrong")
            repair_feedback.append(
                "Historical membership must be accumulated per the requested subject "
                f"({subject}), not a different entity."
            )
        if subject == "user" and not any(
            token in lowered for token in ("by user", "by user_norm", "by account")
        ):
            losses.append("same_account_comparison_missing")
            repair_feedback.append("semantic_loss:same_account_comparison_missing")
        grain = str(spec.get("temporal_grain") or "").strip()
        if grain:
            has_bin, time_ok = _grain_bin_reachable(text, grain)
            if not has_bin:
                losses.append("time_bucket_missing")
                repair_feedback.append("semantic_loss:time_bucket_missing")
            elif not time_ok:
                losses.append("required_temporal_grain_unreachable")
                repair_feedback.append(_LATE_BIN_REPAIR)
            else:
                preserved.append("temporal_grain")
        object_entities = {
            str(item).lower()
            for item in ((roles.get("target") or []) if isinstance(roles, dict) else [])
        }
        required_out = {str(item).lower() for item in (spec.get("required_outputs") or [])}
        if ("domain" in object_entities or "domain" in required_out) and _AS_NEW_HOST_RE.search(
            text
        ):
            losses.append("output_entity_mismatch")
            repair_feedback.append("semantic_loss:output_entity_mismatch")
        elif "domain" in required_out and not re.search(r"\bas\s+domain\b", lowered):
            losses.append("output_entity_mismatch")
            repair_feedback.append("semantic_loss:output_entity_mismatch")

    output_aliases = {
        "user": ("user", "account", "user_norm"),
        "host": ("host", "dest", "new_host", "dest_host", "host_norm"),
        "src_ip": ("src_ip", "source_ip", "src", "src_ip_norm"),
        "distinct_new_host_count": ("dc(", "distinct_new", "distinct_count"),
        "domain": ("domain", "query", "domain_norm"),
        "first_seen": ("first_seen", "earliest(_time)"),
        "last_seen": ("last_seen", "latest(_time)"),
        "command_line": ("command_line", "commandline", "process_command_line"),
        "parent_process": ("parent_process", "parent_process_name"),
        "child_process": ("child_process", "new_process_name"),
        "failure_count": ("failure_count",),
        "first_failure_time": ("first_failure", "first_event_a"),
        "success_time": ("success_time", "event_b_time"),
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

    if shape == "first_seen" or first_seen_rel:
        obj = _rel_field(spec, "first_seen", "object", "host")
        stats_cmds = re.findall(r"\|\s*stats\s+([^|]+)", text, re.I)
        if obj == "host":
            last_stats = stats_cmds[-1] if stats_cmds else ""
            fields_match = re.search(r"\|\s*fields\s+([^|]+)", text, re.I)
            surface = f"{last_stats} {fields_match.group(1) if fields_match else ''}"
            if _AS_NEW_HOST_RE.search(surface) or re.search(r"\bnew_host\b", surface, re.I):
                preserved.append("output:new_host")
            else:
                losses.append("output_missing:new_host")
                repair_feedback.append("semantic_loss:output_missing:new_host")
            dc_fields = [item.lower() for item in _DC_RE.findall(text)]
            host_ok = {item.lower() for item in _OBJECT_ALIASES["host"]}
            if not any(field in host_ok for field in dc_fields):
                losses.append("distinct_count_not_host_field")
                repair_feedback.append("semantic_loss:distinct_count_must_use_actual_host_field")
        required_out = {str(item).lower() for item in (spec.get("required_outputs") or [])}
        if stats_cmds and ("src_ip" in required_out or "source_ip" in required_out):
            last_stats = stats_cmds[-1]
            if re.search(r"src_ip|source_ip", last_stats, re.I):
                preserved.append("output:src_ip_survives_stats")
            else:
                losses.append("output_missing:src_ip")
                repair_feedback.append("semantic_loss:source_ip_must_survive_aggregation")

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
        child = list(spec["process_constraints"].get("child") or [])
        parent = list(spec["process_constraints"].get("parent") or [])
        child_hay = _assignment_haystack(text, _CHILD_ROLE_FIELDS)
        parent_hay = _assignment_haystack(text, _PARENT_ROLE_FIELDS)
        cmd_hay = _assignment_haystack(text, _COMMAND_LINE_FIELDS)
        child_in_child = _any_process_token(child, child_hay)
        parent_in_parent = _any_process_token(parent, parent_hay)
        child_in_parent = _any_process_token(child, parent_hay)
        parent_in_child = _any_process_token(parent, child_hay)
        child_in_cmd = _any_process_token(child, cmd_hay)
        if child_in_parent and parent_in_child and not (child_in_child and parent_in_parent):
            losses.append("parent_child_inverted")
            repair_feedback.append(
                "Parent and child are inverted. The launcher belongs in the parent-process "
                "field; the launched process belongs in the child-process field."
            )
        if child and not child_in_child:
            losses.append("child_process_not_proven")
            if child_in_cmd:
                repair_feedback.append(_parent_child_repair_child(spec))
            else:
                repair_feedback.append("semantic_loss:child_process_not_proven")
        if parent and not parent_in_parent:
            losses.append("parent_process_missing")
            if parent_in_child:
                repair_feedback.append(_PARENT_CHILD_PARENT_REPAIR)
            else:
                repair_feedback.append("semantic_loss:parent_process_missing")
        if parent and child:
            unrelated = bool(_JOIN_APPEND_RE.search(text))
            if unrelated or not (child_in_child and parent_in_parent):
                if "parent_child_inverted" not in losses:
                    losses.append("parent_child_relationship_missing")
                    repair_feedback.append(_PARENT_CHILD_DIRECTION_REPAIR)
        stats_hits = list(re.finditer(r"\|\s*stats\s+", text, re.I))
        if stats_hits:
            tail = text[stats_hits[-1].start():]
            stats_body = tail.split("|", 2)
            stats_cmd = stats_body[1] if len(stats_body) > 1 else tail
            later = "|".join(stats_body[2:]) if len(stats_body) > 2 else ""
            lineage_fields = ("parent_process", "child_process", "command_line")
            referenced = []
            for match in _FIELDS_AFTER_RE.finditer(later):
                referenced.extend(part.strip().lower() for part in match.group(1).split(",") if part.strip())
            stats_l = stats_cmd.lower()
            for field in lineage_fields:
                named_in_fields = any(field in item for item in referenced)
                kept_in_stats = field in stats_l
                required = field in {str(item).lower() for item in (spec.get("required_outputs") or [])}
                if (named_in_fields or required) and not kept_in_stats:
                    losses.append("field_lineage_missing")
                    repair_feedback.append(_parent_child_repair_lineage())
                    break
            for output_name in spec.get("required_outputs") or []:
                aliases = output_aliases.get(str(output_name), (str(output_name),))
                if any(alias.lower() in tail.lower() for alias in aliases):
                    preserved.append(f"output_survives_stats:{output_name}")
                elif str(output_name) in {"first_seen", "last_seen", "event_count"}:
                    continue
                else:
                    losses.append(f"output_dropped_by_stats:{output_name}")
                    repair_feedback.append(_parent_child_repair_lineage())
        required_out = {str(item).lower() for item in (spec.get("required_outputs") or [])}
        if "first_seen" in required_out and not re.search(
            r"earliest\s*\(\s*_time\s*\)|min\s*\(\s*_time\s*\)", text, re.I
        ):
            losses.append("output_missing:first_seen")
            repair_feedback.append("semantic_loss:output_missing:first_seen")
        if "last_seen" in required_out and not re.search(
            r"latest\s*\(\s*_time\s*\)|max\s*\(\s*_time\s*\)", text, re.I
        ):
            losses.append("output_missing:last_seen")
            repair_feedback.append("semantic_loss:output_missing:last_seen")

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
