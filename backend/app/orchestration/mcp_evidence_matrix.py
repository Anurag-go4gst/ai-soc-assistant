"""P3: report-first MCP evidence-needs matrix.

This module is read-only. It builds deterministic records that explain which
evidence families a question/operation would need and which MCP tools could be
eligible after existing validation gates. It never calls MCP and never grants
execution authority.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.coverage.coverage_loader import coverage_for_id, list_coverage
from app.coverage.question_runtime_map import list_question_runtime_entries
from app.orchestration.evidence_mcp_mapping import (
    DETECTION_REGISTRY_BINDING,
    LOCAL_LOOKUP_REGISTRY,
    SPLUNK_AUTH_EVIDENCE,
    SPLUNK_METADATA_DISCOVERY,
    map_evidence_need_to_mcp_tools,
)


_MCP_DISCOVERED_REPORT_TOOLS = [
    "splunk_get_indexes",
    "splunk_get_metadata",
    "splunk_run_query",
    "splunk_run_saved_search",
    "saia_generate_spl",
]


def build_operation_mcp_evidence_matrix() -> dict[str, Any]:
    """Build the P3 operation/pattern → evidence-needs matrix."""
    rows: list[dict[str, Any]] = []
    for entry in list_coverage():
        raw = entry.model_dump(mode="json")
        needs = _needs_for_manifest_row(raw)
        rows.append(_matrix_row(raw, needs, source="promoted_manifest"))
    return _matrix_payload(rows, scope="promoted_manifest")


def build_question_mcp_evidence_report() -> dict[str, Any]:
    """Build a 105-question report with manifest rows and non-promoted estimates."""
    manifest_rows = {
        row.coverage_id: row.model_dump(mode="json")
        for row in list_coverage()
    }
    rows: list[dict[str, Any]] = []
    for question in list_question_runtime_entries():
        coverage_id = question.get("manifest_coverage_id")
        manifest = manifest_rows.get(coverage_id) if isinstance(coverage_id, str) else None
        if manifest:
            needs = _needs_for_manifest_row(manifest)
            raw = {**question, "coverage_id": coverage_id, "primary_skill": manifest.get("primary_skill")}
            rows.append(_matrix_row(raw, needs, source="promoted_manifest"))
            continue
        needs = _needs_for_question_row(question)
        rows.append(_matrix_row(question, needs, source="question_runtime_estimate"))
    return _matrix_payload(rows, scope="question_runtime_map_105")


def mcp_evidence_needs_for_coverage(coverage_id: str) -> dict[str, Any] | None:
    """Return a single promoted coverage row report."""
    coverage = coverage_for_id(coverage_id)
    if coverage is None:
        return None
    raw = coverage.model_dump(mode="json")
    return _matrix_row(raw, _needs_for_manifest_row(raw), source="promoted_manifest")


def _matrix_payload(rows: list[dict[str, Any]], *, scope: str) -> dict[str, Any]:
    need_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for row in rows:
        source_counts[str(row.get("matrix_source"))] += 1
        for need in row.get("mcp_evidence_needs", []):
            need_counts[str(need)] += 1
    return {
        "schema_version": "p3_mcp_evidence_matrix_v1",
        "scope": scope,
        "authority": "report_only",
        "mcp_called": False,
        "execution_authorized": False,
        "llm_tool_suggestions_authority": "ignored_advisory_only",
        "row_count": len(rows),
        "need_counts": dict(sorted(need_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "rows": rows,
    }


def _matrix_row(raw: dict[str, Any], needs: list[str], *, source: str) -> dict[str, Any]:
    unique_needs = list(dict.fromkeys(needs))
    mappings = [
        map_evidence_need_to_mcp_tools(
            evidence_need=need,
            discovered_tools=_MCP_DISCOVERED_REPORT_TOOLS,
            llm_suggested_tool_names=["saia_generate_spl", "splunk_run_saved_search"],
        )
        for need in unique_needs
    ]
    return {
        "question_ref": raw.get("question_ref"),
        "question": raw.get("question"),
        "coverage_id": raw.get("coverage_id") or raw.get("manifest_coverage_id"),
        "primary_operation": raw.get("primary_skill") or raw.get("proposed_primary_skill"),
        "operation_type": _operation_type(raw),
        "dependency_class": raw.get("dependency_class"),
        "matrix_source": source,
        "mcp_evidence_needs": unique_needs,
        "mcp_tool_mappings": mappings,
        "mcp_called": False,
        "execution_authorized": False,
        "real_mcp_blocked_until_coe_contract": True,
    }


def _needs_for_manifest_row(row: dict[str, Any]) -> list[str]:
    needs: list[str] = []
    route_shape = row.get("route_plan_shape") if isinstance(row.get("route_plan_shape"), dict) else {}
    if row.get("template_ref") or route_shape.get("evidence_needs"):
        needs.extend([SPLUNK_METADATA_DISCOVERY, SPLUNK_AUTH_EVIDENCE])
    if row.get("lookup_ref") or row.get("readiness") == "ioc_dependent":
        needs.append(LOCAL_LOOKUP_REGISTRY)
    if row.get("detection_ref") or row.get("detection_family") or row.get("readiness") == "detection_dependent":
        needs.append(DETECTION_REGISTRY_BINDING)
    if not needs:
        needs.append(SPLUNK_METADATA_DISCOVERY)
    return needs


def _needs_for_question_row(row: dict[str, Any]) -> list[str]:
    dependency = str(row.get("dependency_class") or "")
    operation_type = _operation_type(row)
    needs: list[str] = []
    if dependency in {"source_binding", "notable_risk_source"}:
        needs.append(SPLUNK_METADATA_DISCOVERY)
    if dependency == "local_lookup":
        needs.append(LOCAL_LOOKUP_REGISTRY)
    if dependency == "detection_binding":
        needs.append(DETECTION_REGISTRY_BINDING)
    if operation_type in {
        "top_n",
        "threshold_anomaly",
        "success_after_failure",
        "risk_lookup",
        "detection_binding",
        "ioc_correlation",
        "lookup_match",
    }:
        needs.append(SPLUNK_AUTH_EVIDENCE)
    if not needs:
        needs.append(SPLUNK_METADATA_DISCOVERY)
    return needs


def _operation_type(row: dict[str, Any]) -> str | None:
    route_shape = row.get("route_plan_shape") if isinstance(row.get("route_plan_shape"), dict) else {}
    value = route_shape.get("operation_type") or row.get("proposed_operation_type")
    return str(value) if value else None
