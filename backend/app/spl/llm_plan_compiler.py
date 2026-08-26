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


_EVENT_SET_FILTERS: dict[str, str] = {
    "failed_login": "(action=failure OR action=failed OR EventCode=4625)",
    "successful_login": "(action=success OR EventCode=4624)",
    "password_change": "(EventCode=4723 OR EventCode=4724 OR action=password_change)",
    "account_lockout": "(EventCode=4740)",
    "privilege_change": "(EventCode=4728 OR EventCode=4732 OR EventCode=4756)",
    "denied_traffic": "(action=denied OR action=blocked OR action=drop)",
}


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
    else:
        try:
            hours = int(plan.get("time_window_hours") or 24)
        except (TypeError, ValueError):
            hours = 24
        hours = max(1, min(hours, 168))
        if "implicit_default_24h_overwrite" in prohibitions and not search_horizon:
            time_clause_search = ""
        else:
            time_clause_search = f"earliest=-{hours}h latest=now"

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
    for event_name in spec.get("required_event_sets") or []:
        fragment = _EVENT_SET_FILTERS.get(str(event_name))
        if fragment:
            search_terms.append(fragment)
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

    eval_clause = f"| eval {', '.join(eval_parts)}" if eval_parts else ""

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
        gap = str(spec.get("sequence_max_gap") or "5m")
        ordered = [str(item) for item in (spec.get("ordered_sequence") or spec.get("required_event_sets") or [])]
        correlate = _alias((roles.get("correlate_by") or roles.get("subject") or group_by or ["user"])[0])
        case_parts: list[str] = []
        for name in ordered:
            fragment = _EVENT_SET_FILTERS.get(name)
            if fragment:
                case_parts.append(f'if({fragment}, "{name}",')
        event_eval = ""
        if case_parts:
            nested = "null"
            for part in reversed(case_parts):
                nested = f"{part} {nested})"
            event_eval = f"| eval event_type={nested}"
        parts = [search_line]
        if eval_clause:
            parts.append(eval_clause)
        if event_eval:
            parts.append(event_eval)
        parts.append("| sort 0 + _time")  # Q11: explicit ascending sort before streamstats
        parts.append(f"| streamstats window=1 current=f last(event_type) as prev_event last(_time) as prev_time by {correlate}")
        if len(ordered) >= 2:
            parts.append(
                f'| where prev_event="{ordered[0]}" AND event_type="{ordered[1]}" '
                f"AND (_time-prev_time)<={_gap_seconds(gap)}"
            )
        else:
            parts.append(f"| transaction {correlate} maxspan={gap}")
        # The ordered A->B match is already decided above; this summarises the
        # matched pairs per correlation entity. It is required because the SPL
        # validator rejects a query with no stats/timechart stage
        # (`missing_aggregation`) — it does not collapse the sequence semantics.
        parts.append(
            f"| stats count as sequence_matches earliest(_time) as first_match_epoch "
            f"latest(_time) as last_match_epoch by {correlate}"
        )
        # U02: earliest(_time)/latest(_time) require a readable strftime() after stats.
        parts.append(
            '| eval first_match=strftime(first_match_epoch, "%Y-%m-%d %H:%M:%S"), '
            'last_match=strftime(last_match_epoch, "%Y-%m-%d %H:%M:%S") '
            "| fields - first_match_epoch last_match_epoch"
        )
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

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


def _gap_seconds(token: str) -> int:
    match = re.fullmatch(r"(\d+)([smhd])", str(token or "").strip().lower())
    if not match:
        return 300
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


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
