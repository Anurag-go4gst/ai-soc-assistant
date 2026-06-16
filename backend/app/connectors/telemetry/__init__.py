from app.config import settings
from app.connectors.telemetry.base import TelemetryConnector
from app.connectors.telemetry.db import DbTelemetryConnector
from app.connectors.telemetry.null import NullTelemetryConnector


def get_telemetry_connector() -> TelemetryConnector:
    mode = settings.telemetry_mode.strip().lower()
    sink = settings.ai_soc_telemetry_sink.strip().lower()
    if mode == "none" or sink in {"none", "splunk"}:
        return NullTelemetryConnector()
    if sink == "file":
        from app.connectors.telemetry.file import FileTelemetryConnector

        return FileTelemetryConnector()
    return DbTelemetryConnector()


__all__ = ["TelemetryConnector", "get_telemetry_connector"]
