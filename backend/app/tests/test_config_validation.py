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
