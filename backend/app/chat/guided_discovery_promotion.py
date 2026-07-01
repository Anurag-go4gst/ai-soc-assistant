"""HIL promotion offer for guided read-only MCP discovery (metadata only)."""

from __future__ import annotations

from typing import Any

_VETTED_OBJECT_TYPES = frozenset({"saved_search", "savedsearch", "macro", "data_model"})


def build_guided_discovery_promotion_offer(
    mcp_evidence: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Return a deterministic HIL promotion offer when knowledge objects plausibly match a governed hunt."""
    if not mcp_evidence:
        return None
    for hop in mcp_evidence:
        if str(hop.get("tool") or "") != "splunk_get_knowledge_objects":
            continue
        payload = hop.get("payload") if isinstance(hop.get("payload"), dict) else {}
        candidates = _knowledge_object_candidates(payload)
        if not candidates:
            continue
        best = candidates[0]
        return {
            "offer_type": "governed_route_rephrase",
            "suggested_route": "spl_generation",
            "knowledge_object_name": best.get("name"),
            "knowledge_object_type": best.get("object_type"),
            "message": (
                f"Governed saved artifact '{best.get('name')}' may cover this hunt — "
                "an analyst can re-run under spl_generation with confirmation."
            ),
            "analyst_confirmation_required": True,
            "authority_impact": "none",
        }
    return None


def _knowledge_object_candidates(payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, Any]] = []
    objects = payload.get("objects")
    if isinstance(objects, list):
        rows.extend(item for item in objects if isinstance(item, dict))
    preview = payload.get("preview_rows")
    if isinstance(preview, list):
        rows.extend(item for item in preview if isinstance(item, dict))
    candidates: list[dict[str, str]] = []
    for row in rows:
        object_type = str(row.get("object_type") or row.get("type") or row.get("kind") or "").lower()
        name = str(row.get("name") or row.get("title") or row.get("saved_search") or "").strip()
        if not name:
            continue
        if object_type and object_type not in _VETTED_OBJECT_TYPES:
            continue
        candidates.append({"name": name, "object_type": object_type or "saved_search"})
    return candidates
