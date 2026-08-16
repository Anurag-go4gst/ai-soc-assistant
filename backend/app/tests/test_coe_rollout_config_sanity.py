"""COE rollout config sanity — docs/profile alignment, safe code defaults."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"
_COE_PROFILE = _REPO_ROOT / "env" / "profiles" / "coe.env.example"
_COE_ROLLOUT_DOC = _REPO_ROOT / "docs" / "coe" / "COE_ROLLOUT_CONFIGURATION.md"
_COE_LIVE_TESTING_GUIDE = _REPO_ROOT / "docs" / "coe" / "COE_LIVE_TESTING_GUIDE.md"
_REAL_MCP_CONTRACT = _REPO_ROOT / "docs" / "architecture" / "real_splunk_mcp_safety_contract.md"

_RETIRED_ENV_KEYS = (
    "CONTROL_PLANE_ENABLED",
    "AI_SOC_CANONICAL_PLANNING_ENABLED",
    "AI_SOC_HANDOFF_STORE_BACKEND",
    "AI_SOC_HANDOFF_STORE_FILE_DIR",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        values[key.strip()] = raw.strip()
    return values


def test_code_defaults_keep_execution_and_split_routing_off(monkeypatch) -> None:
    for key in (
        "MCP_GLOBAL_EXECUTION_ENABLED",
        "MCP_SERVER_MOCK_EXECUTION_ENABLED",
        "AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED",
        "AI_SOC_RUNTIME_ENRICHMENT_ENABLED",
        "AI_SOC_ANSWER_GUARD_LAB_ENABLED",
        "AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED",
        "AI_SOC_SESSION_STORE_BACKEND",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.mcp_global_execution_enabled is False
    assert settings.mcp_server_mock_execution_enabled is False
    assert settings.ai_soc_pipeline_split_routing_nodes_enabled is False
    assert settings.ai_soc_runtime_enrichment_enabled is False
    assert settings.ai_soc_answer_guard_lab_enabled is False
    assert settings.ai_soc_guided_hybrid_investigation_enabled is False
    assert settings.ai_soc_session_store_backend == "memory"


def test_retired_env_keys_absent_from_rollout_profiles() -> None:
    for path in (
        _ENV_EXAMPLE,
        _COE_PROFILE,
        _REPO_ROOT / "env" / "profiles" / "development.env.example",
        _REPO_ROOT / "env" / "profiles" / "production.env.example",
    ):
        env = _parse_env_file(path)
        for key in _RETIRED_ENV_KEYS:
            assert key not in env, f"{key} must be removed from {path.name}"


def test_env_example_keeps_dangerous_flags_off() -> None:
    env = _parse_env_file(_ENV_EXAMPLE)
    assert env.get("MCP_GLOBAL_EXECUTION_ENABLED", "").lower() == "false"
    assert env.get("MCP_SERVER_MOCK_EXECUTION_ENABLED", "").lower() == "false"
    assert env.get("AI_SOC_RUNTIME_ENRICHMENT_ENABLED", "").lower() == "false"
    assert env.get("AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED", "").lower() == "false"
    assert env.get("AI_SOC_ANSWER_GUARD_LAB_ENABLED", "").lower() == "false"
    assert env.get("AI_SOC_SESSION_STORE_BACKEND", "memory").lower() == "memory"


def test_coe_profile_enables_safe_rollout_flags() -> None:
    env = _parse_env_file(_COE_PROFILE)
    assert env.get("AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_RUNTIME_ENRICHMENT_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_ANSWER_GUARD_LAB_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_SESSION_STORE_BACKEND", "").lower() == "file"
    assert env.get("AI_SOC_SESSION_STORE_FILE_DIR", "")
    assert env.get("AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED", "").lower() == "false"
    assert env.get("AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_LLM_ANSWER_GUARD_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_PIPELINE_DISPATCH_V2_ENABLED", "").lower() == "false"
    assert env.get("AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED", "").lower() == "true"
    assert "AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS" not in env


def test_coe_profile_keeps_live_splunk_execution_off() -> None:
    """COE now mirrors development's bounded MOCK execution posture (2026-07
    directive: MCP eligibility on all tiers) — global/mock execution flags are
    on, matching development.env.example. The real "live execution" boundary
    is MCP_MODE: only MCP_MODE=registry + operator-supplied SPLUNK_MCP_* creds
    route to a live Splunk connector (see CLAUDE.md Gotchas); mock mode cannot
    reach live Splunk regardless of the execution flags above."""
    env = _parse_env_file(_COE_PROFILE)
    assert env.get("MCP_MODE", "mock").lower() == "mock"
    assert env.get("MCP_GLOBAL_EXECUTION_ENABLED", "").lower() == "true"
    assert env.get("MCP_SERVER_MOCK_EXECUTION_ENABLED", "").lower() == "true"


def test_coe_profile_live_synthesis_flags_are_documented() -> None:
    rollout = _COE_ROLLOUT_DOC.read_text(encoding="utf-8")
    live_testing = _COE_LIVE_TESTING_GUIDE.read_text(encoding="utf-8")
    for flag in (
        "AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED",
        "AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED",
        "AI_SOC_LLM_ANSWER_GUARD_ENABLED",
    ):
        assert flag in rollout
    assert "AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true" in live_testing
    assert "AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true" in live_testing


def test_rollout_docs_match_live_mcp_adapter_status() -> None:
    for path in (_COE_LIVE_TESTING_GUIDE, _REAL_MCP_CONTRACT):
        text = path.read_text(encoding="utf-8")
        assert "splunk_mcp.py` is a placeholder" not in text
        assert "real_mcp_adapter_not_implemented" not in text
        assert "live `splunk_run_query` adapter" in text or "live search adapter is implemented" in text
