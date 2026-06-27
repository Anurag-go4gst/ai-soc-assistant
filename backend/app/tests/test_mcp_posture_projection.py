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

def test_project_mcp_posture_prefers_skill_contract_metadata() -> None:
    posture = project_mcp_posture(
        {
            "evidence_plan": {
                "resource_plan": {
                    "steps": [
                        {
                            "step_id": "mcp",
                            "purpose": "mcp_execution",
                            "status": "blocked_policy",
                            "status_reason": "skill_contract",
                            "policy_checks": ["blocked_by_skill_contract"],
                            "mcp_step_metadata": {
                                "status": "blocked_policy",
                                "primary_reason": "skill_contract",
                                "secondary_reasons": [
                                    "mcp_global_execution_disabled",
                                    "skill_contract",
                                ],
                                "execution_authorized": False,
                            },
                        }
                    ]
                }
            },
            "execution": {
                "status": "blocked",
                "block_reason": "mcp_global_execution_disabled",
            },
        }
    )
    assert posture is not None
    assert posture["primary_reason"] == "skill_contract"
    assert posture["execution_authorized"] is False

