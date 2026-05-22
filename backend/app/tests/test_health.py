from app.api.routes_health import health


def test_health() -> None:
    assert health() == {"status": "ok", "service": "ai-soc-assistant-backend"}
