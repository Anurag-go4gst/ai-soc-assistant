"""Stage 3M-S1: SplunkResultEnvelope and fixture adapter tests."""

from __future__ import annotations

import ast
import inspect

from app.connectors.mcp import splunk_result_fixture as fixture_module
from app.connectors.mcp import splunk_result_envelope as envelope_module
from app.connectors.mcp.splunk_result_envelope import REDACTED_VALUE, SplunkResultEnvelope
from app.connectors.mcp.splunk_result_fixture import envelope_from_fixture_payload


def test_rows_and_field_derivation() -> None:
    payload = {
        "status": "ok",
        "rows": [
            {"user": "svc_app", "fail_count": 184},
            {"user": "admin", "fail_count": 22, "active": True},
        ],
        "row_count": 2,
    }
    env = envelope_from_fixture_payload(payload, origin="mock_connector")
    assert env.status == "ok"
    assert env.row_count == 2
    assert env.fields == ("user", "fail_count", "active")
    assert env.rows[0]["fail_count"] == 184
    assert env.rows[1]["active"] is True
    assert env.schema_confirmed is False
    assert env.schema_confirmed_reason == "mock_payload"


def test_empty_normalizes_from_ok_zero_rows() -> None:
    env = envelope_from_fixture_payload(
        {"status": "ok", "rows": [], "row_count": 0},
        origin="fixture",
    )
    assert env.status == "empty"
    assert env.row_count == 0
    assert env.rows == ()
    assert "zero_rows_normalized_to_empty" in env.warnings


def test_timeout_result() -> None:
    env = envelope_from_fixture_payload(
        {"status": "timeout", "error": "search_timeout", "rows": []},
    )
    assert env.status == "timeout"
    assert env.rows == ()
    assert env.error_code == "search_timeout"
    assert env.truncation_reason == "timeout"


def test_error_result() -> None:
    env = envelope_from_fixture_payload(
        {"status": "error", "error": "search_failed", "rows": [{"user": "x"}]},
    )
    assert env.status == "error"
    assert env.rows == ()
    assert env.error_code == "search_failed"


def test_truncation_by_total_row_count() -> None:
    rows = [{"id": i} for i in range(5)]
    env = envelope_from_fixture_payload(
        {
            "status": "ok",
            "rows": rows,
            "row_count": 5,
            "total_row_count": 20,
        },
        max_rows=100,
    )
    assert env.truncated is True
    assert env.total_row_count == 20
    assert env.truncation_reason in {"unknown", "row_limit"}


def test_truncation_by_explicit_fixture_flag() -> None:
    env = envelope_from_fixture_payload(
        {
            "status": "ok",
            "rows": [{"a": 1}],
            "row_count": 1,
            "truncated": True,
            "truncation_reason": "fixture_declared",
        },
    )
    assert env.truncated is True
    assert env.truncation_reason == "fixture_declared"


def test_truncation_by_row_limit() -> None:
    rows = [{"n": i} for i in range(10)]
    env = envelope_from_fixture_payload(
        {"status": "ok", "rows": rows, "row_count": 10},
        max_rows=3,
    )
    assert env.row_count == 3
    assert env.truncated is True
    assert env.truncation_reason == "row_limit"


def test_sensitive_value_redaction_keeps_key() -> None:
    env = envelope_from_fixture_payload(
        {
            "status": "ok",
            "rows": [{"user": "alice", "api_key": "super-secret-value"}],
            "row_count": 1,
        },
    )
    row = env.rows[0]
    assert "api_key" in row
    assert row["api_key"] == REDACTED_VALUE
    assert row["user"] == "alice"


def test_preview_rows_capped() -> None:
    rows = [{"n": i} for i in range(10)]
    env = envelope_from_fixture_payload(
        {"status": "ok", "rows": rows, "row_count": 10},
        max_rows=10,
    )
    preview = env.preview_rows(5)
    assert len(preview) == 5
    assert preview[0]["n"] == 0


def test_to_dict_stable_keys() -> None:
    env = envelope_from_fixture_payload(
        {"status": "ok", "rows": [{"x": 1}], "row_count": 1},
    )
    d1 = env.to_dict()
    d2 = env.to_dict()
    assert list(d1.keys()) == list(d2.keys())
    assert d1 == d2


def test_schema_confirmed_false_for_fixture_origins() -> None:
    fixture_env = envelope_from_fixture_payload({"status": "ok", "rows": [{"a": 1}], "row_count": 1})
    mock_env = envelope_from_fixture_payload(
        {"status": "ok", "rows": [{"a": 1}], "row_count": 1},
        origin="mock_connector",
    )
    assert fixture_env.schema_confirmed is False
    assert fixture_env.schema_confirmed_reason == "fixture_adapter"
    assert mock_env.schema_confirmed_reason == "mock_payload"


def test_fixture_module_has_no_real_mcp_or_network_imports() -> None:
    source = inspect.getsource(fixture_module)
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = (
        "app.connectors.mcp.splunk_mcp",
        "app.connectors.mcp.__init__",
        "app.api.routes_chat",
        "httpx",
        "requests",
        "urllib",
    )
    for name in imported:
        for bad in forbidden:
            assert bad not in name, f"unexpected import {name}"


def test_envelope_module_exports_dataclass() -> None:
    assert SplunkResultEnvelope.__name__ == "SplunkResultEnvelope"
    assert envelope_module.DEFAULT_MAX_ROWS == 100
    assert envelope_module.DEFAULT_PREVIEW_ROWS == 5
    assert envelope_module.FIELD_CAP == 40
    assert envelope_module.VALUE_CAP == 240
