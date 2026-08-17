"""Real MCP tools/list descriptor parsing.

All parsed fields (name/description/inputSchema/annotations) are UNTRUSTED
discovery metadata — this module only proves the parser tolerates real and
malformed server shapes without raising or leaking secrets. Local authority
(classify_mcp_tool, TOOL_ALLOWLIST) decides what is approved, never this
parser.
"""

from __future__ import annotations

from app.connectors.mcp.splunk_mcp import (
    _tool_descriptors_from_list_result,
    _tool_names_from_list_result,
)


def test_complete_descriptor_parsed() -> None:
    result = {
        "tools": [
            {
                "name": "splunk_run_query",
                "description": "Run a bounded SPL search.",
                "inputSchema": {"type": "object", "properties": {"search_query": {"type": "string"}}, "required": ["search_query"]},
                "annotations": {"readOnlyHint": False},
            }
        ]
    }
    descriptors = _tool_descriptors_from_list_result(result)
    assert descriptors == [
        {
            "name": "splunk_run_query",
            "description": "Run a bounded SPL search.",
            "input_schema": {"type": "object", "properties": {"search_query": {"type": "string"}}, "required": ["search_query"]},
            "input_schema_malformed": False,
            "annotations": {"readOnlyHint": False},
        }
    ]


def test_missing_description_defaults_empty() -> None:
    descriptors = _tool_descriptors_from_list_result({"tools": [{"name": "splunk_get_indexes"}]})
    assert descriptors[0]["description"] == ""


def test_missing_input_schema_defaults_empty_dict() -> None:
    descriptors = _tool_descriptors_from_list_result({"tools": [{"name": "splunk_get_indexes"}]})
    assert descriptors[0]["input_schema"] == {}
    assert descriptors[0]["input_schema_malformed"] is False


def test_malformed_input_schema_flagged_not_raised() -> None:
    descriptors = _tool_descriptors_from_list_result({"tools": [{"name": "splunk_get_indexes", "inputSchema": "not-a-schema"}]})
    assert descriptors[0]["input_schema"] == {}
    assert descriptors[0]["input_schema_malformed"] is True


def test_unexpected_annotations_tolerated() -> None:
    descriptors = _tool_descriptors_from_list_result(
        {"tools": [{"name": "splunk_get_metadata", "annotations": {"somethingUnknown": True, "nested": {"a": 1}}}]}
    )
    assert descriptors[0]["annotations"] == {"somethingUnknown": True, "nested": {"a": 1}}


def test_extra_unknown_tool_parsed_but_carries_no_local_authority() -> None:
    descriptors = _tool_descriptors_from_list_result({"tools": [{"name": "totally_unknown_vendor_tool"}]})
    assert descriptors[0]["name"] == "totally_unknown_vendor_tool"
    # Parsing succeeds; local approval is decided elsewhere (classify_mcp_tool),
    # never by this parser.


def test_write_admin_looking_tool_name_parsed_verbatim() -> None:
    descriptors = _tool_descriptors_from_list_result({"tools": [{"name": "splunk_admin_delete_index"}]})
    assert descriptors[0]["name"] == "splunk_admin_delete_index"


def test_duplicate_names_collapse_to_first_occurrence() -> None:
    descriptors = _tool_descriptors_from_list_result(
        {
            "tools": [
                {"name": "splunk_get_indexes", "description": "first"},
                {"name": "splunk_get_indexes", "description": "second"},
            ]
        }
    )
    assert len(descriptors) == 1
    assert descriptors[0]["description"] == "first"


def test_malformed_tools_list_response_fails_safely() -> None:
    assert _tool_descriptors_from_list_result(None) == []
    assert _tool_descriptors_from_list_result({}) == []
    assert _tool_descriptors_from_list_result({"tools": "not-a-list"}) == []
    assert _tool_descriptors_from_list_result({"tools": [1, 2, None, {}, {"name": ""}]}) == []
    assert _tool_names_from_list_result("not-a-dict") == []


def test_description_redaction_applies_same_as_local_safe_text() -> None:
    result = {"tools": [{"name": "x", "description": "call with Bearer abc123secrettoken"}]}
    descriptors = _tool_descriptors_from_list_result(result)
    assert "abc123secrettoken" not in descriptors[0]["description"]
    assert "[redacted]" in descriptors[0]["description"]


def test_string_only_tool_entry_still_parses() -> None:
    descriptors = _tool_descriptors_from_list_result({"tools": ["splunk_get_info"]})
    assert descriptors == [
        {"name": "splunk_get_info", "description": "", "input_schema": {}, "input_schema_malformed": False, "annotations": {}}
    ]
