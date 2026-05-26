from __future__ import annotations

from app.orchestration.evidence_mcp_mapping import map_evidence_need_to_mcp_tools


def test_metadata_discovery_maps_to_deterministic_splunk_metadata_tools() -> None:
    mapping = map_evidence_need_to_mcp_tools(
        evidence_need="splunk_metadata_discovery",
        discovered_tools=[
            {"name": "splunk_get_indexes"},
            {"name": "splunk_get_metadata"},
            {"name": "unknown_helper"},
        ],
        llm_suggested_tool_names=["splunk_run_query"],
    )

    assert mapping["selected_mcp_tools"] == ["splunk_get_indexes", "splunk_get_metadata"]
    assert mapping["gated_after_validation_tools"] == []
    assert mapping["candidate_only_tools"] == []
    assert "llm_tool_suggestion_ignored:splunk_run_query" in mapping["warnings"]
    assert "unknown_tool_ignored:unknown_helper" in mapping["warnings"]


def test_auth_evidence_uses_validator_path_and_only_gates_run_query_after_validation() -> None:
    mapping = map_evidence_need_to_mcp_tools(
        evidence_need="splunk_auth_evidence",
        discovered_tools=["splunk_run_query", "splunk_get_indexes"],
        llm_suggested_tool_names=["splunk_get_indexes"],
    )

    assert mapping["selected_mcp_tools"] == []
    assert mapping["validator_path"] == ["splunk_auth_evidence_template", "spl_validator"]
    assert mapping["requires_spl_validation"] is True
    assert mapping["gated_after_validation_tools"] == ["splunk_run_query"]
    assert "llm_tool_suggestion_ignored:splunk_get_indexes" in mapping["warnings"]


def test_saia_generate_spl_is_candidate_only_and_requires_validation() -> None:
    mapping = map_evidence_need_to_mcp_tools(
        evidence_need="saia_generate_spl",
        discovered_tools=["saia_generate_spl"],
        llm_suggested_tool_names=["saia_generate_spl"],
    )

    assert mapping["selected_mcp_tools"] == []
    assert mapping["gated_after_validation_tools"] == []
    assert mapping["candidate_only_tools"] == ["saia_generate_spl"]
    assert mapping["candidate_only"] is True
    assert mapping["requires_spl_validation"] is True
    assert "llm_tool_suggestion_ignored:saia_generate_spl" in mapping["warnings"]


def test_saved_search_suggestions_are_blocked_by_default() -> None:
    mapping = map_evidence_need_to_mcp_tools(
        evidence_need="splunk_auth_evidence",
        discovered_tools=["splunk_run_query", "splunk_run_saved_search"],
        llm_suggested_tool_names=["splunk_run_saved_search"],
    )

    assert mapping["selected_mcp_tools"] == []
    assert mapping["gated_after_validation_tools"] == ["splunk_run_query"]
    assert "splunk_run_saved_search" not in mapping["gated_after_validation_tools"]
    assert "saved_search_blocked_by_default:splunk_run_saved_search" in mapping["warnings"]


def test_unknown_evidence_need_and_unknown_llm_tools_are_ignored_with_warnings() -> None:
    mapping = map_evidence_need_to_mcp_tools(
        evidence_need="unknown_need",
        llm_suggested_tool_names=["totally_new_tool"],
    )

    assert mapping["selected_mcp_tools"] == []
    assert mapping["gated_after_validation_tools"] == []
    assert mapping["candidate_only_tools"] == []
    assert "unknown_evidence_need_ignored:unknown_need" in mapping["warnings"]
    assert "unknown_tool_ignored:totally_new_tool" in mapping["warnings"]
