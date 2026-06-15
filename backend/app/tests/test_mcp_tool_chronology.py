from __future__ import annotations

from app.connectors.mcp.mcp_tool_chronology import (
    deterministic_default_chronology,
    load_playbook,
    review_proposed_tool_chronology,
)


def test_playbook_blocks_saia_and_user_list_but_enables_user_info() -> None:
    tools = load_playbook()["tools"]
    assert tools["splunk_get_user_info"]["blocked"] is False
    assert tools["splunk_get_user_info"]["rbac_gated"] is True
    assert tools["splunk_get_user_list"]["blocked"] is True
    for saia in ("saia_generate_spl", "saia_optimize_spl", "saia_explain_spl", "saia_ask_splunk_question"):
        assert tools[saia]["blocked"] is True


def test_default_chronology_prunes_index_info_and_search() -> None:
    # No target index, SPL not yet approved.
    seq = deterministic_default_chronology(target_index=None, spl_approved=False)
    assert seq == [
        "splunk_get_info",
        "splunk_get_indexes",
        "splunk_get_metadata",
        "splunk_get_knowledge_objects",
    ]
    assert "splunk_get_index_info" not in seq
    assert "splunk_run_query" not in seq


def test_default_chronology_includes_search_and_index_info_when_ready() -> None:
    seq = deterministic_default_chronology(target_index="pgcil_soc", spl_approved=True)
    assert seq[0] == "splunk_get_info"
    assert "splunk_get_index_info" in seq
    assert seq[-1] == "splunk_run_query"


def test_no_proposal_uses_deterministic_default() -> None:
    plan = review_proposed_tool_chronology(None, target_index="pgcil_soc", spl_approved=True)
    assert plan.decision_source == "deterministic_default"
    assert plan.approved_tools[-1] == "splunk_run_query"


def test_llm_proposal_reordered_to_canonical_order() -> None:
    # LLM proposes a valid-but-scrambled order; deterministic review reorders it.
    plan = review_proposed_tool_chronology(
        ["splunk_run_query", "splunk_get_metadata", "splunk_get_indexes", "splunk_get_info"],
        target_index="pgcil_soc",
        spl_approved=True,
    )
    assert plan.approved_tools == [
        "splunk_get_info",
        "splunk_get_indexes",
        "splunk_get_metadata",
        "splunk_run_query",
    ]
    assert plan.decision_source == "llm_reviewed_adjusted"


def test_llm_proposal_blocked_and_unknown_tools_dropped() -> None:
    plan = review_proposed_tool_chronology(
        ["splunk_get_indexes", "saia_generate_spl", "splunk_get_user_list", "wazuh_magic"],
        spl_approved=False,
    )
    dropped = {d.tool: d.reason for d in plan.dropped}
    assert dropped["saia_generate_spl"] == "saia_conditional_blocked"
    assert dropped["splunk_get_user_list"] == "admin_or_sensitive_tool"
    assert dropped["wazuh_magic"] == "unknown_tool"
    assert plan.approved_tools == ["splunk_get_indexes"]


def test_run_query_dropped_when_spl_not_approved() -> None:
    plan = review_proposed_tool_chronology(
        ["splunk_get_indexes", "splunk_run_query"],
        spl_approved=False,
    )
    assert "splunk_run_query" not in plan.approved_tools
    assert any(d.reason == "approved_normalized_spl_missing" for d in plan.dropped)


def test_rbac_role_gates_user_info_and_search() -> None:
    # viewer may not run searches or read identity per the playbook roles.
    plan = review_proposed_tool_chronology(
        ["splunk_get_indexes", "splunk_get_user_info", "splunk_run_query"],
        spl_approved=True,
        rbac_role="viewer",
    )
    dropped = {d.tool: d.reason for d in plan.dropped}
    assert dropped["splunk_get_user_info"] == "rbac_denied:viewer:splunk_get_user_info"
    assert dropped["splunk_run_query"] == "rbac_denied:viewer:splunk_run_query"
    assert plan.approved_tools == ["splunk_get_indexes"]


def test_all_rejected_falls_back_to_deterministic() -> None:
    plan = review_proposed_tool_chronology(
        ["saia_generate_spl", "splunk_get_user_list"],
        target_index="pgcil_soc",
        spl_approved=True,
    )
    assert plan.decision_source == "deterministic_fallback"
    assert plan.approved_tools[0] == "splunk_get_info"
    assert "llm_proposal_empty_after_review_fell_back_to_deterministic" in plan.warnings
