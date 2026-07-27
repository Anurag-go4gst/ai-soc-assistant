"""Item 2.3 — T2 SPL producer boundary, scoped narrow (recorded in plan Drift log).

The plan's original Do text asked the T2 lab-tier LLM plan-compiler
(`generate_llm_spl_via_plan`, `backend/app/spl/llm_plan_compiler.py`) to
"produce an approved normalized_spl artifact" feeding item 2.1's MCP-eligibility
grant. That directly contradicts a documented, independently-pinned governance
invariant (CLAUDE.md: "Lab-tier LLM SPL always approved=false/normalized_spl=
null"; `test_t2_governed_producer.py::test_producer_output_is_governed_review_
only`; `test_llm_plan_compiler.py::test_plan_path_reaches_lab_tier`). Opening
that path is a real safety-posture decision (free-form LLM-authored SPL, not
template-matched), not a wiring gap — user did not confirm before the
autonomous-execution timeout, so this item stays on the conservative default:
lab-tier SPL remains permanently non-executable, no invariant touched.

Governed-template-family SPL (the plan's OTHER named source) already feeds
item 2.1's lane with no code change needed: template-matched SPL already
gets real `approved=True`/`normalized_spl` when valid (proven in item 2.1's
own test — the AWS-security-group query, `deterministic_template_render`,
reaches `approved=True`). This file adds the one thing 2.3 can honestly close:
an explicit end-to-end proof that evidence-plan MCP eligibility (2.1) and
SPL-level approval are independent gates — eligibility alone never lets a
lab-tier candidate execute.
"""

from __future__ import annotations

import json

import pytest

from app.config import settings
from app.spl.llm_plan_compiler import generate_llm_spl_via_plan

_PLAN = {
    "detection_family": "ot_modbus_unauthorized_write",
    "data_domain": "ot_network",
    "time_window_hours": 24,
    "filters": [{"field": "protocol", "match": "modbus"}],
    "group_by": ["src_ip", "dest_ip"],
    "metric": "count",
    "assumptions": ["<ot_network_index> is the OT network telemetry source"],
    "required_fields": ["src_ip", "dest_ip", "protocol"],
}


@pytest.fixture
def _llm_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")


def test_lab_tier_stays_non_executable_even_with_mcp_eligibility_on(
    _llm_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MCP eligibility (item 2.1) is a plan-time, family-level flag; SPL approval
    is decided entirely by the validator downstream. Turning the former on must
    never influence the latter for a lab-tier producer."""

    result = generate_llm_spl_via_plan(
        user_query="Detect Modbus writes to PLCs from unapproved hosts",
        plan_raw_output_provider=lambda: json.dumps(_PLAN),
    )

    assert result is not None
    assert result.lab_tier is True
    assert result.validation.get("approved") is False
    assert result.validation.get("normalized_spl") is None
    assert result.validation.get("execution_eligible") in (False, None)
