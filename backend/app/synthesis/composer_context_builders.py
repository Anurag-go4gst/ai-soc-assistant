"""Build governed context slices for weak-case answer composition."""

from __future__ import annotations

from typing import Any

from app.connectors.mcp.registry import load_mcp_registry_status


def soc_kb_snippets_from_source_evidence(source_evidence: list[dict[str, Any]] | None) -> list[str]:
    """Redacted SOC-KB excerpt lines only — never raw MCP rows."""
    snippets: list[str] = []
    for item in source_evidence or []:
        if item.get("source_type") != "rag":
            continue
        if item.get("collection_status") not in {"collected", "ambiguous"}:
            continue
        for row in item.get("preview_rows") or []:
            if not isinstance(row, dict):
                continue
            excerpt = row.get("source_excerpt")
            if excerpt:
                snippets.append(str(excerpt)[:500])
    return snippets[:6]


def skill_sections_from_enrichment(projection: dict[str, Any] | None) -> list[str]:
    if not projection:
        return []
    sections: list[str] = []
    use_case_id = projection.get("use_case_id")
    if use_case_id:
        sections.append(f"use_case: {use_case_id}")
    for key, label in (
        ("planning_or_analytic_skill", "skill"),
        ("investigation_workflow", "workflow"),
        ("analyst_checklist", "checklist"),
        ("answer_rules", "rules"),
        ("recommended_pivots", "pivots"),
        ("evidence_requirements", "evidence_requirements"),
    ):
        values = projection.get(key)
        if not values:
            continue
        if isinstance(values, str):
            sections.append(f"{label}: {values}")
        else:
            sections.append(f"{label}: " + "; ".join(str(item) for item in values[:5] if item))
    return sections[:8]


def mcp_tool_hints_from_registry(*, mcp_allowed: bool) -> list[str]:
    """One-line capability hints — never parameters, schema, or credentials."""
    if not mcp_allowed:
        return []
    hints: list[str] = []
    registry = load_mcp_registry_status()
    for server in registry.servers:
        if not getattr(server, "configured", False):
            continue
        for tool in (getattr(server, "discovered_tools", None) or [])[:6]:
            if not isinstance(tool, dict):
                continue
            name = str(tool.get("name") or "").strip()
            if not name:
                continue
            description = str(tool.get("description") or tool.get("capability") or "bounded search tool").strip()
            hints.append(f"{name}: {description[:120]} (HIL-gated; review-only)")
    return hints[:8]
