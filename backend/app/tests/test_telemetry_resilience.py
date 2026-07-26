"""Telemetry must never crash the calling request flow."""

from app.connectors.telemetry import metrics
from app.connectors.telemetry.db import DbTelemetryConnector


def test_write_failure_increments_counter_and_does_not_raise(monkeypatch) -> None:
    metrics.reset_for_tests()
    prior_global_disabled = DbTelemetryConnector._global_disabled_after_failure
    DbTelemetryConnector._global_disabled_after_failure = False
    try:
        connector = DbTelemetryConnector(database_url="postgresql://example/test")

        async def _boom(*_a, **_kw):
            raise RuntimeError("db unreachable")

        # Force a failure deep inside the inner coroutine — asyncpg.connect is
        # the first awaited call. Patching it here means the coroutine *is*
        # awaited (no unawaited-coroutine warning), but the awaited call raises.
        import app.connectors.telemetry.db as db_module

        monkeypatch.setattr(db_module.asyncpg, "connect", _boom)

        # Must NOT raise.
        connector.record_step("trace-x", "route", "ok", detail="anything")

        snapshot = metrics.snapshot()
        assert snapshot["telemetry_write_failures"] >= 1
    finally:
        DbTelemetryConnector._global_disabled_after_failure = prior_global_disabled


def test_health_counter_reflects_failures() -> None:
    metrics.reset_for_tests()
    metrics.increment("telemetry_write_failures", 3)
    from app.api.routes_health import health

    assert health()["telemetry"]["write_failures"] == 3
