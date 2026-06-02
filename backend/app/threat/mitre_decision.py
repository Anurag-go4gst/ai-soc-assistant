"""Runtime MITRE decision contract (Phase 1B stub — not wired into /chat pipeline yet)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.threat.mitre_registry_schema import MitreRegistryMetadata


class MitreDecision(BaseModel):
    """Governed runtime MITRE outcome (visibility + status); not observed evidence."""

    mitre_status: str = "legacy_passthrough"
    techniques: list[dict[str, Any]] = Field(default_factory=list)
    rejected_techniques: list[str] = Field(default_factory=list)
    registry_candidates: list[str] = Field(default_factory=list)
    not_claimed: list[str] = Field(default_factory=list)
    answer_visible: bool = False
    requires_alert_context: bool = False
    requires_more_context_for_supported_mapping: bool = False
    reason: str = ""
    registry_metadata: MitreRegistryMetadata | None = None


def resolve_mitre_decision(
    *,
    question_ref: str | None = None,
    use_case_id: str | None = None,
    registry_metadata: MitreRegistryMetadata | None = None,
    **_kwargs: Any,
) -> MitreDecision:
    """Stub: attach registry metadata for trace/debug; no live answer behavior change."""
    from app.threat.mitre_registry_enrichment import registry_mitre_metadata

    meta = registry_metadata
    if meta is None:
        meta = registry_mitre_metadata(question_ref=question_ref, use_case_id=use_case_id)

    candidates: list[str] = []
    if meta is not None:
        candidates = meta.all_mapped_technique_ids()

    return MitreDecision(
        mitre_status="legacy_passthrough",
        techniques=[],
        rejected_techniques=list(meta.mitre_blocked) if meta else [],
        registry_candidates=candidates,
        not_claimed=[],
        answer_visible=False,
        requires_alert_context=bool(meta.mitre_requires_alert_context) if meta else False,
        requires_more_context_for_supported_mapping=False,
        reason="Phase 1B stub: registry metadata attached; runtime MITRE decision not active.",
        registry_metadata=meta,
    )
