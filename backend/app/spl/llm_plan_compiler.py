"""Plan-plus-compiler path for the LLM SPL producer (spike).

Thesis (validated in the lab probe): a small instruct model is unreliable when it
must simultaneously write SPL, satisfy a large schema, remember SOC-STD ordering
rules, and emit governance metadata — it trips ordering rules (strftime before
stats) and drops fields. So we split the work:

  LLM  -> a small SEMANTIC DETECTION PLAN (domain, filters, entities, metric)
  code -> deterministically COMPILES the plan into SOC-STD-compliant SPL
          (placeholders, time bound, coalesce-normalized stats, strftime AFTER
          stats, sort, head 100)

The compiled SPL is then fed through the EXISTING governed producer
(`generate_llm_spl_fallback` via its raw-output hook), so validation, SOC-STD
quality lint, the role adapter, lab-tier gating, and execution_eligible=false all
run unchanged. SOC-STD is never weakened; execution stays disabled.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Callable

from app.config import settings
from app.llm.adapter.output_preprocessor import preprocess_llm_output
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.spl.llm_fallback import (
    CLARIFICATION_INVALID_SCHEMA,
    CLARIFICATION_NO_CLIENT,
    LlmSplFallbackResult,
    _clarification,
    _spl_max_output_tokens,
    generate_llm_spl_fallback,
)

# Default seed for repeatable SPL generation (temperature=0 is not enough on
# llama.cpp without a seed).
SPL_PLAN_SEED = 1729

# Compact plan schema — small enough that an 8B fills it reliably.
PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "detection_family": {"type": "string"},
        "data_domain": {
            "type": "string",
            "enum": ["auth", "network", "dns", "endpoint", "firewall", "ot_protocol", "ot_network"],
        },
        "time_window_hours": {"type": "integer"},
        "filters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"field": {"type": "string"}, "match": {"type": "string"}},
                "required": ["field", "match"],
            },
        },
        "group_by": {"type": "array", "items": {"type": "string"}},
        "metric": {"type": "string", "enum": ["count", "distinct_count"]},
        "metric_field": {"type": "string"},
        "index": {"type": "string"},
        "sourcetype": {"type": "string"},
        "earliest": {"type": "string"},
        "latest": {"type": "string"},
        "result_cap": {"type": "integer"},
        "unresolved_slots": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "required_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["detection_family", "data_domain", "group_by", "metric"],
}

_DOMAIN_PLACEHOLDERS: dict[str, tuple[str, str]] = {
    "auth": ("<auth_index>", "<auth_sourcetype>"),
    "network": ("<network_index>", "<network_sourcetype>"),
    "dns": ("<dns_index>", "<dns_sourcetype>"),
    "endpoint": ("<endpoint_index>", "<endpoint_sourcetype>"),
    "firewall": ("<firewall_index>", "<firewall_sourcetype>"),
    "ot_protocol": ("<ot_index>", "<ot_sourcetype>"),
    "ot_network": ("<ot_network_index>", "<ot_network_sourcetype>"),
}

_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_field(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if _FIELD_RE.match(text) else None


def _safe_value(value: Any) -> str:
    # Strip anything that could break out of a quoted SPL term or inject a command.
    text = str(value or "").strip()
    text = re.sub(r'[|"\\\n\r]', "", text)
    return text[:80]


#: Match values that are not predicates. A planner reaching for "select everything"
#: writes one of these; compiled literally they become a filter that matches only
#: the literal string ('src_ip="*"'), silently narrowing the search to nothing.
#: The prompt already forbids them, but the compiler must not depend on that.
_NON_PREDICATE_MATCHES: frozenset[str] = frozenset(
    {"*", "%", "any", "all", "null", "not null", "is not null", "notnull", "distinct", "none", "-"}
)


def _is_predicate_match(value: str) -> bool:
    return bool(value) and value.strip().lower() not in _NON_PREDICATE_MATCHES


# Event-class atoms: (field, value). Value kind is inferred (numeric vs string).
# SEARCH context may emit unquoted Splunk tokens (`action=failure`).
# EVAL / WHERE / CASE context must quote string literals (`action="failure"`)
# and must leave numeric EventCode comparisons unquoted. No field/value
# hardcodes — denied/allowed/password_change follow the same rule.
_EVENT_SET_ATOMS: dict[str, tuple[tuple[str, str], ...]] = {
    "failed_login": (("action", "failure"), ("action", "failed"), ("EventCode", "4625")),
    "successful_login": (("action", "success"), ("EventCode", "4624")),
    "password_change": (("EventCode", "4723"), ("EventCode", "4724"), ("action", "password_change")),
    "account_lockout": (("EventCode", "4740"),),
    "privilege_change": (("EventCode", "4728"), ("EventCode", "4732"), ("EventCode", "4756")),
    "denied_traffic": (("action", "denied"), ("action", "blocked"), ("action", "drop")),
}

_NUMERIC_LITERAL_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _is_numeric_literal(value: str) -> bool:
    return bool(_NUMERIC_LITERAL_RE.fullmatch(str(value or "").strip()))


def render_field_eq(field: str, value: str, *, context: str) -> str:
    """Render ``field=value`` for search vs eval/where/case expression context."""
    safe_field = _safe_field(field) or ""
    raw = str(value or "").strip()
    if not safe_field or not raw:
        return ""
    if _is_numeric_literal(raw):
        return f"{safe_field}={raw}"
    if context == "search":
        return f"{safe_field}={_safe_value(raw)}"
    quoted = _safe_value(raw).replace('"', '\\"')
    return f'{safe_field}="{quoted}"'


def event_set_fragment(name: str, *, context: str) -> str:
    atoms = _EVENT_SET_ATOMS.get(str(name))
    if not atoms:
        return ""
    parts = [render_field_eq(field, value, context=context) for field, value in atoms]
    parts = [part for part in parts if part]
    if not parts:
        return ""
    return "(" + " OR ".join(parts) + ")"


# Search-context fragments. Prefer ``event_set_fragment(..., context=...)``.
_EVENT_SET_FILTERS: dict[str, str] = {
    name: event_set_fragment(name, context="search") for name in _EVENT_SET_ATOMS
}


def _governed_default_time_clause() -> str:
    """Retrieval envelope when the semantic contract has no user/RQC horizon.

    Origin: ``settings.spl_default_earliest`` / ``spl_default_latest``
    (``SPL_DEFAULT_EARLIEST``, SPL validation policy). Not a compiler-local 24h.
    """
    earliest = str(settings.spl_default_earliest or "-24h").strip() or "-24h"
    latest = str(settings.spl_default_latest or "now").strip() or "now"
    if not earliest.lower().startswith("earliest="):
        earliest = f"earliest={earliest}"
    if not latest.lower().startswith("latest="):
        latest = f"latest={latest}"
    return f"{earliest} {latest}"


def compile_intent_spec_to_spl(spec: dict[str, Any]) -> str:
    """Compile the immutable semantic contract without a second planner."""
    if not isinstance(spec, dict) or spec.get("support_status") == "unsupported":
        return ""
    domain = str(spec.get("event_domain") or "auth")
    if domain == "authentication":
        domain = "auth"
    if domain == "firewall":
        domain = "firewall"
    metric = "distinct_count" if spec.get("distinct_by") else "count"
    metric_field = None
    distinct = spec.get("distinct_by") or []
    if distinct:
        metric_field = str(distinct[0])
    plan = {
        "detection_family": str(spec.get("analysis_shape") or "aggregation"),
        "data_domain": domain,
        "group_by": list(spec.get("group_by") or []),
        "metric": metric,
        "metric_field": metric_field,
        "filters": [],
    }
    return compile_plan_to_spl(plan, intent_spec=spec)


def compile_plan_to_spl(plan: dict[str, Any], *, intent_spec: dict[str, Any] | None = None) -> str:
    """Deterministically assemble SOC-STD-compliant SPL from a detection plan.

    When ``intent_spec`` is absent, the historical lab shape is preserved
    (placeholders, stats, strftime after stats, sort, head 100). When the
    semantic contract is present it is authority: analysis shape, search
    horizon, rolling/sequence windows, and prohibitions override plan defaults.

    OPTIONAL_PHASE_S Layer 1a: selective filters stay in the base search (already);
    project kept fields before aggregation when the plan proves unused columns are
    safe to drop; keep non-streaming stages late; preserve Q11 ``sort 0 + _time``
    before streamstats exactly.
    """
    spec = intent_spec if isinstance(intent_spec, dict) else {}
    if spec.get("support_status") == "unsupported":
        return ""

    domain = str(plan.get("data_domain") or spec.get("event_domain") or "")
    if domain == "authentication":
        domain = "auth"
    index_ph, sourcetype_ph = _DOMAIN_PLACEHOLDERS.get(domain, ("<index>", "<sourcetype>"))
    source = spec.get("source_constraints") if isinstance(spec.get("source_constraints"), dict) else {}
    index_value = str(source.get("index") or "").strip() or index_ph
    sourcetype_value = str(source.get("sourcetype") or "").strip() or sourcetype_ph

    search_horizon = str(spec.get("search_horizon") or spec.get("time_window") or "").strip()
    prohibitions = {str(item) for item in (spec.get("prohibitions") or [])}
    if search_horizon and "earliest=" in search_horizon.lower():
        time_clause_search = search_horizon
    elif spec:
        # Semantic contract present: never invent a compiler-local 24h.
        # User/RQC horizon already handled above. Empty horizon uses the
        # governed SPL policy default, unless overwrite of that default is banned.
        if "implicit_default_24h_overwrite" in prohibitions:
            time_clause_search = ""
        else:
            time_clause_search = _governed_default_time_clause()
    else:
        try:
            hours = int(plan.get("time_window_hours") or 24)
        except (TypeError, ValueError):
            hours = 24
        hours = max(1, min(hours, 168))
        time_clause_search = f"earliest=-{hours}h latest=now"

    # Layer 1a: selective filters into base search before the first pipe.
    search_terms = [f"search index={index_value} sourcetype={sourcetype_value}"]
    if time_clause_search:
        search_terms.append(time_clause_search)
    for item in plan.get("filters") or []:
        if not isinstance(item, dict):
            continue
        field = _safe_field(item.get("field"))
        match = _safe_value(item.get("match"))
        if field and _is_predicate_match(match):
            search_terms.append(f'{field}="{match}"')
    event_fragments: list[str] = []
    for event_name in spec.get("required_event_sets") or []:
        fragment = event_set_fragment(str(event_name), context="search")
        if fragment:
            event_fragments.append(fragment)
    if len(event_fragments) >= 2:
        # Splunk juxtaposition is AND. Mutually exclusive event types (failure vs
        # success, password-change vs login) must be retrieved as a union or the
        # base search matches nothing.
        inners: list[str] = []
        for fragment in event_fragments:
            inner = fragment.strip()
            if inner.startswith("(") and inner.endswith(")"):
                inner = inner[1:-1].strip()
            inners.append(inner)
        search_terms.append("(" + " OR ".join(inners) + ")")
    elif event_fragments:
        search_terms.append(event_fragments[0])
    process = spec.get("process_constraints") if isinstance(spec.get("process_constraints"), dict) else {}
    child_names = [str(item) for item in (process.get("child") or []) if str(item).strip()]
    parent_names = [str(item) for item in (process.get("parent") or []) if str(item).strip()]
    if child_names:
        child_terms: list[str] = []
        for name in child_names:
            safe = _safe_value(name)
            if safe:
                child_terms.append(f'like(Image, "%{safe}")')
                child_terms.append(f'like(New_Process_Name, "%{safe}")')
        if child_terms:
            search_terms.append("(" + " OR ".join(child_terms) + ")")
    if parent_names:
        parent_terms: list[str] = []
        for name in parent_names:
            safe = _safe_value(name)
            if safe:
                parent_terms.append(f'like(ParentImage, "%{safe}")')
                parent_terms.append(f'like(Parent_Process_Name, "%{safe}")')
        if parent_terms:
            search_terms.append("(" + " OR ".join(parent_terms) + ")")
    search_line = " ".join(search_terms)

    analysis_shape = str(spec.get("analysis_shape") or "")
    roles = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
    group_by = [g for g in (_safe_field(x) for x in (spec.get("group_by") or plan.get("group_by") or [])) if g]
    if not group_by and not analysis_shape:
        group_by = ["src_ip"]

    norm_reqs = spec.get("normalization_requirements") if isinstance(spec.get("normalization_requirements"), list) else []
    alias_by_field: dict[str, str] = {}
    eval_parts: list[str] = []
    if norm_reqs:
        for item in norm_reqs:
            if not isinstance(item, dict):
                continue
            alias = _safe_field(item.get("alias"))
            expr = str(item.get("expression") or "").strip()
            if alias and expr:
                eval_parts.append(f"{alias}={expr}")
                sources = item.get("source_fields") if isinstance(item.get("source_fields"), list) else []
                for src in sources:
                    alias_by_field[str(src)] = alias
    else:
        for group in group_by:
            eval_parts.append(f'{group}_norm=lower(coalesce({group}, "unknown"))')
            alias_by_field[group] = f"{group}_norm"

    def _alias(field_name: str) -> str:
        return alias_by_field.get(field_name, field_name)

    def _early_projection(keep: list[str]) -> str:
        """Emit ``| fields …`` before aggregation when unused columns are proven droppable."""
        ordered: list[str] = []
        seen: set[str] = set()
        for name in keep:
            token = name if name == "_time" else (_safe_field(name) or "")
            if not token or token in seen:
                continue
            seen.add(token)
            ordered.append(token)
        if len(ordered) < 2:
            return ""
        return "| fields " + ", ".join(ordered)

    eval_clause = f"| eval {', '.join(eval_parts)}" if eval_parts else ""

    if child_names or parent_names:
        return _compile_process_parent_child(
            spec=spec,
            search_line=search_line,
            eval_parts=eval_parts,
            alias_by_field=dict(alias_by_field),
            group_by=group_by,
            _alias=_alias,
        )

    if analysis_shape == "raw":
        fields = spec.get("field_requirements") or ["_time", "src_ip", "user", "action"]
        safe_fields = [f for f in (_safe_field(x) or str(x) for x in fields) if f][:8]
        parts = [search_line]
        if eval_clause:
            parts.append(eval_clause)
        parts.append("| table " + " ".join(["_time", *safe_fields]))
        limit = spec.get("result_limit")
        if limit is not None:
            parts.append(f"| head {int(limit)}")
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    if analysis_shape == "trend":
        grain = str(spec.get("temporal_grain") or "1h")
        parts = [search_line]
        if eval_clause:
            parts.append(eval_clause)
        by_fields = [_alias(g) for g in group_by[:2]]
        proj = _early_projection(["_time", *by_fields])
        if proj:
            parts.append(proj)
        by_clause = f" by {', '.join(by_fields)}" if by_fields else ""
        parts.append(f"| timechart span={grain} count as event_count{by_clause}")
        # `| sort 0 _time` keeps the buckets chronological AND satisfies the
        # validator's result-limit contract (_result_limit_value reads `sort 0`).
        # A `| head N` cannot be used here: the trend contract prohibits
        # arbitrary_head_100 / arbitrary_truncation / time_series_truncation.
        parts.append("| sort 0 _time")
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    if analysis_shape == "rolling":
        window = (spec.get("analytical_window") or {}) if isinstance(spec.get("analytical_window"), dict) else {}
        size = str(window.get("size") or "10m")
        subject = _alias((roles.get("subject") or group_by or ["src_ip"])[0])
        distinct = (spec.get("distinct_by") or ["user"])[0]
        distinct_alias = _alias(str(distinct))
        parts = [search_line]
        if eval_clause:
            parts.append(eval_clause)
        proj = _early_projection(["_time", subject, distinct_alias])
        if proj:
            parts.append(proj)
        # Q11 (draft_quality) requires the explicit `sort 0 + _time` form before
        # streamstats; `sort 0 _time` is the same ascending sort but fails the lint.
        parts.append("| sort 0 + _time")
        parts.append(
            f"| streamstats time_window={size} dc({distinct_alias}) as distinct_count by {subject}"
        )
        parts.append(f"| where distinct_count > 1")
        parts.append(f"| stats max(distinct_count) as distinct_count by {subject}")
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    if analysis_shape == "sequence":
        agg_window, follow_gap = _sequence_windows_from_spec(spec)
        ordered = [str(item) for item in (spec.get("ordered_sequence") or spec.get("required_event_sets") or [])]
        correlate = _alias((roles.get("correlate_by") or roles.get("subject") or group_by or ["user"])[0])
        case_arms: list[str] = []
        for name in ordered:
            fragment = event_set_fragment(name, context="eval")
            if not fragment:
                continue
            cond = fragment.strip()
            if cond.startswith("(") and cond.endswith(")"):
                cond = cond[1:-1].strip()
            case_arms.append(f'{cond}, "{name}"')
        event_eval = ""
        if case_arms:
            event_eval = "| eval event_type=case(" + ", ".join(case_arms) + ")"
        parts = [search_line]
        if eval_clause:
            parts.append(eval_clause)
        if event_eval:
            parts.append(event_eval)
        by_fields = _sequence_by_fields(
            spec=spec,
            correlate=correlate,
            group_by=group_by,
            alias_by_field=alias_by_field,
            _alias=_alias,
        )
        keep = ["_time", *by_fields]
        if event_eval:
            keep.append("event_type")
        outputs = {str(item) for item in (spec.get("required_outputs") or [])}
        host_alias = alias_by_field.get("host") or (_alias("host") if "host" in outputs else "")
        if host_alias and host_alias not in by_fields:
            keep.append(host_alias)
        proj = _early_projection(keep)
        if proj:
            parts.append(proj)
        parts.append("| sort 0 + _time")  # Q11: explicit ascending sort before streamstats
        threshold_n = _explicit_threshold_int(spec)
        streamstats_by = ", ".join(by_fields) if by_fields else correlate
        if threshold_n is not None and len(ordered) >= 2:
            first_event = ordered[0]
            second_event = ordered[1]
            op = _threshold_compare_op(spec)
            parts.append(
                f"| streamstats time_window={agg_window} "
                f'count(eval(event_type="{first_event}")) as failure_count '
                f'min(eval(if(event_type="{first_event}", _time, null()))) as first_failure_epoch '
                f'latest(eval(if(event_type="{first_event}", _time, null()))) as last_failure_epoch '
                f"by {streamstats_by}"
            )
            where = (
                f'| where event_type="{second_event}" AND failure_count{op}{threshold_n}'
            )
            if follow_gap and follow_gap != agg_window:
                where += f" AND (_time-last_failure_epoch)<={_gap_seconds(follow_gap)}"
            parts.append(where)
        elif len(ordered) >= 2:
            parts.append(
                f"| streamstats window=1 current=f last(event_type) as prev_event last(_time) as prev_time by {streamstats_by}"
            )
            parts.append(
                f'| where prev_event="{ordered[0]}" AND event_type="{ordered[1]}" '
                f"AND (_time-prev_time)<={_gap_seconds(follow_gap)}"
            )
        else:
            parts.append(f"| transaction {streamstats_by} maxspan={agg_window}")
        extra_aggs: list[str] = []
        if threshold_n is not None or "failure_count" in outputs:
            extra_aggs.append("max(failure_count) as failure_count")
        if "first_failure_time" in outputs and threshold_n is not None:
            extra_aggs.append("min(first_failure_epoch) as first_failure_keep")
        if "success_time" in outputs:
            extra_aggs.append("latest(_time) as success_time_epoch")
        if host_alias and host_alias not in by_fields:
            extra_aggs.append(f"latest({host_alias}) as {host_alias}")
        extra = (" " + " ".join(extra_aggs)) if extra_aggs else ""
        parts.append(
            f"| stats count as sequence_matches{extra} earliest(_time) as first_match_epoch "
            f"latest(_time) as last_match_epoch by {', '.join(by_fields)}"
        )
        time_eval = (
            '| eval first_match=strftime(first_match_epoch, "%Y-%m-%d %H:%M:%S"), '
            'last_match=strftime(last_match_epoch, "%Y-%m-%d %H:%M:%S")'
        )
        drop = ["first_match_epoch", "last_match_epoch"]
        if "first_failure_time" in outputs:
            time_eval += ', first_failure=strftime(first_failure_keep, "%Y-%m-%d %H:%M:%S")'
            drop.append("first_failure_keep")
        if "success_time" in outputs:
            time_eval += ', success_time=strftime(success_time_epoch, "%Y-%m-%d %H:%M:%S")'
            drop.append("success_time_epoch")
        parts.append(time_eval + " | fields - " + " ".join(drop))
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    if analysis_shape == "first_seen":
        return _compile_first_seen(
            spec=spec,
            search_line=search_line,
            eval_parts=eval_parts,
            alias_by_field=alias_by_field,
            roles=roles,
            group_by=group_by,
            _alias=_alias,
        )

    metric = str(plan.get("metric") or "count")
    metric_field = _safe_field(plan.get("metric_field") or (spec.get("distinct_by") or [None])[0])
    if (metric == "distinct_count" or spec.get("distinct_by")) and metric_field:
        agg = f"dc({_alias(metric_field)}) as distinct_count"
        sort_field = "distinct_count"
    else:
        agg = "count as event_count"
        sort_field = "event_count"

    norm_fields = [_alias(g) for g in group_by] or (["src_ip_norm"] if not spec else group_by)
    if not norm_fields:
        norm_fields = ["src_ip"]
    stats_clause = (
        f"| stats {agg} earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch "
        f"by {', '.join(norm_fields)}"
    )
    time_format = (
        '| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S"), '
        'last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S") '
        "| fields - first_seen_epoch last_seen_epoch"
    )
    parts = [search_line]
    if eval_clause:
        parts.append(eval_clause)
    keep_for_stats = ["_time", *norm_fields]
    if metric_field:
        keep_for_stats.append(_alias(metric_field))
    proj = _early_projection(keep_for_stats)
    if proj:
        parts.append(proj)
    parts.extend([stats_clause, time_format])
    if analysis_shape == "ranking" or spec.get("ranking") or not spec:
        parts.append(f"| sort - {sort_field}")
        limit = spec.get("result_limit")
        if limit is not None:
            parts.append(f"| head {int(limit)}")
        elif "arbitrary_head_100" not in prohibitions:
            parts.append("| head 100")
    elif spec.get("result_limit") is not None:
        parts.append(f"| head {int(spec['result_limit'])}")
    spl = " ".join(parts)
    return re.sub(r"\s+", " ", spl).strip()


def _compile_first_seen(
    *,
    spec: dict[str, Any],
    search_line: str,
    eval_parts: list[str],
    alias_by_field: dict[str, str],
    roles: dict[str, Any],
    group_by: list[str],
    _alias: Callable[[str], str],
) -> str:
    """Compile observation-vs-baseline first-seen SPL without sample-query literals."""
    observation = str(spec.get("observation_window") or "").strip()
    subject_raw = str((roles.get("subject") or group_by or ["user"])[0])
    object_raw = str((roles.get("target") or roles.get("distinct_by") or ["host"])[0])
    subject = _alias(subject_raw)
    obj = _alias(object_raw)
    grain = str(spec.get("temporal_grain") or "").strip()
    extras = list(eval_parts)
    required_outputs = [str(item) for item in (spec.get("required_outputs") or [])]
    if "src_ip" in required_outputs and "src_ip" not in alias_by_field:
        extras.append(
            'src_ip_norm=coalesce(src_ip, src, source, source_ip, Source_Network_Address, "unknown")'
        )
        alias_by_field["src_ip"] = "src_ip_norm"
    extra_clause = f"| eval {', '.join(extras)}" if extras else ""
    parts = [search_line]
    if extra_clause:
        parts.append(extra_clause)
    actor_clauses: list[str] = []
    for pattern in spec.get("actor_patterns") or []:
        token = str(pattern).strip()
        if not token:
            continue
        if token.endswith("*"):
            prefix = _safe_value(token[:-1])
            if prefix:
                actor_clauses.append(f'like({subject}, "{prefix}%")')
        else:
            safe = _safe_value(token)
            if safe:
                actor_clauses.append(f'{subject}="{safe}"')
    if actor_clauses:
        parts.append("| where " + " OR ".join(actor_clauses))
    obs = observation or "24h"
    parts.append(
        f'| eval period=if(_time>=relative_time(now(), "-{obs}"), "observation", "baseline")'
    )
    parts.append(f'| eval baseline_object=if(period="baseline", {obj}, null())')
    parts.append("| sort 0 + _time")
    parts.append(f"| streamstats values(baseline_object) as baseline_objects by {subject}")
    parts.append('| where period="observation"')
    parts.append(
        f'| eval new_object=if(isnull(mvfind(baseline_objects, {obj})), {obj}, null())'
    )
    parts.append("| where isnotnull(new_object)")
    stats_bits = [
        f"dc({obj}) as distinct_new_host_count",
        f"values({obj}) as new_host",
    ]
    if "src_ip" in required_outputs:
        stats_bits.append(f"values({alias_by_field.get('src_ip', 'src_ip')}) as src_ip")
    if "connection_count" in required_outputs:
        stats_bits.append("count as connection_count")
    if "first_seen" in required_outputs or not grain:
        stats_bits.append("earliest(_time) as first_seen_epoch")
    if grain:
        parts.append(f"| bin _time span={grain}")
        by_clause = f"{subject}, _time"
    else:
        by_clause = f"{subject}, {obj}"
    parts.append(f"| stats {' '.join(stats_bits)} by {by_clause}")
    if any("first_seen_epoch" in item for item in stats_bits):
        parts.append(
            '| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S") '
            "| fields - first_seen_epoch"
        )
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _explicit_threshold_int(spec: dict[str, Any]) -> int | None:
    if not spec.get("explicit_threshold_present"):
        return None
    raw = spec.get("explicit_threshold_value")
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _threshold_compare_op(spec: dict[str, Any]) -> str:
    comparison = str(spec.get("explicit_threshold_comparison") or "greater_than").strip().lower()
    if comparison in {"at_least", "greater_than_or_equal", "gte", ">="}:
        return ">="
    if comparison in {"less_than", "lt", "<"}:
        return "<"
    if comparison in {"less_than_or_equal", "lte", "<="}:
        return "<="
    return ">"


def _sequence_by_fields(
    *,
    spec: dict[str, Any],
    correlate: str,
    group_by: list[str],
    alias_by_field: dict[str, str],
    _alias: Callable[[str], str],
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        token = str(name or "").strip()
        if token and token not in seen:
            seen.add(token)
            ordered.append(token)

    _add(correlate)
    roles_map = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
    for name in roles_map.get("correlate_by") or []:
        _add(_alias(str(name)))
    return ordered or [correlate]


def _compile_process_parent_child(
    *,
    spec: dict[str, Any],
    search_line: str,
    eval_parts: list[str],
    alias_by_field: dict[str, str],
    group_by: list[str],
    _alias: Callable[[str], str],
) -> str:
    extras = list(eval_parts)
    outputs = {str(item) for item in (spec.get("required_outputs") or [])}
    if "host" in outputs or "host" in group_by:
        if "host_norm" not in alias_by_field.values():
            extras.append(
                'host_norm=lower(coalesce(dest_host, dest, dvc, host, ComputerName, "unknown"))'
            )
            alias_by_field["host"] = "host_norm"
    extras.append('parent_process=coalesce(ParentImage, Parent_Process_Name, "unknown")')
    extras.append('child_process=coalesce(Image, New_Process_Name, process, "unknown")')
    extras.append('command_line=coalesce(CommandLine, process, "unknown")')
    names = list(group_by) if group_by else ["host", "user"]
    if "host" in outputs and "host" not in names:
        names.append("host")
    if "user" in outputs and "user" not in names:
        names.append("user")
    by_fields: list[str] = []
    seen: set[str] = set()
    for group in names:
        aliased = alias_by_field.get(group) or _alias(group)
        if aliased and aliased not in seen:
            seen.add(aliased)
            by_fields.append(aliased)
    for alias in alias_by_field.values():
        token = str(alias)
        if token and token not in seen:
            seen.add(token)
            by_fields.append(token)
    if not by_fields:
        by_fields = ["host_norm", "user_norm"]
    stats_bits = [
        "count as event_count",
        "earliest(_time) as first_seen_epoch",
        "latest(_time) as last_seen_epoch",
        "values(parent_process) as parent_process",
        "values(child_process) as child_process",
        "values(command_line) as command_line",
    ]
    parts = [search_line, f"| eval {', '.join(extras)}"]
    parts.append(f"| stats {' '.join(stats_bits)} by {', '.join(by_fields)}")
    parts.append(
        '| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S"), '
        'last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S") '
        "| fields - first_seen_epoch last_seen_epoch"
    )
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _gap_seconds(token: str) -> int:
    match = re.fullmatch(r"(\d+)([smhd])", str(token or "").strip().lower())
    if not match:
        return 300
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _sequence_windows_from_spec(spec: dict[str, Any]) -> tuple[str, str]:
    follow = str(spec.get("sequence_max_gap") or "5m").strip() or "5m"
    window = spec.get("analytical_window") if isinstance(spec.get("analytical_window"), dict) else {}
    aggregation = str(window.get("size") or "").strip() if window.get("kind") == "sequence" else ""
    if not aggregation:
        aggregation = follow
    return aggregation, follow


def _plan_system_prompt() -> str:
    return (
        "You are an OT/SOC detection PLANNER. Given an investigation request, return a small JSON "
        "detection plan — NOT SPL. Deterministic code compiles your plan into a validated, review-only "
        "query, so do not write any SPL or pipes.\n"
        "Return only valid JSON. No markdown, no explanation outside JSON, no hidden reasoning, no "
        "scratchpad, no planning text, and no <think> tags.\n"
        "Describe: data_domain (one of auth, network, dns, endpoint, firewall, ot_protocol, ot_network); "
        "filters as field+match pairs using generic field names (src_ip, dest_ip, user, host, protocol, "
        "function_code, query, action, bytes_out); group_by entities; metric (count or distinct_count, "
        "with metric_field for distinct_count); source fields index and sourcetype; time fields earliest/latest "
        "or time_window_hours; result_cap; unresolved_slots; a short detection_family; assumptions and required_fields. "
        "Pick the data_domain that matches the question. Keep filters minimal and on-question."
    )


def _grounding_block(
    *,
    slot_handoff: Any,
    mcp_discovery_context: Any,
    llm_intent_advisory: Any,
) -> str:
    """Render redacted planning context (slots, discovery, 2C advisory) for the prompt.

    Phase 4A — closes the input-preservation gap: previously only the raw query
    reached the planner. All values are bounded and advisory; the compiler still
    forces placeholders/governance.
    """
    lines: list[str] = []

    def _slots(obj: Any) -> dict[str, Any]:
        if obj is None:
            return {}
        if hasattr(obj, "normalized_slots"):
            return dict(getattr(obj, "normalized_slots", {}) or {})
        if isinstance(obj, dict):
            inner = obj.get("normalized_slots")
            return dict(inner) if isinstance(inner, dict) else dict(obj)
        return {}

    slots = _slots(slot_handoff)
    if slots:
        rendered = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(slots.items())[:12] if v)
        if rendered:
            lines.append(f"Resolved slots (advisory): {rendered}")

    discovery = mcp_discovery_context if isinstance(mcp_discovery_context, dict) else (
        mcp_discovery_context.model_dump() if hasattr(mcp_discovery_context, "model_dump") else {}
    )
    if isinstance(discovery, dict):
        idx = [str(x) for x in (discovery.get("indexes") or [])][:5]
        st = [str(x) for x in (discovery.get("sourcetypes") or [])][:5]
        if idx:
            lines.append(f"Discovered indexes (advisory): {', '.join(idx)}")
        if st:
            lines.append(f"Discovered sourcetypes (advisory): {', '.join(st)}")

    advisory = llm_intent_advisory if isinstance(llm_intent_advisory, dict) else {}
    candidate = advisory.get("entity_slots_candidate") if isinstance(advisory, dict) else None
    if isinstance(candidate, dict) and candidate:
        rendered = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(candidate.items())[:8] if v)
        if rendered:
            lines.append(f"Intent slot candidates (advisory): {rendered}")

    return "\n".join(lines)


def _plan_user_prompt(user_query: str, grounding: str = "", shape_example: str = "") -> str:
    base = f"Investigation request:\n{user_query}"
    if grounding:
        base += f"\n\nPlanning context (advisory; do not invent beyond it):\n{grounding}"
    if shape_example:
        # One shape-keyed example, selected by the deterministic semantic
        # contract. It goes in the user prompt, not the system prompt, so the
        # cacheable stable prefix is identical across every request.
        base += f"\n\n{shape_example}"
    return base + "\n\nReturn only the detection plan JSON."


def get_detection_plan(
    user_query: str,
    *,
    client: LocalChatClient | None = None,
    seed: int = SPL_PLAN_SEED,
    llm_raw_output_provider: Callable[[], str] | None = None,
    grounding: str = "",
    analysis_shape: str = "",
) -> tuple[dict[str, Any] | None, list[str]]:
    """Ask the LLM for a small detection plan; parse it tolerantly. Returns (plan, errors).

    ``analysis_shape`` is the shape the deterministic semantic contract already
    resolved. It selects at most one governed few-shot, and only under the
    candidate eval arm; production renders no example and is unchanged.
    """
    if llm_raw_output_provider is not None:
        raw = llm_raw_output_provider()
    else:
        active_client = client or build_synthesis_client_from_settings()
        if active_client is None:
            return None, [CLARIFICATION_NO_CLIENT]
        try:
            from app.llm.policy.candidates import live_system_prompt, spl_shape_few_shot_block

            completion = active_client.generate(
                system_prompt=live_system_prompt("spl_advisory_generator", _plan_system_prompt()),
                user_prompt=_plan_user_prompt(
                    user_query, grounding, spl_shape_few_shot_block(analysis_shape)
                ),
                max_tokens=_spl_max_output_tokens(),
                temperature=0.0,
                seed=seed,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "detection_plan", "schema": PLAN_JSON_SCHEMA},
                },
            )
        except LocalChatError:
            return None, [CLARIFICATION_NO_CLIENT]
        if completion.finish_reason == "length":
            return None, ["llm_finish_reason=length"]
        raw = completion.text
    pre = preprocess_llm_output(raw or "", PLAN_JSON_SCHEMA, allow_retry=False)
    if pre.payload is None:
        return None, pre.validation_errors or [pre.verdict]
    return pre.payload, []


def _redacted_detection_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Snapshot of the LLM-chosen plan for downstream nodes (no raw query echo)."""
    domain = str(plan.get("data_domain") or "")
    index_ph, sourcetype_ph = _DOMAIN_PLACEHOLDERS.get(domain, ("<index>", "<sourcetype>"))
    filters = [
        f"{_safe_field(f.get('field'))}={_safe_value(f.get('match'))}"
        for f in (plan.get("filters") or [])
        if isinstance(f, dict)
        and _safe_field(f.get("field"))
        and _is_predicate_match(_safe_value(f.get("match")))
    ]
    return {
        "index": index_ph,
        "sourcetype": sourcetype_ph,
        "data_domain": domain or None,
        "required_fields": [str(x) for x in (plan.get("required_fields") or [])][:12],
        "filters": filters[:12],
        "threshold": plan.get("threshold") if isinstance(plan.get("threshold"), dict) else None,
        "detection_family": str(plan.get("detection_family") or "") or None,
    }


