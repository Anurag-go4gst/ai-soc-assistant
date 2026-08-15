"""P0.2 — Plan 6 env-capture schema must fail closed on secret-shaped keys."""

from __future__ import annotations

from app.evals.plan6_env_capture import (
    FORBIDDEN_KEY_RE,
    SCHEMA_PATH,
    load_schema,
    validate_env_capture,
)


def _valid_capture() -> dict:
    return {
        "git_sha": "1d32ac66dd6c707789db8b44574bd566af401952",
        "flags": {
            "AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED": False,
            "AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED": False,
            "AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED": False,
            "AI_SOC_PIPELINE_DISPATCH_V2_ENABLED": True,
        },
        "model_endpoint_host": "127.0.0.1",
        "model_role": "instruct",
        "db_reachable": True,
        "mcp_mode": "mock",
        "mcp_connectivity": True,
        "environment_identity": "coe-vps",
        "test_account_role": "demo_analyst",
        "timestamp": "2026-08-13T00:00:00Z",
        "corpus_version": "vps_corpus_v1",
    }


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.is_file()
    schema = load_schema()
    assert schema["title"]
    assert "git_sha" in schema["required"]


def test_valid_capture_is_accepted() -> None:
    assert validate_env_capture(_valid_capture()) == []


def test_forbidden_key_regex_matches_plan_words() -> None:
    for word in ("token", "password", "secret", "api_key", "API_KEY", "splunk_token"):
        assert FORBIDDEN_KEY_RE.search(word), word


def test_token_key_is_rejected() -> None:
    payload = _valid_capture()
    payload["splunk_token"] = "should-never-land"
    errors = validate_env_capture(payload)
    assert errors
    assert "splunk_token" in errors[0]


def test_nested_password_key_is_rejected() -> None:
    payload = _valid_capture()
    payload["flags"] = dict(payload["flags"])
    payload["flags"]["APP_AUTH_PASSWORD"] = "nope"
    errors = validate_env_capture(payload)
    assert errors
    assert "APP_AUTH_PASSWORD" in errors[0]


def test_secret_and_api_key_keys_are_rejected() -> None:
    for bad in ("session_secret", "openai_api_key"):
        payload = _valid_capture()
        payload[bad] = "nope"
        errors = validate_env_capture(payload)
        assert errors, bad
        assert bad in errors[0]
