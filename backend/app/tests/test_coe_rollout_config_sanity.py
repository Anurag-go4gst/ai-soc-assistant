"""COE rollout config sanity — docs/profile alignment, safe code defaults."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"
_COE_PROFILE = _REPO_ROOT / "env" / "profiles" / "coe.env.example"


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


def test_code_defaults_keep_execution_and_split_routing_off() -> None:
    settings = Settings()
    assert settings.mcp_global_execution_enabled is False
    assert settings.mcp_server_mock_execution_enabled is False
    assert settings.ai_soc_pipeline_split_routing_nodes_enabled is False
    assert settings.ai_soc_runtime_enrichment_enabled is False
    assert settings.ai_soc_answer_guard_lab_enabled is False
    assert settings.control_plane_enabled is False
    assert settings.ai_soc_guided_hybrid_investigation_enabled is False
    assert settings.ai_soc_session_store_backend == "memory"


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
    assert env.get("CONTROL_PLANE_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_RUNTIME_ENRICHMENT_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_ANSWER_GUARD_LAB_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_SESSION_STORE_BACKEND", "").lower() == "file"
    assert env.get("AI_SOC_SESSION_STORE_FILE_DIR", "")
    assert env.get("AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED", "").lower() == "false"


def test_coe_profile_keeps_live_mcp_execution_off() -> None:
    env = _parse_env_file(_COE_PROFILE)
    assert env.get("MCP_GLOBAL_EXECUTION_ENABLED", "").lower() == "false"
    assert env.get("MCP_SERVER_MOCK_EXECUTION_ENABLED", "").lower() == "false"
    assert env.get("MCP_MODE", "mock").lower() == "mock"
