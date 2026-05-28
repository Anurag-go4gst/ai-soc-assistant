"""Stage 3K-Q1C LLM-assist sidecar for template matching (semantic hints only).

Instruct-only, shadow-gated, never authoritative. Deterministic matcher wins;
disagreements are recorded on ``TemplateMatchResult``.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import replace
from typing import Any, Callable

from app.config import settings
from app.llm.adapter import adapt_llm_output
from app.llm.registry_settings import REASONING_PROVIDER_ID, build_llm_governance_status
from app.safeguards.spl_validator import APPROVED_DATAMODELS, DATAMODEL_FIELD_ALLOWLIST
from app.spl.template_matcher import TemplateMatchResult, match_route_plan_to_template

TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE = "template_match_semantic_assist"
TEMPLATE_MATCH_ASSIST_TIMEOUT_SECONDS = 1.5

SPL_FRAGMENT_PATTERN = re.compile(
    r"\||\bsearch\b|\btstats\b|\bfrom\b.*\bdatamodel\b|\bstats\b|\bhead\b",
    re.IGNORECASE,
)

APPROVED_SOURCE_CLASS_HINTS = frozenset(
    {
        "okta_authentication_logs",
        "windows_security",
        "identity_authentication",
        "active_directory",
        "network_traffic",
        "firewall_logs",
        "dns_logs",
        "network_resolution",
    }
)


def match_route_plan_with_semantic_assist(
    normalized_route_plan: dict[str, Any],
    *,
    user_query: str = "",
    include_disabled: bool = True,
    shadow_enabled: bool | None = None,
    llm_raw_output_provider: Callable[[], str] | None = None,
) -> TemplateMatchResult:
    """Run deterministic matcher; optionally merge Instruct semantic hints (shadow)."""
    shadow_on = settings.routing_llm_shadow_enabled if shadow_enabled is None else shadow_enabled
    deterministic = match_route_plan_to_template(
        normalized_route_plan,
        include_disabled=include_disabled,
    )

    if not shadow_on:
        return deterministic

    assist_invoked = llm_raw_output_provider is not None
    role_status = _role_assist_status(assist_invoked=assist_invoked)

    if role_status.get("rejected_reason") == "reasoning_model_not_allowed_for_matching":
        return replace(
            deterministic,
            llm_assist_enabled=True,
            template_match_llm_hints={"rejected_reason": role_status["rejected_reason"]},
        )

    if not assist_invoked:
        if not role_status["enabled"]:
            return replace(
                deterministic,
                llm_assist_enabled=False,
                template_match_llm_hints=None,
            )
        return replace(
            deterministic,
            llm_assist_enabled=False,
            template_match_llm_hints=None,
        )

    hints, timed_out, adapter_notes = _fetch_semantic_hints(
        user_query=user_query,
        normalized_route_plan=normalized_route_plan,
        llm_raw_output_provider=llm_raw_output_provider,
    )
    disagreements = _compare_hints_to_match(deterministic, hints, normalized_route_plan)
    merged_disagreements = list(deterministic.disagreements) + disagreements
    hint_payload = None
    if hints is not None or adapter_notes or timed_out:
        hint_payload = {
            "llm_semantic_hints": hints,
            "adapter_notes": adapter_notes,
            "coe_synthetic_fixture": True,
            "captured_live_run": False,
            "production_execution": False,
        }

    return replace(
        deterministic,
        disagreements=merged_disagreements,
        template_match_llm_hints=hint_payload,
        llm_assist_timed_out=timed_out,
        llm_assist_enabled=True,
    )


def sanitize_template_match_llm_payload(raw_output: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse and sanitize LLM semantic-hint JSON via the guarded adapter."""
    notes: list[str] = []
    result = adapt_llm_output(role=TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE, raw_output=raw_output)
    if not result.accepted or not result.normalized_payload:
        if not result.schema_valid:
            notes.append("schema_invalid")
        notes.extend(result.errors)
        notes.extend(result.warnings)
        return None, notes

    payload = result.normalized_payload
    dropped = list(result.dropped_fields)
    if dropped:
        if "template_id" in dropped or any("template" in field for field in dropped):
            notes.append("template_id_stripped")
        notes.extend(f"dropped_field:{field}" for field in dropped)

    hints = payload.get("llm_semantic_hints")
    if not isinstance(hints, dict):
        notes.append("schema_invalid")
        return None, notes

    sanitized, strip_notes = _sanitize_hints_dict(hints)
    notes.extend(strip_notes)
    if not sanitized:
        return None, notes
    return {"llm_semantic_hints": sanitized}, notes


