"""MCP posture projection normalization for RunContract dump enrichment."""

from __future__ import annotations

from app.chat.run_contract_builder import project_mcp_posture


def test_project_mcp_posture_normalizes_execution_status_without_composed_step() -> None:
    posture = project_mcp_posture(
        {
            "execution": {
                "status": "requires_human_review",
                "block_reason": "spl_validation_failed",
            }
        }
    )
    assert posture is not None
    assert posture["status"] == "blocked_policy"
    assert posture["primary_reason"] == "spl_validation_failed"
    assert posture["execution_authorized"] is False
