"""Placeholder resolution orchestration (SPL audit Phase H).

Resolution ladder:
  H0 — config / policy map
  H1 — governed SOC-KB retrieval hints
  H2 — COE-gated MCP discovery scaffold (no real execution until COE)
  H3 — session pins + HIL clarification for remaining slots
  H4 — substituted SPL re-validated for `normalized_spl`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.orchestration.human_review import human_review
from app.safeguards.spl_validator import validate_spl
from app.spl.rag_source_profile_bridge import extract_rag_source_profile
from app.spl.source_profile_resolver import (
    extract_placeholder_slots,
    load_static_source_profile,
    merge_profiles,
    substitute_placeholders,
)


@dataclass(frozen=True)
class SourceResolveResult:
    spl: str
    resolved_slots: dict[str, str] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    tiers_used: list[str] = field(default_factory=list)
    fully_resolved: bool = False
    validation: dict[str, Any] | None = None


def try_mcp_source_discovery(*, required_slots: list[str]) -> dict[str, str]:
    """H2 scaffold — returns values only when mock MCP execution is explicitly enabled."""
    del required_slots
    if not settings.mcp_global_execution_enabled:
        return {}
    if str(settings.mcp_mode or "").lower() != "mock":
        return {}
    return {}


def build_spl_source_profile_review(missing_slots: list[str]) -> dict[str, Any]:
    slot_list = ", ".join(f"<{slot}>" for slot in missing_slots)
    return human_review(
        review_type="spl_source_profile_clarification",
        reason="source_profile_slots_missing",
        reviewer_role="analyst",
        allowed_actions=["provide_source_profile", "cancel"],
        safe_message_for_user=(
            "This SPL still needs source configuration before search can run. "
            f"Provide values for: {slot_list}."
        ),
        required=True,
    )


def resolve_spl_source_profile(
    spl: str,
    *,
    user_query: str,
    soc_kb_retrieval: dict[str, Any] | None = None,
    session_slots: dict[str, str] | None = None,
    required_sources: list[str] | None = None,
) -> SourceResolveResult:
    del user_query
    text = (spl or "").strip()
    if not text or "<" not in text:
        return SourceResolveResult(text, fully_resolved=True)

    required_slots = extract_placeholder_slots(text)
    tiers_used: list[str] = []

    profile = load_static_source_profile(session_slots=session_slots)
    if profile:
        tiers_used.append("h0_config")

    rag_profile = extract_rag_source_profile(
        soc_kb_retrieval,
        required_sources=required_sources,
        required_slots=required_slots,
    )
    if rag_profile:
        tiers_used.append("h1_rag")
    profile = merge_profiles(profile, rag_profile)

    mcp_profile = try_mcp_source_discovery(required_slots=required_slots)
    if mcp_profile:
        tiers_used.append("h2_mcp")
    profile = merge_profiles(profile, mcp_profile)

    resolved_slots = {slot: profile[slot] for slot in required_slots if slot in profile and profile[slot]}
    substituted, missing_slots = substitute_placeholders(text, profile)
    if session_slots:
        tiers_used.append("h3_session")

    if missing_slots:
        return SourceResolveResult(
            spl=text,
            resolved_slots=resolved_slots,
            missing_slots=missing_slots,
            tiers_used=tiers_used,
            fully_resolved=False,
        )

    validation = validate_spl(substituted)
    fully_resolved = bool(validation.get("approved") and validation.get("normalized_spl"))
    if fully_resolved:
        tiers_used.append("h4_validated")
    return SourceResolveResult(
        spl=substituted,
        resolved_slots=resolved_slots,
        missing_slots=[],
        tiers_used=tiers_used,
        fully_resolved=fully_resolved,
        validation=validation,
    )
