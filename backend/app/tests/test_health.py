from app.api.routes_health import health


def test_health_returns_ok_status() -> None:
    payload = health()
    assert payload["status"] == "ok"
    assert payload["service"] == "ai-soc-assistant-backend"


def test_health_exposes_telemetry_counter() -> None:
    payload = health()
    assert "telemetry" in payload
    assert isinstance(payload["telemetry"]["write_failures"], int)


def test_health_does_not_leak_payloads() -> None:
    payload = health()
    # Counter values are integers only; no payload content should appear here.
    for value in payload["telemetry"].values():
        assert isinstance(value, int)
