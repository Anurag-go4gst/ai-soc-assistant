"""S3 — compiler and postprocessor preserve temporal/normalization dependencies."""

from __future__ import annotations

import re

from app.spl.llm_plan_compiler import (
    compile_intent_spec_to_spl,
    compile_plan_to_spl,
    event_set_fragment,
    render_field_eq,
)
from app.spl.review_only_spl_postprocessor import normalize_review_only_spl
from app.spl.spl_intent_spec import build_spl_intent_spec


def test_rolling_compile_preserves_window_and_distinct() -> None:
    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    spl = compile_intent_spec_to_spl(spec)
    assert "streamstats time_window=10m" in spl
    assert "dc(user_norm)" in spl or "dc(user)" in spl
    assert "by src_ip_norm" in spl or "by src_ip" in spl
    assert "head 100" not in spl
    assert "user_norm=" in spl
    assert "src_ip_norm=" in spl


def test_trend_compile_preserves_grain_and_horizon() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    spl = compile_intent_spec_to_spl(spec)
    assert "earliest=-24h" in spl
    assert "timechart span=1h" in spl
    assert "failed" in spl.lower() or "4625" in spl
    assert "head 100" not in spl


def test_sequence_compile_preserves_order_and_gap() -> None:
    spec = build_spl_intent_spec(
        "password change followed by successful login within 5 minutes"
    )
    spl = compile_intent_spec_to_spl(spec)
    assert "password_change" in spl
    assert "successful_login" in spl
    # SOC-STD-SPL-001-Q11 requires the explicit `sort 0 + _time` form before
    # streamstats; the bare `sort 0 _time` is the same sort but hard-fails the lint.
    assert "sort 0 + _time" in spl
    assert "300" in spl or "maxspan=5m" in spl
    assert "head 100" not in spl
    assert re.search(r"\)\s+\(", spl.split("|", 1)[0]) is None


def test_sequence_threshold_and_process_parent_child_compile() -> None:
    failed = build_spl_intent_spec(
        "Write review-only SPL to identify accounts with more than 20 failed logins "
        "within 15 minutes followed by a successful login from the same source IP. "
        "Return user, source IP, destination host, failure count and success time. "
        "Do not execute."
    )
    failed_spl = compile_intent_spec_to_spl(failed)
    assert "failure_count>20" in failed_spl.replace(" ", "")
    assert "time_window=15m" in failed_spl
    process = build_spl_intent_spec(
        "Write review-only SPL to find powershell.exe launched by winword.exe or "
        "excel.exe, grouped by host and user, returning parent process, child process, "
        "command line and first/last seen. Do not execute."
    )
    process_spl = compile_intent_spec_to_spl(process)
    assert "powershell.exe" in process_spl.lower()
    assert "command_line" in process_spl
    assert "parent_process" in process_spl


def test_comparison_compile_fails_closed() -> None:
    spec = build_spl_intent_spec("is this the same campaign as last month")
    assert compile_intent_spec_to_spl(spec) == ""


def test_legacy_plan_compile_unchanged_without_spec() -> None:
    plan = {
        "detection_family": "ot_modbus_unauthorized_write",
        "data_domain": "ot_network",
        "time_window_hours": 24,
        "filters": [{"field": "protocol", "match": "modbus"}],
        "group_by": ["src_ip", "dest_ip"],
        "metric": "count",
    }
    spl = compile_plan_to_spl(plan)
    assert spl.rstrip().endswith("head 100")
    assert "| stats count as event_count" in spl


def test_postprocessor_does_not_overwrite_explicit_horizon() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    spl = "search index=<your_index> earliest=-24h latest=now | timechart span=1h count"
    out = normalize_review_only_spl(
        spl,
        {
            "is_explicit_spl_authoring": True,
            "is_universal_spl": False,
            "semantic_analyst_intent": spec,
        },
    )
    assert "earliest=-24h" in out.normalized_spl
    assert "earliest=-24h" in (out.trace.get("final_earliest") or "earliest=-24h")


