"""OPTIONAL_PHASE_S S5 — generation-prompt efficiency guidance."""

from __future__ import annotations

from app.spl.llm_fallback import (
    _spl_efficiency_guidance_block,
    set_spl_efficiency_prompt_enabled,
    spl_advisory_prompts,
)


def test_efficiency_block_contains_plan_rules() -> None:
    block = _spl_efficiency_guidance_block()
    assert "never sacrifice correctness" in block.lower()
    assert "TERM()" in block
    assert "IN (" in block or "IN(" in block


def test_system_prompt_includes_efficiency_when_enabled() -> None:
    set_spl_efficiency_prompt_enabled(True)
    system, _ = spl_advisory_prompts("failed logins by src_ip", correctness_mode=True)
    assert "Efficiency guidance" in system


def test_system_prompt_omits_efficiency_when_disabled() -> None:
    set_spl_efficiency_prompt_enabled(False)
    system, _ = spl_advisory_prompts("failed logins by src_ip", correctness_mode=True)
    assert "Efficiency guidance" not in system
    set_spl_efficiency_prompt_enabled(True)
