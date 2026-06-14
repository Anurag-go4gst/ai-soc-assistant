"""Phase 2.5: skill metadata + MCP tool hints in the governed context package."""

from __future__ import annotations

from app.chat.contracts.answer_contract import AnswerContract
from app.llm.governed_context_package import build_governed_context_package_for_contract


def test_skill_and_mcp_hints_rendered() -> None:
    pkg = build_governed_context_package_for_contract(
        query="hunt for unusual smb lateral movement",
        contract=AnswerContract(missing_evidence=["asset_context"], hil_status="not_required"),
        skill_sections=[
            "lateral_movement: checklist — enumerate SMB sessions, group by src/dest",
        ],
        mcp_tool_hints=[
            "search_splunk: run a bounded SPL search and return rows (HIL-gated)",
        ],
    )
    block = pkg.to_prompt_block()
    assert "lateral_movement" in block
    assert "search_splunk" in block
    assert "skill_sections" in block
    assert "mcp_tool_hints" in block


def test_mcp_hints_carry_no_execution_schema() -> None:
    # Caller contract: hints are capability lines only. Builder must not synthesize
    # parameters/credentials — it only echoes what it is given.
    pkg = build_governed_context_package_for_contract(
        query="q",
        contract=AnswerContract(missing_evidence=["x"], hil_status="not_required"),
        mcp_tool_hints=["search_splunk: bounded search (HIL-gated)"],
    )
    block = pkg.to_prompt_block().lower()
    assert "token" not in block
    assert "api_key" not in block
    assert "earliest_time" not in block  # no parameter schema leaked
