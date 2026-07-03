"""Validate startup config rejects unsupported telemetry sinks."""

import pytest

from app.config import ConfigError, Settings, _validate


def _make(sink: str) -> Settings:
    return Settings(ai_soc_telemetry_sink=sink)


def test_db_sink_is_accepted() -> None:
    s = _validate(_make("db"))
    assert s.ai_soc_telemetry_sink == "db"


def test_none_sink_is_accepted() -> None:
    s = _validate(_make("none"))
    assert s.ai_soc_telemetry_sink == "none"


def test_splunk_sink_is_rejected_with_clear_error() -> None:
    with pytest.raises(ConfigError) as exc:
        _validate(_make("splunk"))
    assert "not implemented" in str(exc.value).lower()


def test_both_sink_is_rejected() -> None:
    with pytest.raises(ConfigError):
        _validate(_make("both"))


def test_unknown_sink_is_rejected() -> None:
    with pytest.raises(ConfigError):
        _validate(_make("kafka"))


def test_stage3h_enum_values_are_accepted() -> None:
    for environment in ("coe", "customer_test", "production", "air_gapped"):
        for assistant_mode in ("auto", "enabled", "disabled"):
            for discovery_mode in ("dynamic", "restricted", "static_only"):
                settings = Settings(
                    ai_soc_telemetry_sink="db",
                    ai_soc_environment_mode=environment,
                    splunk_ai_assistant_mode=assistant_mode,
                    splunk_mcp_discovery_mode=discovery_mode,
                )
                assert _validate(settings) is settings


def test_invalid_stage3h_enum_values_are_rejected() -> None:
    with pytest.raises(ConfigError):
        _validate(Settings(ai_soc_telemetry_sink="db", ai_soc_environment_mode="lab"))
    with pytest.raises(ConfigError):
        _validate(Settings(ai_soc_telemetry_sink="db", splunk_ai_assistant_mode="maybe"))
    with pytest.raises(ConfigError):
        _validate(Settings(ai_soc_telemetry_sink="db", splunk_mcp_discovery_mode="open"))


def test_cors_allowed_origins_default_parses() -> None:
    from app.config import parse_cors_allowed_origins

    origins = parse_cors_allowed_origins("http://localhost:3010,http://127.0.0.1:3010")
    assert origins == ["http://localhost:3010", "http://127.0.0.1:3010"]


def test_cors_allowed_origins_rejects_empty() -> None:
    from app.config import parse_cors_allowed_origins

    with pytest.raises(ConfigError):
        parse_cors_allowed_origins(" , ")
