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
from typing import Any, Callable

from app.config import settings
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.spl.llm_fallback import (
    CLARIFICATION_INVALID_SCHEMA,
    CLARIFICATION_NO_CLIENT,
    LlmSplFallbackResult,
    _clarification,
    _spl_max_output_tokens,
    _strict_json_payload,
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


def compile_plan_to_spl(plan: dict[str, Any]) -> str:
    """Deterministically assemble SOC-STD-compliant SPL from a detection plan.

    Guarantees by construction: placeholder index/sourcetype, explicit time bound,
    a stats aggregation, strftime AFTER stats (never before), sort, head 100, and
    only allowlisted commands. This is what makes the output pass validation +
    quality where free-form 8B SPL did not.
    """
    domain = str(plan.get("data_domain") or "")
    index_ph, sourcetype_ph = _DOMAIN_PLACEHOLDERS.get(domain, ("<index>", "<sourcetype>"))

    try:
        hours = int(plan.get("time_window_hours") or 24)
    except (TypeError, ValueError):
        hours = 24
    hours = max(1, min(hours, 168))

    search_terms = [f"search index={index_ph} sourcetype={sourcetype_ph} earliest=-{hours}h latest=now"]
    for item in plan.get("filters") or []:
        if not isinstance(item, dict):
            continue
        field = _safe_field(item.get("field"))
        match = _safe_value(item.get("match"))
        if field and match:
            search_terms.append(f'{field}="{match}"')
    search_line = " ".join(search_terms)

    group_by = [g for g in (_safe_field(x) for x in (plan.get("group_by") or [])) if g] or ["src_ip"]
    norm_evals = [f'{g}_norm=lower(coalesce({g}, "unknown"))' for g in group_by]
    norm_fields = [f"{g}_norm" for g in group_by]
    eval_clause = "| eval " + ", ".join(norm_evals)

    metric = str(plan.get("metric") or "count")
    metric_field = _safe_field(plan.get("metric_field"))
    if metric == "distinct_count" and metric_field:
        agg = f"dc({metric_field}) as distinct_count"
        sort_field = "distinct_count"
    else:
        agg = "count as event_count"
        sort_field = "event_count"

    stats_clause = (
        f"| stats {agg} earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch "
        f"by {', '.join(norm_fields)}"
    )
    # strftime is applied AFTER stats (SOC-STD-SPL-001-U02) — the exact rule the
    # free-form model kept violating.
    time_clause = (
        '| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S"), '
        'last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S") '
        "| fields - first_seen_epoch last_seen_epoch"
    )
    tail = f"| sort - {sort_field} | head 100"

    spl = " ".join([search_line, eval_clause, stats_clause, time_clause, tail])
    return re.sub(r"\s+", " ", spl).strip()


def _plan_system_prompt() -> str:
    return (
        "You are an OT/SOC detection PLANNER. Given an investigation request, return a small JSON "
        "detection plan — NOT SPL. Deterministic code compiles your plan into a validated, review-only "
        "query, so do not write any SPL or pipes.\n"
        "Describe: data_domain (one of auth, network, dns, endpoint, firewall, ot_protocol, ot_network); "
        "filters as field+match pairs using generic field names (src_ip, dest_ip, user, host, protocol, "
        "function_code, query, action, bytes_out); group_by entities; metric (count or distinct_count, "
        "with metric_field for distinct_count); a short detection_family; assumptions and required_fields. "
        "Pick the data_domain that matches the question. Keep filters minimal and on-question."
    )


def _plan_user_prompt(user_query: str) -> str:
    return f"Investigation request:\n{user_query}\n\nReturn only the detection plan JSON."


def get_detection_plan(
    user_query: str,
    *,
    client: LocalChatClient | None = None,
    seed: int = SPL_PLAN_SEED,
    llm_raw_output_provider: Callable[[], str] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Ask the LLM for a small detection plan; parse it tolerantly. Returns (plan, errors)."""
    if llm_raw_output_provider is not None:
        raw = llm_raw_output_provider()
    else:
        active_client = client or build_synthesis_client_from_settings()
        if active_client is None:
            return None, [CLARIFICATION_NO_CLIENT]
        try:
            completion = active_client.generate(
                system_prompt=_plan_system_prompt(),
                user_prompt=_plan_user_prompt(user_query),
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
        raw = completion.text
    payload, errors = _strict_json_payload(raw or "")
    return payload, errors


def generate_llm_spl_via_plan(
    *,
    user_query: str,
    client: LocalChatClient | None = None,
    seed: int = SPL_PLAN_SEED,
    plan_raw_output_provider: Callable[[], str] | None = None,
) -> LlmSplFallbackResult | None:
    """Plan -> compile -> feed through the existing governed producer (gates unchanged)."""
    if not settings.ai_soc_llm_spl_fallback_enabled:
        return _clarification("llm_spl_fallback_disabled")
    if settings.ai_soc_llm_mode.strip().lower() == "disabled" or not settings.ai_soc_llm_enabled:
        return _clarification("llm_spl_fallback_disabled")

    plan, errors = get_detection_plan(
        user_query, client=client, seed=seed, llm_raw_output_provider=plan_raw_output_provider
    )
    if plan is None:
        return _clarification(CLARIFICATION_INVALID_SCHEMA, adapter_errors=errors)

    compiled_spl = compile_plan_to_spl(plan)
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
    return generate_llm_spl_fallback(
        user_query=user_query, llm_raw_output_provider=lambda: producer_payload
    )
