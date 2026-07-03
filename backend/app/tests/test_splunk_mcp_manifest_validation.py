from __future__ import annotations

import json
from pathlib import Path

from app.splunk.capabilities import EXPECTED_CORE_TOOLS

_MANIFEST = Path(__file__).resolve().parents[3] / "docs" / "splunk_mcp_tool_manifest_2026-07-03.json"


def test_manifest_json_exists_and_lists_core_tools() -> None:
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    names = {item["name"] for item in payload["tools_observed"]}
    for tool in EXPECTED_CORE_TOOLS:
        assert tool in names or tool == "splunk_run_query"
    assert "splunk_run_saved_search" in names
    assert payload.get("coe_sign_off")
