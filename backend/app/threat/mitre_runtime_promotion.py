"""Shared, pure derivation of the governed MITRE runtime patch from a DRAFT enrichment item.

Two producers write governed MITRE metadata into the runtime artifacts: the promoter CLI
(`scripts/promote_mitre_registry_to_runtime.py`) and the runtime-map builder
(`tools/coverage_authoring/question_runtime_map_builder.py`). They must derive that metadata
identically — the builder previously did not carry it at all, so a regeneration dropped the governed
`mitre_registry` block and re-routed those rows to the unsuppressed draft fallback, broadening
analyst-visible technique claims (Plan 5 A1/A2).

The logic lives here rather than in the promoter so both callers share one implementation. This
module is import-safe: it mutates no global state and touches no filesystem at import time, unlike
the promoter CLI, which inserts into `sys.path` when imported.
"""

from __future__ import annotations

from typing import Any

from app.threat.mitre_registry_enrichment import normalize_legacy_mitre_fields
from app.threat.mitre_registry_schema import MitreRegistryMetadata

__all__ = ["registry_block_from_draft", "runtime_patch_for_draft_item"]


def registry_block_from_draft(
    draft_item: dict[str, Any],
    meta: MitreRegistryMetadata,
) -> dict[str, Any]:
    """Build the governed `mitre_registry` block a runtime row carries."""
    raw = draft_item.get("mitre_registry")
    block = dict(raw) if isinstance(raw, dict) else {}
    block["schema_version"] = meta.schema_version
    block["registry_role"] = meta.registry_role
    block["permitted"] = list(meta.mitre_permitted)
    block["candidate"] = list(meta.mitre_candidate)
    block["blocked"] = list(meta.mitre_blocked)
    block["requires_evidence"] = meta.mitre_requires_evidence
    block["requires_alert_context"] = meta.mitre_requires_alert_context
    block["answer_visibility_policy"] = meta.mitre_visibility_policy.value
    if meta.mapping_rationale:
        block["mapping_rationale"] = meta.mapping_rationale
    blocked_rationale = block.get("blocked_rationale")
    if isinstance(blocked_rationale, dict):
        block["blocked_rationale"] = blocked_rationale
    return block


def runtime_patch_for_draft_item(
    draft_item: dict[str, Any],
    *,
    question_ref: str | None,
    use_case_id: str | None,
) -> dict[str, Any]:
    """Return the governed MITRE fields to merge onto a runtime row.

    Key insertion order is load-bearing: callers apply this with ``row.update(patch)``, so fields the
    row already has keep their original position and the remainder append in the order written here.
    That is what makes a regenerated artifact byte-identical to the committed one.

    `mitre_runtime_kb_overlap` / `mitre_runtime_kb_match_count` are taken from the DRAFT rather than
    recomputed against the runtime KB subset — the decision recorded as
    ``A_KB_OVERLAP_AUTHORITY = DRAFT_AUTHORITATIVE_CLOSED``. Measured on all 61 rows where the two
    sources disagree, the recomputed IDs are already in ``mitre_permitted`` and are filtered out by
    ``normalize_legacy_mitre_fields``, so the recompute changes no analyst-visible outcome.
    """
    meta = normalize_legacy_mitre_fields(
        draft_item,
        question_ref=question_ref,
        use_case_id=use_case_id,
    )
    registry = registry_block_from_draft(draft_item, meta)
    patch: dict[str, Any] = {
        "mitre_registry": registry,
        "mitre_registry_schema_version": meta.schema_version,
        "mitre_requires_evidence": meta.mitre_requires_evidence,
        "mitre_requires_alert_context": meta.mitre_requires_alert_context,
        "mitre_visibility_policy": meta.mitre_visibility_policy.value,
    }
    if question_ref:
        patch["mitre_permitted"] = list(meta.mitre_permitted)
        patch["mitre_candidate"] = list(meta.mitre_candidate)
        patch["mitre_blocked"] = list(meta.mitre_blocked)
        overlap = draft_item.get("kb_references")
        if isinstance(overlap, dict):
            kb_overlap = overlap.get("mitre_runtime_kb_overlap")
            if isinstance(kb_overlap, list):
                patch["mitre_runtime_kb_overlap"] = [str(x).upper() for x in kb_overlap if x]
                patch["mitre_runtime_kb_match_count"] = len(patch["mitre_runtime_kb_overlap"])
    if use_case_id:
        patch["mitre_candidates"] = list(meta.mitre_candidate) or list(meta.mitre_permitted)
        if meta.mitre_permitted:
            patch["mitre_permitted"] = list(meta.mitre_permitted)
        patch["mitre_blocked"] = list(meta.mitre_blocked)
    return patch