def test_postprocessor_keeps_streamstats_order() -> None:
    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype>\n"
        "| sort 0 _time\n"
        "| streamstats time_window=10m dc(user_norm) as distinct_count by src_ip_norm"
    )
    out = normalize_review_only_spl(
        spl,
        {
            "is_explicit_spl_authoring": True,
            "is_universal_spl": False,
            "semantic_analyst_intent": spec,
        },
    )
    assert "streamstats time_window=10m" in out.normalized_spl
    assert "sort 0 _time" in out.normalized_spl


def test_normalization_alias_is_consumed() -> None:
    spec = build_spl_intent_spec(
        "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
    )
    spl = compile_intent_spec_to_spl(spec)
    assert "user_norm=" in spl
    assert "dc(user_norm)" in spl


def test_search_vs_eval_literal_quoting_is_generic() -> None:
    assert render_field_eq("action", "failure", context="search") == "action=failure"
    assert render_field_eq("action", "failure", context="eval") == 'action="failure"'
    assert render_field_eq("action", "denied", context="eval") == 'action="denied"'
    assert render_field_eq("action", "allowed", context="eval") == 'action="allowed"'
    assert render_field_eq("EventCode", "4625", context="search") == "EventCode=4625"
    assert render_field_eq("EventCode", "4625", context="eval") == "EventCode=4625"

    search = event_set_fragment("failed_login", context="search")
    eval_pred = event_set_fragment("failed_login", context="eval")
    assert "action=failure" in search
    assert 'action="failure"' in eval_pred
    assert "EventCode=4625" in search
    assert "EventCode=4625" in eval_pred
    assert 'EventCode="4625"' not in eval_pred

    denied = event_set_fragment("denied_traffic", context="eval")
    assert 'action="denied"' in denied
    assert 'action="blocked"' in denied
    assert "action=denied OR" not in denied


def test_sequence_case_quotes_strings_search_stays_unquoted() -> None:
    spec = build_spl_intent_spec(
        "password change followed by successful login within 5 minutes"
    )
    spl = compile_intent_spec_to_spl(spec)
    base = spl.split("|", 1)[0]
    assert "action=success" in base or "action=password_change" in base
    assert 'action="success"' not in base
    assert "EventCode=4624" in spl
    assert 'EventCode="4624"' not in spl
    case_m = re.search(r"eval event_type=case\((.*)\)", spl)
    assert case_m, spl
    case_expr = case_m.group(1)
    assert 'action="success"' in case_expr or 'action="password_change"' in case_expr
    assert re.search(r'\baction=(?:success|password_change)\b', case_expr) is None
    assert "EventCode=4723" in case_expr
    assert 'EventCode="4723"' not in case_expr
    issues = _eval_where_unquoted_string_literals(spl)
    assert issues == [], issues


_EVAL_CALL_NAMES = frozenset(
    {
        "lower",
        "coalesce",
        "case",
        "if",
        "strftime",
        "like",
        "isnull",
        "isnotnull",
        "mvfind",
        "relative_time",
        "now",
        "null",
        "true",
        "tonumber",
        "tostring",
        "replace",
        "match",
        "typeof",
        "round",
        "len",
        "substr",
        "split",
        "mvjoin",
        "cidrmatch",
        "count",
        "max",
        "min",
        "latest",
        "earliest",
        "values",
        "dc",
    }
)
_UNQUOTED_EQ_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\b"
)


def _eval_where_unquoted_string_literals(spl: str) -> list[str]:
    """Flag eval/where ``field=bareword`` string comparisons that must be quoted."""
    issues: list[str] = []
    for raw in spl.split("|")[1:]:
        body = raw.strip()
        cmd = body.split(None, 1)[0].lower() if body else ""
        if cmd not in {"eval", "where"}:
            continue
        for match in _UNQUOTED_EQ_RE.finditer(body):
            rhs = match.group(2)
            rest = body[match.end() :].lstrip()
            if rest.startswith("("):
                continue
            if rhs.lower() in _EVAL_CALL_NAMES:
                continue
            issues.append(f"{cmd}:{match.group(0)}")
    return issues
