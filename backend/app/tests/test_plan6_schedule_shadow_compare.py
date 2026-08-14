"""Plan 6 A3 — schedule shadow compare is offline-only and never calls MCP."""

from __future__ import annotations

import ast
from pathlib import Path

from app.evals.plan6_schedule_shadow import compare_schedules_offline

HELPER = (
    Path(__file__).resolve().parents[1] / "evals" / "plan6_schedule_shadow.py"
)

FORBIDDEN_IMPORT_FRAGMENTS = (
    "mcp_execution_gate",
    "splunk_mcp",
    "splunk_search",
    "mcp.client",
    "connectors.mcp",
)
FORBIDDEN_CALLS = (
    "evaluate_mcp_execution",
    "call_tool",
    "splunk_run_query",
)


def test_helper_source_never_imports_or_calls_mcp() -> None:
    source = HELPER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    called: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.append(module)
            imported.extend(f"{module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.append(func.id)
            elif isinstance(func, ast.Attribute):
                called.append(func.attr)
    for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
        assert not any(fragment in name for name in imported), imported
    for name in FORBIDDEN_CALLS:
        assert name not in called, called
    assert "evaluate_mcp_execution" not in source
    assert "call_tool" not in source


def test_offline_compare_returns_five_c2_probes_without_execution() -> None:
    payload = compare_schedules_offline()
    assert payload["schema_version"] == "plan6_schedule_shadow_v1"
    assert payload["execute_mcp"] is False
    ids = [row["probe_id"] for row in payload["rows"]]
    assert ids == [
        "t0_smb_spl",
        "t1_spl_artifact",
        "novel_identity_hunt",
        "mitre_reference",
        "knowledge_only",
    ]
    for row in payload["rows"]:
        assert isinstance(row["production_hooks"], list)
        assert isinstance(row["merged_hooks"], list)
        assert "capability_satisfied" in row
        assert "merge_downgrade" in row
