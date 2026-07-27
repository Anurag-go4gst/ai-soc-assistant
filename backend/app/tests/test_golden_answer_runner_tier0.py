from __future__ import annotations

from app.evals.golden_answer_runner import SAFE_ENV_DEFAULTS
from app.evals.golden_answer_runner import discover_case_files
from app.evals.golden_answers.schema import load_jsonl_cases


def test_tier0_fixture_has_shared_control_plane_flow_refs() -> None:
    case_files = discover_case_files(tier=0)
    cases = load_jsonl_cases(case_files)

    assert len(cases) == 7
    assert len({case.case_id for case in cases}) == 7
    assert all(case.tier == 0 for case in cases)
    assert all(case.source_refs for case in cases)
    assert all("test_chat_control_plane_golden.py::" in case.source_refs[0] for case in cases)
    assert "CONTROL_PLANE_ENABLED" not in SAFE_ENV_DEFAULTS
    assert SAFE_ENV_DEFAULTS["MCP_GLOBAL_EXECUTION_ENABLED"] == "false"
    assert SAFE_ENV_DEFAULTS["AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED"] == "false"
