"""T4.2 — composer/executor bind registry onboarding matrix."""

from __future__ import annotations

from app.chat.contracts.evidence_plan import EvidencePlan
from app.planner.composer import compose_resource_plan
from app.planner.executor import _blocked_step_ids, walk_plan_steps
from app.planner.resource_registry import ResourceRegistry


def _mcp_only_plan(**overrides) -> EvidencePlan:
    base = {
        "answer_mode": "live_investigation",
        "rag_phase": "post_mcp",
        "needs_rag": False,
        "needs_spl": False,
        "needs_mcp": True,
        "needs_mitre": False,
        "spl_allowed": True,
        "mcp_allowed": True,
        "policy_context_required": False,
        "policy_context_recommended": False,
    }
    base.update(overrides)
    return EvidencePlan(**base)


def test_declared_mcp_compose_not_onboarded() -> None:
    registry = ResourceRegistry.model_validate(
        {
            "schema_version": 2,
            "resources": [
                {
                    "resource_id": "mcp_tool:vendor_search",
                    "kind": "mcp_tool",
                    "capabilities": ["execute_validated_spl"],
                    "availability": "fixture_only",
                    "onboarding_status": "declared",
                    "policy_tier": 2,
                },
                {
                    "resource_id": "rag_corpus:soc_kb",
                    "kind": "rag_corpus",
                    "availability": "available",
                    "onboarding_status": "fixture_tested",
                },
            ],
        }
    )
    plan = compose_resource_plan(_mcp_only_plan(), registry=registry)
    mcp_steps = [s for s in plan.steps if s.purpose == "mcp_execution"]
    assert mcp_steps
    assert mcp_steps[0].status == "not_onboarded"


def test_fixture_tested_mcp_stays_planned_in_mock(monkeypatch) -> None:
    from app.config import settings
    from app.planner.resource_registry import clear_resource_registry_cache, load_resource_registry

    monkeypatch.setattr(settings, "mcp_mode", "mock")
    clear_resource_registry_cache()
    registry = load_resource_registry(reload=True)
    plan = compose_resource_plan(
        _mcp_only_plan(needs_spl=True),
        use_case_id="auth_failed_login_spike",
        registry=registry,
    )
    mcp = next(s for s in plan.steps if s.purpose == "mcp_execution")
    assert mcp.resource_id == "mcp_tool:splunk_run_query"
    assert mcp.status == "planned"


def test_not_onboarded_step_blocked_in_executor() -> None:
    state = {
        "evidence_plan": {
            "resource_plan": {
                "steps": [
                    {
                        "step_id": "mcp",
                        "resource_id": "mcp_tool:splunk_run_query",
                        "purpose": "mcp_execution",
                        "status": "not_onboarded",
                    }
                ]
            }
        }
    }
    blocked = _blocked_step_ids(state)
    assert "mcp" in blocked
    walk = walk_plan_steps(state)
    assert walk is not None
    assert walk.skipped_step_reasons["mcp"] == "resource_not_onboarded"
