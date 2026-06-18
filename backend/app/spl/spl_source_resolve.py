"""Placeholder resolution orchestration (SPL audit Phase H).

Authority order (later wins on conflict):
  1. Policy / env defaults (lowest)
  2. SOC-KB RAG hints
  3. Session / chat-provided slots
  4. MCP discovery fills blanks from splunk_get_indexes / get_metadata
  5. Asset registry derived slots
  6. COE persisted store (Settings UI) — highest for conflicts
  7. HIL only when slots still missing after merge
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.orchestration.human_review import human_review
from app.safeguards.spl_validator import validate_spl
from app.environment.asset_registry_store import build_asset_registry_profile
from app.spl.mcp_source_discovery import run_mcp_source_discovery
from app.spl.rag_source_profile_bridge import extract_rag_source_profile
from app.spl.source_profile_resolver import (
    build_policy_derived_profile,
    extract_placeholder_slots,
    merge_profiles,
    substitute_placeholders,
)
from app.spl.source_profile_store import load_persisted_source_profile, load_persisted_source_profile_document
from app.spl.template_registry import get_spl_template


@dataclass(frozen=True)
class SourceResolveResult:
    spl: str
    resolved_slots: dict[str, str] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    tiers_used: list[str] = field(default_factory=list)
    slot_sources: dict[str, str] = field(default_factory=dict)
    mcp_discovery_trace: dict[str, Any] = field(default_factory=dict)
    fully_resolved: bool = False
    validation: dict[str, Any] | None = None


def build_spl_source_profile_review(missing_slots: list[str]) -> dict[str, Any]:
    slot_list = ", ".join(f"<{slot}>" for slot in missing_slots)
    return human_review(
        review_type="spl_source_profile_clarification",
        reason="source_profile_slots_missing",
        reviewer_role="analyst",
        allowed_actions=["provide_source_profile", "open_source_profile_settings", "cancel"],
        safe_message_for_user=(
            "This SPL still needs source configuration before search can run. "
            f"Provide values for: {slot_list}. "
            "Open Settings → Environment Knowledge to enter COE index/sourcetype names, "
            "or refresh from MCP discovery."
        ),
        required=True,
    )


def _slot_source_map(
    *,
    persisted: dict[str, str],
    persisted_sources: dict[str, str],
    rag_profile: dict[str, str],
    session_slots: dict[str, str],
    mcp_profile: dict[str, str],
    asset_profile: dict[str, str],
) -> dict[str, str]:
    sources: dict[str, str] = {}
    for slot_id in set(persisted) | set(rag_profile) | set(session_slots) | set(mcp_profile) | set(asset_profile):
        if slot_id in persisted:
            sources[slot_id] = persisted_sources.get(slot_id, "coe_ui")
        elif slot_id in asset_profile:
            sources[slot_id] = "asset_registry"
        elif slot_id in mcp_profile:
            sources[slot_id] = "mcp_discovery"
        elif slot_id in session_slots:
            sources[slot_id] = "chat_or_session"
        elif slot_id in rag_profile:
            sources[slot_id] = "rag_kb"
        else:
            sources[slot_id] = "policy_or_env"
    return sources


def resolve_spl_source_profile(
    spl: str,
    *,
    user_query: str,
    soc_kb_retrieval: dict[str, Any] | None = None,
    session_slots: dict[str, str] | None = None,
    required_sources: list[str] | None = None,
    run_mcp_discovery: bool = True,
    template_id: str | None = None,
) -> SourceResolveResult:
    del user_query
    text = (spl or "").strip()
    if not text or "<" not in text:
        return SourceResolveResult(text, fully_resolved=True)

    required_slots = extract_placeholder_slots(text)
    tiers_used: list[str] = []
    mcp_trace: dict[str, Any] = {}

    policy_profile = build_policy_derived_profile()
    if policy_profile:
        tiers_used.append("policy_env")

    persisted_sources = dict(load_persisted_source_profile_document().get("field_sources") or {})
    persisted = load_persisted_source_profile()
    if persisted:
        tiers_used.append("coe_store")

    rag_profile = extract_rag_source_profile(
        soc_kb_retrieval,
        required_sources=required_sources,
        required_slots=required_slots,
    )
    if rag_profile:
        tiers_used.append("rag_kb")

    session_profile = dict(session_slots or {})
    if session_profile:
        tiers_used.append("chat_session")

    mcp_profile: dict[str, str] = {}
    if run_mcp_discovery and settings.mcp_discovery_enabled:
        mcp_profile, mcp_trace = run_mcp_source_discovery(required_slots=required_slots)
        if mcp_profile:
            tiers_used.append("mcp_discovery")

    asset_profile = build_asset_registry_profile(required_slots)
    if asset_profile:
        tiers_used.append("asset_registry")

    # COE/manual persisted values are authoritative. MCP discovery fills blanks
    # only in the effective merge and must not override analyst-entered slots.
    profile = merge_profiles(policy_profile, rag_profile, session_profile, mcp_profile, asset_profile, persisted)

    resolved_slots = {slot: profile[slot] for slot in required_slots if slot in profile and profile[slot]}
    substituted, missing_slots = substitute_placeholders(text, profile)
    slot_sources = _slot_source_map(
        persisted=persisted,
        persisted_sources=persisted_sources,
        rag_profile=rag_profile,
        session_slots=session_profile,
        mcp_profile=mcp_profile,
        asset_profile=asset_profile,
    )

    if missing_slots:
        return SourceResolveResult(
            spl=text,
            resolved_slots=resolved_slots,
            missing_slots=missing_slots,
            tiers_used=tiers_used,
            slot_sources=slot_sources,
            mcp_discovery_trace=mcp_trace,
            fully_resolved=False,
        )

    template = get_spl_template(template_id)
    validation = validate_spl(
        substituted,
        template_profile=template.validation_rules if template is not None else None,
    )
    fully_resolved = bool(validation.get("approved") and validation.get("normalized_spl"))
    if fully_resolved:
        tiers_used.append("validated_normalized_spl")
    return SourceResolveResult(
        spl=substituted,
        resolved_slots=resolved_slots,
        missing_slots=[],
        tiers_used=tiers_used,
        slot_sources=slot_sources,
        mcp_discovery_trace=mcp_trace,
        fully_resolved=fully_resolved,
        validation=validation,
    )
