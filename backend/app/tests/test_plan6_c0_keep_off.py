"""Plan 6 C0/C1 — ResourcePlan execution KEEP OFF; CHANGE_LADDER not selected.

C0 recorded KEEP OFF. C1 must pin the repo default false and must not rewrite
the dispatch-v2 ladder. Live capability enforcement stays OFF. T4 default/timeout
pins live in test_semantic_t4_understanding.py (D4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings, settings
from app.planner import executor
from app.tests.test_phase_merge_activation import _state

_REPO = Path(__file__).resolve().parents[3]
_CONFIG_PY = Path(__file__).resolve().parents[1] / "config.py"
_PROFILE = _REPO / "docs" / "evals" / "plan6" / "production_flag_profile.md"
_STOP = _REPO / "docs" / "evals" / "plan6" / "c0_d3_stop_decisions.md"


def test_c0_keep_off_is_recorded() -> None:
    stop = _STOP.read_text(encoding="utf-8")
    assert "P6_RESOURCE_PLAN_EXECUTION_ACTIVATION" in stop
    assert "**KEEP OFF**" in stop
    assert "N/A" in stop
    assert "CHANGE_LADDER" in stop
    assert "Do not self-select" in stop or "not selected" in stop.lower()
    profile = _PROFILE.read_text(encoding="utf-8")
    assert "KEEP OFF" in profile
    assert "CHANGE_LADDER" in profile
    assert "was **not** selected" in profile
    assert "AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED" in profile
    assert "**OFF**" in profile


def test_config_py_execution_default_stays_false() -> None:
    text = _CONFIG_PY.read_text(encoding="utf-8")
    assert "ai_soc_resource_plan_execution_enabled: bool = False" in text
    assert Settings().ai_soc_resource_plan_execution_enabled is False


def test_live_capability_enforcement_stays_false() -> None:
    text = _CONFIG_PY.read_text(encoding="utf-8")
    assert "ai_soc_live_capability_enforcement_enabled: bool = False" in text
    assert Settings().ai_soc_live_capability_enforcement_enabled is False


def test_flags_remain_independently_controllable() -> None:
    fields = Settings.model_fields
    names = (
        "ai_soc_resource_plan_execution_enabled",
        "ai_soc_pipeline_dispatch_v2_enabled",
        "ai_soc_t4_semantic_understanding_enabled",
        "ai_soc_t4_semantic_understanding_timeout_seconds",
        "ai_soc_live_capability_enforcement_enabled",
    )
    for name in names:
        assert name in fields, name
    assert fields["ai_soc_resource_plan_execution_enabled"].default is False
    assert fields["ai_soc_pipeline_dispatch_v2_enabled"].default is False
    assert fields["ai_soc_t4_semantic_understanding_enabled"].default is False
    assert fields["ai_soc_t4_semantic_understanding_timeout_seconds"].default == 2.0
    assert fields["ai_soc_live_capability_enforcement_enabled"].default is False


def test_plan7_explicit_direction_supersedes_plan6_ladder_without_rewriting_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan 6 recorded KEEP OFF; Plan 7 later authorized ResourcePlan precedence."""
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    monkeypatch.setattr(
        "app.planner.executor.imperative_hook_schedule_from_state",
        lambda _state: ["workflow_spl", "execution"],
    )
    state = _state()
    compiled, reason, merge_trace = executor._execution_driven_schedule_detailed(
        state, executor.walk_plan_steps(state)
    )
    assert reason is None
    assert compiled == ["workflow_spl", "spl_postprocessor", "spl_source_resolve", "execution"]
    assert merge_trace is not None


def test_coe_profile_follows_plan7_authority_not_the_plan6_seed() -> None:
    """Plan 6 seeded COE with dispatch-v2; `1c6c247` realigned it to Plan 7/8.

    The original assertion (dispatch-v2 on, ResourcePlan/T4 absent) described the
    seed at Plan 6 closure. `1c6c247 ops: align COE authority profile` moved COE
    onto ResourcePlan authority deliberately, and Plan 7 made that the sole normal
    scheduler. Superseded like the ladder test above: the Plan 6 record stays
    intact in the decision docs and repo defaults (pinned by the tests above),
    while the deployed profile follows current authority.
    """
    text = (_REPO / "env" / "profiles" / "coe.env.example").read_text(encoding="utf-8")
    assert "AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=false" in text
    assert "AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true" in text
