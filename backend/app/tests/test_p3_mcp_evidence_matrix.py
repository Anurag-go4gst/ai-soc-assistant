from __future__ import annotations

from app.orchestration.evidence_mcp_mapping import (
    DETECTION_REGISTRY_BINDING,
    LOCAL_LOOKUP_REGISTRY,
    SPLUNK_AUTH_EVIDENCE,
    SPLUNK_METADATA_DISCOVERY,
    map_evidence_need_to_mcp_tools,
)
from app.orchestration.mcp_evidence_matrix import (
    build_operation_mcp_evidence_matrix,
    build_question_mcp_evidence_report,
    mcp_evidence_needs_for_coverage,
)


def test_promoted_manifest_matrix_is_report_only_and_covers_10_rows() -> None:
    report = build_operation_mcp_evidence_matrix()
    assert report["schema_version"] == "p3_mcp_evidence_matrix_v1"
    assert report["authority"] == "report_only"
    assert report["mcp_called"] is False
    assert report["execution_authorized"] is False
    assert report["row_count"] == 10


def test_cov_q046_maps_to_metadata_and_gated_splunk_search() -> None:
    row = mcp_evidence_needs_for_coverage("cov.q046.excessive_failed_logins_sample")
    assert row is not None
    assert row["mcp_evidence_needs"] == [SPLUNK_METADATA_DISCOVERY, SPLUNK_AUTH_EVIDENCE]
    auth_mapping = next(
        item for item in row["mcp_tool_mappings"] if item["evidence_need"] == SPLUNK_AUTH_EVIDENCE
    )
    assert auth_mapping["selected_mcp_tools"] == []
    assert auth_mapping["gated_after_validation_tools"] == ["splunk_run_query"]
    assert auth_mapping["requires_spl_validation"] is True


def test_ioc_and_detection_rows_record_local_registry_needs_without_mcp_execution() -> None:
    report = build_question_mcp_evidence_report()
    q004 = next(row for row in report["rows"] if row["question_ref"] == "q0.q004")
    q007 = next(row for row in report["rows"] if row["question_ref"] == "q0.q007")

    assert LOCAL_LOOKUP_REGISTRY in q004["mcp_evidence_needs"]
    assert DETECTION_REGISTRY_BINDING in q007["mcp_evidence_needs"]
    for row in (q004, q007):
        assert row["mcp_called"] is False
        assert row["execution_authorized"] is False


def test_105_question_report_has_one_row_per_taxonomy_question() -> None:
    report = build_question_mcp_evidence_report()
    assert report["scope"] == "question_runtime_map_105"
    assert report["row_count"] == 105
    assert report["source_counts"]["promoted_manifest"] == 10
    assert report["source_counts"]["question_runtime_estimate"] == 95


def test_llm_tool_suggestions_do_not_populate_mcp_tool_outputs() -> None:
    mapping = map_evidence_need_to_mcp_tools(
        evidence_need=SPLUNK_METADATA_DISCOVERY,
        discovered_tools=["splunk_get_indexes", "splunk_get_metadata", "saia_generate_spl"],
        llm_suggested_tool_names=["saia_generate_spl"],
    )
    assert mapping["selected_mcp_tools"] == ["splunk_get_indexes", "splunk_get_metadata"]
    assert mapping["candidate_only_tools"] == []
    assert "llm_tool_suggestion_ignored:saia_generate_spl" in mapping["warnings"]
