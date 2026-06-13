from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.config import settings
from app.safeguards.spl_validator import validate_spl
from app.spl.generator import CandidateSpl, StubSplGenerator
from app.splunk.capabilities import SplunkCapabilityProfile, build_splunk_capability_profile


def generate_candidate_spl_with_provider(trace_id: str, skill: str, user_query: str, profile: SplunkCapabilityProfile | None = None) -> tuple[CandidateSpl, dict[str, Any]]:
    profile = profile or build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    provider = _candidate_provider(profile)
    candidate = StubSplGenerator().generate(trace_id=trace_id, skill=skill, user_query=user_query)
    if provider == "saia_generate_spl":
        candidate = replace(candidate, generation_mode="saia_generate_spl", assumptions=[*candidate.assumptions, "SAIA output is candidate SPL only and requires AI-SOC validation."])
    elif provider == "template":
        candidate = replace(candidate, generation_mode="template", assumptions=[*candidate.assumptions, "AI-SOC template fallback used because SAIA is unavailable or disabled."])
    elif provider == "internal_llm":
        # The body here is always the deterministic StubSplGenerator — no live LLM
        # call happens on this path (real LLM failover lands in Phase C). Label the
        # generation_mode honestly as `stub` so the trace does not claim LLM output.
        candidate = replace(candidate, generation_mode="stub", assumptions=[*candidate.assumptions, "Internal LLM provider selected, but live LLM generation is not wired; body is a deterministic stub and requires validation."])
    else:
        candidate = CandidateSpl(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            candidate_spl="",
            generation_mode="unavailable",
            confidence=0.0,
            assumptions=["No candidate SPL provider available."],
            warnings=["manual_spl_required"],
        )
    metadata = {
        "selected_candidate_spl_provider": provider,
        "reason": _provider_reason(provider, profile, "saia_generate_spl"),
        "saia_available": profile.saia_available,
        "saia_usable": profile.saia_usable,
        "fallback_required": profile.fallback_required,
        "candidate_spl_generated": bool(candidate.candidate_spl),
        "validation_required": True,
        "execution_eligible": False,
        "capability_profile": profile.model_dump(),
    }
    return candidate, metadata


def explain_spl(spl: str, profile: SplunkCapabilityProfile | None = None) -> dict[str, Any]:
    profile = profile or build_splunk_capability_profile(required_saia_tool="saia_explain_spl")
    provider = "saia_explain_spl" if profile.saia_usable and profile.saia_explain_spl_available and settings.splunk_use_saia_explain_spl else "rule_based"
    return {
        "provider": provider,
        "advisory_only": True,
        "explanation": _rule_based_explanation(spl),
        "saia_available": profile.saia_available,
        "fallback_required": provider != "saia_explain_spl",
    }


def optimize_spl(spl: str, profile: SplunkCapabilityProfile | None = None) -> dict[str, Any]:
    profile = profile or build_splunk_capability_profile(required_saia_tool="saia_optimize_spl")
    provider = "saia_optimize_spl" if profile.saia_usable and profile.saia_optimize_spl_available and settings.splunk_use_saia_optimize_spl else "rule_based"
    optimized = _rule_based_optimize(spl)
    revalidation = validate_spl(optimized) if optimized != spl else None
    return {
        "provider": provider,
        "optimization_applied": optimized != spl,
        "optimized_candidate_spl": optimized,
        "requires_revalidation": optimized != spl,
        "revalidation_status": revalidation,
        "revalidation_approved": bool(revalidation and revalidation.get("approved")),
    }


def splunk_guidance(query: str, profile: SplunkCapabilityProfile | None = None) -> dict[str, Any]:
    profile = profile or build_splunk_capability_profile(required_saia_tool="saia_ask_splunk_question")
    if profile.saia_usable and profile.saia_ask_splunk_question_available and settings.splunk_use_saia_ask_question:
        provider = "saia_ask_splunk_question"
    elif profile.get_metadata_available or profile.get_knowledge_objects_available:
        provider = "scd_rag"
    else:
        provider = "unavailable"
    return {
        "provider": provider,
        "guidance": "Use governed Splunk context and SCD/RAG; validation and policy gates remain authoritative." if provider != "unavailable" else "",
        "can_bypass_validation": False,
        "fallback_required": provider != "saia_ask_splunk_question",
    }


def _candidate_provider(profile: SplunkCapabilityProfile) -> str:
    if profile.run_saved_search_available and settings.splunk_allow_run_saved_search:
        return "saved_search"
    if profile.saia_usable and profile.saia_generate_spl_available and settings.splunk_use_saia_generate_spl:
        return "saia_generate_spl"
    if settings.llm_enabled:
        return "internal_llm"
    return "template"


def _provider_reason(provider: str, profile: SplunkCapabilityProfile, required_tool: str) -> str:
    if provider.startswith("saia_"):
        return "saia_tool_discovered_enabled_and_usable"
    if provider == "saved_search":
        return "approved_saved_search_path_available"
    if required_tool not in profile.available_saia_tools:
        return "saia_tool_unavailable_ai_soc_fallback_used"
    if not profile.saia_usable:
        return "saia_disabled_or_unusable_ai_soc_fallback_used"
    return "ai_soc_fallback_provider_selected"


def _rule_based_explanation(spl: str) -> str:
    lowered = spl.lower()
    parts = []
    if "index=" in lowered:
        parts.append("uses an explicit index")
    if "sourcetype=" in lowered:
        parts.append("uses an explicit sourcetype")
    if "earliest=" in lowered and "latest=" in lowered:
        parts.append("has bounded time")
    if "| stats" in lowered or "| timechart" in lowered:
        parts.append("aggregates results")
    return "Rule-based SPL summary: " + (", ".join(parts) if parts else "basic search structure detected") + "."


def _rule_based_optimize(spl: str) -> str:
    optimized = " ".join(spl.strip().split())
    lowered = optimized.lower()
    if "earliest=" not in lowered:
        optimized = optimized.replace(" search ", " search ", 1)
        optimized += " earliest=-60m latest=now"
    if "| table " in lowered and "| stats " in lowered and lowered.index("| table ") < lowered.index("| stats "):
        segments = [part.strip() for part in optimized.split("|")]
        segments = [part for part in segments if not part.lower().startswith("table ")]
        optimized = " | ".join(segments)
    if "| head " not in optimized.lower() and "| sort" in optimized.lower():
        optimized += " | head 100"
    return optimized
