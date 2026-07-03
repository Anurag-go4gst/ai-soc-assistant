"""Budget profile sizing guards (item 1.5)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.llm.hybrid_role_graph import _MAX_TURN_DEADLINE
from app.planner.llm_plan_bridge import _BRIDGE_TIMEOUT_SECONDS_CAP

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BRIDGE_CAP = float(_BRIDGE_TIMEOUT_SECONDS_CAP)


def _parse_env_example(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


@pytest.mark.parametrize(
    "profile_name",
    ["development.env.example", "coe.env.example"],
)
def test_dev_profiles_allow_planner_plus_synthesis(profile_name: str) -> None:
    env = _parse_env_example(_REPO_ROOT / "env/profiles" / profile_name)
    turn_deadline = float(env["AI_SOC_LLM_TURN_DEADLINE_SECONDS"])
    hop_timeout = float(env["AI_SOC_LLM_TIMEOUT_SECONDS"])
    intent_reserve = float(env["AI_SOC_LLM_INTENT_ADVISOR_RESERVE_SECONDS"])
    guided_calls = int(env["AI_SOC_GUIDED_LLM_MAX_CALLS"])
    max_output = int(env["AI_SOC_LLM_MAX_OUTPUT_TOKENS"])

    assert guided_calls == 3
    assert max_output >= 512
    assert turn_deadline >= _BRIDGE_CAP + hop_timeout + intent_reserve
    assert turn_deadline + 50.0 <= _MAX_TURN_DEADLINE


def test_production_profile_has_high_throughput_budget_block() -> None:
    env = _parse_env_example(_REPO_ROOT / "env/profiles/production.env.example")
    assert int(env["AI_SOC_GUIDED_LLM_MAX_CALLS"]) >= 5
    assert float(env["AI_SOC_LLM_TURN_DEADLINE_SECONDS"]) <= 90.0
    assert float(env["AI_SOC_LLM_TIMEOUT_SECONDS"]) <= 30.0


def test_budget_model_doc_exists_and_references_profiles() -> None:
    doc = (_REPO_ROOT / "docs/architecture/llm_budget_model.md").read_text(encoding="utf-8")
    assert "AI_SOC_LLM_TURN_DEADLINE_SECONDS" in doc
    assert "skipped:budget" in doc
    assert re.search(r"development\.env\.example", doc)
