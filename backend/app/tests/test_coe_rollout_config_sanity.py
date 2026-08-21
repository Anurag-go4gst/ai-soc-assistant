"""COE rollout config sanity — docs/profile alignment, safe code defaults."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"
_COE_PROFILE = _REPO_ROOT / "env" / "profiles" / "coe.env.example"
_COE_ROLLOUT_DOC = _REPO_ROOT / "docs" / "coe" / "COE_ROLLOUT_CONFIGURATION.md"
_COE_LIVE_TESTING_GUIDE = _REPO_ROOT / "docs" / "coe" / "COE_LIVE_TESTING_GUIDE.md"
_COE_PRODUCTION_READINESS = _REPO_ROOT / "docs" / "coe" / "COE_PRODUCTION_READINESS_RUNBOOK.md"
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
    assert env.get("AI_SOC_INVESTIGATION_PLAN_BEFORE_RESOURCE_PLAN_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_CAPABILITY_SNAPSHOT_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_GUIDED_COMPOSABLE_PLANNING_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_INVESTIGATION_PLANNER_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_PLAN_DELTA_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_INVESTIGATION_OUTCOME_V2_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_REMEDIATION_PLANNER_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_ACTION_EMAIL_ENABLED", "").lower() == "true"
    assert env.get("AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED", "").lower() == "true"
    assert "AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS" not in env


def test_coe_profile_keeps_live_splunk_execution_off() -> None:
    """COE ships live-ready registry mode. The only operational go-live switch
    is MCP_GLOBAL_EXECUTION_ENABLED=false. Per-server Splunk execution is
    pre-armed so operators do not flip a second flag; effective execution is
    AND'd with the global switch. Secrets stay empty in git."""
    env = _parse_env_file(_COE_PROFILE)
    assert env.get("MCP_MODE", "mock").lower() == "registry"
    assert env.get("MCP_GLOBAL_EXECUTION_ENABLED", "").lower() == "false"
    assert env.get("MCP_SERVER_MOCK_EXECUTION_ENABLED", "").lower() == "false"
    assert env.get("MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED", "").lower() == "true"
    assert env.get("SPLUNK_MCP_BASE_URL", "") == ""
    assert env.get("SPLUNK_MCP_TOKEN", "") == ""


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


def test_production_readiness_runbook_is_executable_and_no_go() -> None:
    text = _COE_PRODUCTION_READINESS.read_text(encoding="utf-8")
    assert "PRODUCTION_GO_RECOMMENDATION = NO_GO" in text
    assert "eval_t4_coe_qualification.py --live" in text
    assert "eval_splunk_mcp_coe_qualification.py --check" in text
    assert "AI_SOC_COE_LIVE_MCP_QUALIFICATION=1" in text
    assert "LIVE_MCP_CONFIGURED" in text
    assert "LIVE_MCP_EXECUTION" in text
    assert "MCP_GLOBAL_EXECUTION_ENABLED=true" in text
    assert "AUTH0" in text
    assert "Never** roll back by setting `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true`" in text or (
        "Never** roll back by setting" in text and "AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true" in text
    )
    for rel in (
        "scripts/coe_preflight.sh",
        "scripts/coe_deploy_verify.sh",
        "scripts/eval_t4_coe_qualification.py",
        "scripts/eval_splunk_mcp_coe_qualification.py",
        "scripts/select_env_profile.sh",
        "docs/evals/plan7/rollback_runbook.md",
        "env/profiles/coe.env.example",
    ):
        assert (_REPO_ROOT / rel).is_file(), rel
        assert rel.split("/")[-1] in text or rel in text
