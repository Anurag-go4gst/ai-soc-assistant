"""P0 — metadata MCP tool playbook templates and envelope contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat.planned_mcp_call import argument_template_for_tool
from app.connectors.mcp.splunk_mcp_readiness import validate_mcp_result_envelope
from app.connectors.mcp.splunk_result_adapter import sanitize_result_envelope
from app.connectors.mcp.splunk_result_envelope import SplunkResultEnvelope

_PLAYBOOK = Path(__file__).resolve().parents[1] / "connectors" / "mcp" / "mcp_tool_playbook.json"

# Vendor live responses are not operator-signed; envelopes stay REAL_SCHEMA_UNVERIFIED.
REAL_SCHEMA_UNVERIFIED = "real_schema_unverified"


def _playbook_tools() -> dict:
    payload = json.loads(_PLAYBOOK.read_text(encoding="utf-8"))
    tools = payload.get("tools") if isinstance(payload, dict) else {}
    return tools if isinstance(tools, dict) else {}


def _metadata_envelope(tool_name: str) -> SplunkResultEnvelope:
    return SplunkResultEnvelope(
        status="ok",
        origin="mock_connector",
        schema_confirmed=False,
        schema_confirmed_reason=REAL_SCHEMA_UNVERIFIED,
        row_count=0,
        total_row_count=0,
        truncated=False,
        truncation_reason=None,
        fields=(),
        rows=(),
        duration_ms=5,
        error_code=None,
        error_message=None,
        warnings=(REAL_SCHEMA_UNVERIFIED,),
        provenance=f"metadata:{tool_name}",
    )


@pytest.mark.parametrize(
    "tool_name",
    sorted(
        name
        for name, entry in _playbook_tools().items()
        if isinstance(entry, dict) and not entry.get("blocked")
    ),
)
def test_non_blocked_playbook_tools_have_argument_templates(tool_name: str) -> None:
    template = argument_template_for_tool(tool_name)
    assert template is not None, tool_name
    entry = _playbook_tools()[tool_name]
    if entry.get("read_only") is True and tool_name not in {"splunk_run_query"}:
        # Metadata/discovery tools use {} or index placeholder templates.
        assert isinstance(template, dict)


@pytest.mark.parametrize(
    "tool_name",
    [
        "splunk_get_info",
        "splunk_get_indexes",
        "splunk_get_metadata",
        "splunk_get_index_info",
        "splunk_get_knowledge_objects",
        "splunk_get_user_info",
        "splunk_get_kv_store_collections",
    ],
)
def test_metadata_tool_envelopes_sanitize_and_validate_honestly(tool_name: str) -> None:
    envelope = sanitize_result_envelope(_metadata_envelope(tool_name))
    assert envelope.schema_confirmed is False
    assert envelope.schema_confirmed_reason == REAL_SCHEMA_UNVERIFIED
    verdict = validate_mcp_result_envelope(envelope)
    assert verdict["failure_mode"] in {"empty_result", "schema_mismatch"}
    assert verdict.get("negative_result") is True or verdict["failure_mode"] == "schema_mismatch"