def _fetch_semantic_hints(
    *,
    user_query: str,
    normalized_route_plan: dict[str, Any],
    llm_raw_output_provider: Callable[[], str] | None,
) -> tuple[dict[str, Any] | None, bool, list[str]]:
    if llm_raw_output_provider is None:
        return None, False, ["live_llm_template_match_assist_disabled"]

    timed_out = False
    raw_output = ""
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(llm_raw_output_provider)
            raw_output = future.result(timeout=TEMPLATE_MATCH_ASSIST_TIMEOUT_SECONDS)
    except (FuturesTimeoutError, TimeoutError):
        return None, True, ["llm_assist_timed_out"]

    payload, notes = sanitize_template_match_llm_payload(raw_output)
    if payload is None:
        return None, timed_out, notes
    return payload.get("llm_semantic_hints"), timed_out, notes


def _sanitize_hints_dict(hints: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    cleaned: dict[str, Any] = {}

    if "template_id" in hints:
        notes.append("template_id_stripped")

    source_hint = hints.get("source_class_hint")
    if isinstance(source_hint, str) and source_hint.strip():
        value = source_hint.strip()
        if SPL_FRAGMENT_PATTERN.search(value):
            notes.append("spl_in_hint_forbidden")
        elif value in APPROVED_SOURCE_CLASS_HINTS:
            cleaned["source_class_hint"] = value

    datamodel_hint = hints.get("datamodel_hint")
    if isinstance(datamodel_hint, str) and datamodel_hint.strip():
        value = datamodel_hint.strip()
        if SPL_FRAGMENT_PATTERN.search(value):
            notes.append("spl_in_hint_forbidden")
        elif value in APPROVED_DATAMODELS:
            cleaned["datamodel_hint"] = value
        else:
            notes.append("unknown_datamodel")

    aliases = hints.get("field_aliases")
    if isinstance(aliases, dict):
        datamodel = cleaned.get("datamodel_hint")
        allowed = DATAMODEL_FIELD_ALLOWLIST.get(datamodel, set()) if datamodel else set()
        sanitized_aliases: dict[str, str] = {}
        for phrase, field_name in aliases.items():
            if not isinstance(phrase, str) or not isinstance(field_name, str):
                continue
            if SPL_FRAGMENT_PATTERN.search(phrase) or SPL_FRAGMENT_PATTERN.search(field_name):
                notes.append("spl_in_hint_forbidden")
                continue
            if datamodel and field_name not in allowed:
                notes.append(f"unknown_field_alias:{field_name}")
                continue
            sanitized_aliases[phrase] = field_name
        if sanitized_aliases:
            cleaned["field_aliases"] = sanitized_aliases

    return cleaned, notes


def _compare_hints_to_match(
    match: TemplateMatchResult,
    hints: dict[str, Any] | None,
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    if not hints:
        return []

    disagreements: list[dict[str, Any]] = []
    evidence = plan.get("evidence_needs") if isinstance(plan.get("evidence_needs"), dict) else {}
    deterministic_datamodel = match.datamodel or evidence.get("datamodel")
    hint_datamodel = hints.get("datamodel_hint")
    if hint_datamodel and hint_datamodel != deterministic_datamodel:
        disagreements.append(
            {
                "field": "datamodel",
                "llm_value": hint_datamodel,
                "deterministic_value": deterministic_datamodel,
                "reason_for_deterministic_win": "datamodel_hint_advisory_only",
            }
        )

    parameters = plan.get("parameters") if isinstance(plan.get("parameters"), dict) else {}
    group_by = parameters.get("group_by") if isinstance(parameters.get("group_by"), dict) else {}
    deterministic_group_by = group_by.get("field")
    for _phrase, alias_field in (hints.get("field_aliases") or {}).items():
        if alias_field != deterministic_group_by:
            disagreements.append(
                {
                    "field": "group_by",
                    "llm_value": alias_field,
                    "deterministic_value": deterministic_group_by,
                    "reason_for_deterministic_win": "field_alias_advisory_only",
                }
            )
    return disagreements


def _role_assist_status(*, assist_invoked: bool = False) -> dict[str, Any]:
    if settings.ai_soc_llm_mode.strip().lower() == "disabled" or not settings.ai_soc_llm_enabled:
        return {"enabled": False, "rejected_reason": None}

    configured_provider = settings.ai_soc_llm_template_match_provider.strip()
    configured_model = settings.ai_soc_llm_template_match_model.strip()
    if configured_provider == REASONING_PROVIDER_ID or "reasoning" in configured_model.lower():
        return {
            "enabled": False,
            "rejected_reason": "reasoning_model_not_allowed_for_matching",
        }

    governance = build_llm_governance_status()
    role_entry = next(
        (item for item in governance.get("roles", []) if item.get("role") == TEMPLATE_MATCH_SEMANTIC_ASSIST_ROLE),
        None,
    )
    if not role_entry:
        if assist_invoked:
            return {"enabled": True, "rejected_reason": None}
        return {"enabled": False, "rejected_reason": "role_not_configured"}

    if not role_entry.get("enabled"):
        return {"enabled": False, "rejected_reason": "role_not_enabled"}
    return {"enabled": True, "rejected_reason": None}