def generate_llm_spl_via_plan(
    *,
    user_query: str,
    slot_handoff: Any = None,
    mcp_discovery_context: Any = None,
    llm_intent_advisory: Any = None,
    client: LocalChatClient | None = None,
    seed: int = SPL_PLAN_SEED,
    plan_raw_output_provider: Callable[[], str] | None = None,
    resolved_query_contract: dict[str, Any] | None = None,
    intent_spec: dict[str, Any] | None = None,
) -> LlmSplFallbackResult | None:
    """Plan -> compile -> feed through the existing governed producer (gates unchanged).

    Phase 4A: ``slot_handoff`` / ``mcp_discovery_context`` / ``llm_intent_advisory``
    are threaded into the planner prompt so the LLM plans against resolved context
    instead of only the raw query. Phase 4B: the chosen plan is returned (redacted)
    on ``detection_plan`` so the workflow node can persist it for downstream nodes.
    """
    if not settings.ai_soc_llm_spl_fallback_enabled:
        return _clarification("llm_spl_fallback_disabled")
    if settings.ai_soc_llm_mode.strip().lower() == "disabled" or not settings.ai_soc_llm_enabled:
        return _clarification("llm_spl_fallback_disabled")

    grounding = _grounding_block(
        slot_handoff=slot_handoff,
        mcp_discovery_context=mcp_discovery_context,
        llm_intent_advisory=llm_intent_advisory,
    )
    # The semantic contract is resolved BEFORE the model call: it is deterministic
    # and depends only on the query, and its analysis_shape is what selects the
    # single governed few-shot. Nothing about the plan feeds back into it.
    spec = intent_spec if isinstance(intent_spec, dict) else None
    if spec is None:
        from app.spl.spl_intent_spec import build_spl_intent_spec
        from app.spl.source_profile_bindings import source_mappings_for_query

        spec = build_spl_intent_spec(
            user_query,
            resolved_query_contract=resolved_query_contract,
            source_mappings=source_mappings_for_query(user_query),
        )
    if spec.get("support_status") == "unsupported":
        return _clarification("spl_semantic_contract_unsupported")

    plan, errors = get_detection_plan(
        user_query,
        client=client,
        seed=seed,
        llm_raw_output_provider=plan_raw_output_provider,
        grounding=grounding,
        analysis_shape=str(spec.get("analysis_shape") or ""),
    )
    if plan is None:
        return _clarification(CLARIFICATION_INVALID_SCHEMA, adapter_errors=errors)
    apply_spec = intent_spec is not None or spec.get("analysis_shape") in {"trend", "rolling", "sequence"}
    compiled_spl = compile_plan_to_spl(plan, intent_spec=spec if apply_spec else None)
    if not compiled_spl:
        return _clarification("spl_semantic_contract_unsupported")
    redacted_plan = _redacted_detection_plan(plan)
    try:
        time_window_hours = int(plan.get("time_window_hours") or 24)
    except (TypeError, ValueError):
        time_window_hours = 24
    time_window_hours = max(1, min(time_window_hours, 168))
    # Hand the compiled SPL to the existing producer as if it were the raw model
    # output — all validation / SOC-STD quality / adapter / lab-tier gates run
    # unchanged. execution_eligible/governed/catalog_approved forced false.
    producer_payload = json.dumps(
        {
            "status": "candidate_generated",
            "confidence_score": 0.6,
            "confidence_label": "medium",
            "detection_family": str(plan.get("detection_family") or "ot_planned_hunt"),
            "candidate_spl": compiled_spl,
            "index": redacted_plan.get("index") or "",
            "sourcetype": redacted_plan.get("sourcetype") or "",
            "earliest": f"-{time_window_hours}h",
            "latest": "now",
            "time_window_hours": time_window_hours,
            "result_cap": 100,
            "unresolved_slots": [],
            "assumptions": [str(a) for a in (plan.get("assumptions") or [])]
            or ["Placeholder index/sourcetype require a source profile before review."],
            "required_fields": [str(f) for f in (plan.get("required_fields") or [])] or ["index", "sourcetype"],
            "missing_details": [],
            "clarifying_questions": [],
            "validation_notes": ["Compiled from an LLM detection plan; lab candidate only."],
            "soc_std_rules_applied": ["deterministic_compiler", "coalesce_normalization", "native_time_ordering"],
            "risk_notes": ["Not governed; SOC review required."],
            "execution_eligible": False,
            "governed": False,
            "catalog_approved": False,
        }
    )
    result = generate_llm_spl_fallback(
        user_query=user_query, llm_raw_output_provider=lambda: producer_payload
    )
    if result is not None:
        result = replace(result, detection_plan=_redacted_detection_plan(plan))
    return result
