"""P2-10: Bridge use-case catalog rows to registry/operation hints (advisory only)."""

from __future__ import annotations

from typing import Any

from app.use_cases.registry import load_use_case_catalog, match_use_cases


def build_use_case_registry_bridge(query: str, *, limit: int = 3) -> dict[str, Any]:
    """Surface use-case catalog alignment without changing routing authority."""
    matches = match_use_cases(query, limit=limit)
    catalog = load_use_case_catalog()
    return {
        "enabled": True,
        "authority": "advisory_only",
        "catalog_size": len(catalog),
        "matched_use_cases": [
            {
                "use_case_id": item.use_case_id,
                "display_name": item.display_name,
                "primary_skill": item.primary_skill,
                "confidence": item.confidence,
                "matched_patterns": list(item.matched_patterns),
                "registry_operation_hint": item.primary_skill,
            }
            for item in matches
        ],
        "top_use_case_id": matches[0].use_case_id if matches else None,
        "top_operation_hint": matches[0].primary_skill if matches else None,
        "merge_status": "catalog_rows_advisory_until_ec_rebase",
    }
