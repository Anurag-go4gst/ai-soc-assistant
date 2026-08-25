"""Factual SPL + LLM provenance helpers for trace surfaces (read-model only)."""

from __future__ import annotations

from typing import Any

_DETERMINISTIC_SPL_PROVIDERS = frozenset({
    "deterministic_lab_draft",
    "deterministic_skeleton",
})

_LIVE_LLM_SPL_PROVIDERS = frozenset({
    "utility_llm_spl_draft",
    "llm_spl_advisory",
    "llm_spl_advisory_fallback",
})

_REPAIR_SPL_PROVIDERS = frozenset({
    "bounded_llm_repair",
    "utility_llm_spl_repair",
})


def _utility_trace(candidate: dict[str, Any]) -> dict[str, Any]:
    trace = candidate.get("utility_spl_draft_trace")
    return trace if isinstance(trace, dict) else {}


def spl_provider_label(candidate: dict[str, Any] | None, validation: dict[str, Any] | None = None) -> str:
    """Canonical provider string from candidate/validation payloads."""
    for payload in (validation, candidate):
        if not isinstance(payload, dict):
            continue
        provider = str(payload.get("selected_candidate_spl_provider") or "").strip()
        if provider:
            return provider
    return ""


def spl_artifact_source(
    candidate: dict[str, Any] | None,
    validation: dict[str, Any] | None = None,
) -> str:
    """Map runtime provider/generation_mode to factual spl_artifact_source."""
    candidate = candidate if isinstance(candidate, dict) else {}
    validation = validation if isinstance(validation, dict) else {}
    provider = spl_provider_label(candidate, validation)
    generation_mode = str(
        candidate.get("generation_mode") or validation.get("generation_mode") or ""
    ).strip()

    if provider in _LIVE_LLM_SPL_PROVIDERS or generation_mode == "utility_llm_spl_draft":
        return "live_llm"
    if provider in _REPAIR_SPL_PROVIDERS or generation_mode == "utility_llm_spl_repair":
        return "bounded_llm_repair"
    if provider == "deterministic_lab_draft" or generation_mode == "deterministic_lab_draft":
        utility = _utility_trace(candidate)
        if utility.get("llm_spl_draft_used"):
            return "live_llm"
        if utility.get("unavailable_reason") or candidate.get("spl_authoring_unavailable"):
            return "unavailable"
        return "deterministic_fallback"
    if provider == "deterministic_user_bound_skeleton" or generation_mode == "deterministic_user_bound_skeleton":
        return "deterministic_fallback"
    if validation.get("approved") and validation.get("normalized_spl"):
        return "governed_template"
    if candidate.get("spl_authoring_unavailable"):
        return "unavailable"
    return "deterministic_fallback"


def llm_candidate_generated(candidate: dict[str, Any] | None) -> bool:
    candidate = candidate if isinstance(candidate, dict) else {}
    source = spl_artifact_source(candidate)
    return source in {"live_llm", "bounded_llm_repair"}


def deterministic_fallback_used(candidate: dict[str, Any] | None) -> bool:
    candidate = candidate if isinstance(candidate, dict) else {}
    source = spl_artifact_source(candidate)
    return source == "deterministic_fallback"


def fallback_reason(candidate: dict[str, Any] | None) -> str | None:
    candidate = candidate if isinstance(candidate, dict) else {}
    utility = _utility_trace(candidate)
    explicit = str(candidate.get("deterministic_fallback_reason") or utility.get("llm_spl_draft_dropped_reason") or "").strip()
    if explicit:
        return explicit
    if spl_artifact_source(candidate) == "unavailable":
        return str(candidate.get("spl_authoring_unavailable_reason") or "validation_failed").strip() or None
    if deterministic_fallback_used(candidate):
        return str(
            candidate.get("llm_fallback_reason")
            or utility.get("llm_spl_draft_skipped_reason")
            or "deterministic_fallback"
        ).strip() or None
    return None


def is_real_llm_spl_provider(provider: str | None) -> bool:
    key = str(provider or "").strip()
    return key in _LIVE_LLM_SPL_PROVIDERS or key in _REPAIR_SPL_PROVIDERS


def is_deterministic_spl_provider(provider: str | None) -> bool:
    key = str(provider or "").strip()
    return key in _DETERMINISTIC_SPL_PROVIDERS or key == "deterministic_lab_draft"


def llm_attempted_from_budget(records: list[dict[str, Any]] | None) -> bool:
    if not isinstance(records, list):
        return False
    return any(str(item.get("outcome") or "") in {"completed", "timed_out", "dropped"} for item in records if isinstance(item, dict))


