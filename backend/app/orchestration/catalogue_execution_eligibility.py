from __future__ import annotations

from typing import Any

from app.config import settings
from app.coverage.catalogue_execution_map import resolve_catalogue_execution_binding

_CATALOGUE_MATCH_PATHS = frozenset({
    "exact_105_question",
    "exact_105_plus_use_case_catalog",
    "use_case_catalog",
    "exact_cisco_catalog",
})


def catalogue_auto_execute_eligible(
    *,
    match_path: str | None,
    question_ref: str | None,
    use_case_id: str | None,
    spl_validation: dict[str, Any] | None,
    selected_mcp_tool: str | None = None,
    llm_lineage_risk_tier: str | None = None,
    freeform_spl_execution_allowed: bool = False,
) -> tuple[bool, str | None]:
    if not settings.ai_soc_catalogue_auto_execute_enabled:
        return False, "catalogue_auto_execute_disabled"
    path = str(match_path or "").strip()
    if path not in _CATALOGUE_MATCH_PATHS:
        return False, "match_path_not_catalogue_known"
    binding = resolve_catalogue_execution_binding(question_ref=question_ref, use_case_id=use_case_id)
    if binding is None:
        return False, "no_catalogue_execution_binding"
    if not binding.coe_verified or not binding.auto_execute_eligible:
        return False, "binding_not_auto_execute_eligible"
    if path not in set(binding.match_paths or []):
        return False, "match_path_not_on_binding"
    if freeform_spl_execution_allowed:
        return False, "freeform_spl_not_catalogue_auto"
    tier = str(llm_lineage_risk_tier or "").strip().lower()
    if tier in {"medium", "high"}:
        return False, "llm_lineage_vigilance_blocked"
    if binding.execution_mode == "saved_search":
        if selected_mcp_tool and selected_mcp_tool != "splunk_run_saved_search":
            return False, "saved_search_tool_mismatch"
        if not settings.splunk_allow_run_saved_search:
            return False, "saved_search_execution_disabled"
        if not binding.saved_search_name:
            return False, "saved_search_name_missing"
        return True, "catalogue_known_saved_search_binding"
    if not spl_validation or spl_validation.get("approved") is not True:
        return False, "spl_not_approved"
    normalized = spl_validation.get("normalized_spl")
    if not isinstance(normalized, str) or not normalized.strip():
        return False, "normalized_spl_missing"
    if "<" in normalized or ">" in normalized:
        return False, "spl_slots_unresolved"
    if spl_validation.get("lab_tier") is True or spl_validation.get("llm_lineage_source"):
        return False, "non_governed_spl_source"
    return True, "catalogue_known_template_binding"