def llm_live_call_count(records: list[dict[str, Any]] | None) -> int:
    if not isinstance(records, list):
        return 0
    return sum(
        1
        for item in records
        if isinstance(item, dict) and str(item.get("outcome") or "") == "completed"
    )


def llm_roles_from_budget(records: list[dict[str, Any]] | None) -> list[str]:
    if not isinstance(records, list):
        return []
    roles: list[str] = []
    for item in records:
        if not isinstance(item, dict) or str(item.get("outcome") or "") != "completed":
            continue
        role = str(item.get("role") or "").strip()
        if role and role not in roles:
            roles.append(role)
    return roles


def llm_used_factual(
    *,
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    budget_records: list[dict[str, Any]] | None,
) -> bool:
    """True only when at least one real governed LLM endpoint attempt completed."""
    if llm_live_call_count(budget_records) > 0:
        return True
    candidate = candidate_spl if isinstance(candidate_spl, dict) else {}
    validation = spl_validation if isinstance(spl_validation, dict) else {}
    utility = _utility_trace(candidate) or _utility_trace(validation)
    if utility.get("llm_spl_draft_used"):
        return True
    provider = spl_provider_label(candidate, validation)
    return is_real_llm_spl_provider(provider)


def llm_failover_used_factual(
    *,
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    budget_records: list[dict[str, Any]] | None,
) -> bool:
    """Failover only when a real primary LLM attempt preceded a deterministic fallback artifact."""
    candidate = candidate_spl if isinstance(candidate_spl, dict) else {}
    validation = spl_validation if isinstance(spl_validation, dict) else {}
    source = spl_artifact_source(candidate, validation)
    if source == "unavailable":
        return False
    if not deterministic_fallback_used(candidate_spl):
        return False
    utility = _utility_trace(candidate)
    attempted = llm_attempted_from_budget(budget_records) or bool(utility.get("llm_spl_draft_requested"))
    return attempted and bool(utility.get("deterministic_skeleton_used") or utility.get("llm_spl_draft_dropped_reason"))


def build_spl_authoring_provenance_lines(
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Analyst-visible SPL draft provenance lines (no chain-of-thought)."""
    candidate = candidate_spl if isinstance(candidate_spl, dict) else {}
    if not candidate and not spl_validation:
        return []
    source = spl_artifact_source(candidate, spl_validation)
    source_labels = {
        "live_llm": "SPL draft governed LLM",
        "bounded_llm_repair": "SPL draft bounded LLM repair",
        "deterministic_fallback": "SPL draft deterministic fallback",
        "governed_template": "SPL draft governed template",
        "unavailable": "SPL draft unavailable",
    }
    lines = [
        {"label": "SPL draft", "value": source_labels.get(source, source.replace("_", " "))},
        {"label": "Binding", "value": "deterministic"},
        {"label": "Validation", "value": "deterministic"},
        {"label": "Execution", "value": "not requested"},
    ]
    reason = fallback_reason(candidate)
    if reason and source in {"deterministic_fallback", "unavailable"}:
        lines.insert(4, {"label": "Reason", "value": reason.replace("_", " ")})
    return lines


def build_spl_provenance_summary(
    candidate_spl: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None = None,
    budget_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    candidate = candidate_spl if isinstance(candidate_spl, dict) else {}
    validation = spl_validation if isinstance(spl_validation, dict) else {}
    source = spl_artifact_source(candidate, validation)
    return {
        "llm_attempted": llm_attempted_from_budget(budget_records) or bool(_utility_trace(candidate).get("llm_spl_draft_requested")),
        "llm_live_calls": llm_live_call_count(budget_records),
        "llm_succeeded": llm_live_call_count(budget_records) > 0 or bool(_utility_trace(candidate).get("llm_spl_draft_used")),
        "llm_roles": llm_roles_from_budget(budget_records),
        "llm_candidate_generated": llm_candidate_generated(candidate),
        "deterministic_fallback_used": deterministic_fallback_used(candidate),
        "spl_artifact_source": source,
        "fallback_reason": fallback_reason(candidate),
        "llm_used": llm_used_factual(
            candidate_spl=candidate,
            spl_validation=validation,
            budget_records=budget_records,
        ),
        "llm_failover_used": llm_failover_used_factual(
            candidate_spl=candidate,
            spl_validation=validation,
            budget_records=budget_records,
        ),
        "trace_authority": "read_model_projection_only",
    }
