"""Unit tests for telemetry read-store JSON decode recovery (Phase P0-B).

Covers the bug where asyncpg returned JSONB columns as serialized JSON strings
(or bytes) and ``dict("...")`` raised ``ValueError``, aborting the whole timeline
fetch (HTTP 500 → 0/100 debug bundles). These tests exercise the normalizer and
the pure row→event mappers directly; no live Postgres is required.
"""

from __future__ import annotations

from typing import Any

from app.connectors.telemetry import read_store
from app.connectors.telemetry.read_store import (
    _as_dict,
    _map_event_rows_to_events,
    _map_step_rows_to_events,
    _normalize_event,
)


class _FakeRow:
    """Minimal asyncpg.Record-like mapping for row→event tests."""

    def __init__(self, **fields: Any) -> None:
        self._fields = fields

    def __getitem__(self, key: str) -> Any:
        return self._fields[key]


# --------------------------------------------------------------------------- #
# _as_dict
# --------------------------------------------------------------------------- #


def test_as_dict_passes_dict_through_as_copy() -> None:
    src = {"a": 1, "b": {"c": 2}}
    out = _as_dict(src)
    assert out == src
    assert out is not src  # copy, not alias


def test_as_dict_decodes_json_text_string() -> None:
    out = _as_dict('{"answer_mode": "full_answer", "n": 3}')
    assert out == {"answer_mode": "full_answer", "n": 3}


def test_as_dict_decodes_bytes() -> None:
    out = _as_dict(b'{"k": "v"}')
    assert out == {"k": "v"}


def test_as_dict_none_returns_empty() -> None:
    assert _as_dict(None) == {}


def test_as_dict_empty_string_returns_empty() -> None:
    assert _as_dict("") == {}
    assert _as_dict("   ") == {}


def test_as_dict_malformed_string_returns_decode_marker_without_raising() -> None:
    out = _as_dict("not json at all {{{")
    assert out == {"_decode_error": True}


def test_as_dict_malformed_does_not_raise_value_error() -> None:
    # The original crash: dict("...") on a serialized string. Must not raise.
    out = _as_dict("a,b,c")
    assert isinstance(out, dict)
    assert out.get("_decode_error") is True


def test_as_dict_list_shaped_json_is_redacted() -> None:
    out = _as_dict("[1, 2, 3]")
    assert out == {"_decode_error": True, "_decode_error_reason": "non_object_json"}


def test_as_dict_scalar_json_is_wrapped() -> None:
    assert _as_dict("42") == {
        "_decode_error": True,
        "_decode_error_reason": "non_object_json",
    }


def test_as_dict_unexpected_type_returns_decode_marker() -> None:
    assert _as_dict(12345) == {"_decode_error": True}


# --------------------------------------------------------------------------- #
# _normalize_event
# --------------------------------------------------------------------------- #


def test_normalize_event_recovers_text() -> None:
    event, is_err = _normalize_event('{"step": "plan"}')
    assert is_err is False
    assert event.get("step") == "plan"


def test_normalize_event_flags_malformed() -> None:
    event, is_err = _normalize_event("broken {{{")
    assert is_err is True
    assert event.get("_decode_error") is True


def test_normalize_event_dict_passthrough() -> None:
    event, is_err = _normalize_event({"a": 1})
    assert is_err is False
    assert event.get("a") == 1


def test_normalize_event_keeps_forensic_llm_prompt_text() -> None:
    prompt = "Investigate " + ("x" * 2500)
    payload = {
        "schema_version": "llm_interaction_v1",
        "role": "spl_advisory_generator",
        "forensic": {"request": {"user_prompt": prompt, "max_tokens": 800}, "response": {"raw_text": prompt}},
    }
    event, is_err = _normalize_event(payload)
    assert is_err is False
    assert event["forensic"]["request"]["user_prompt"] == prompt
    assert event["forensic"]["request"]["max_tokens"] == 800
    assert "...[truncated]" not in event["forensic"]["request"]["user_prompt"]


# --------------------------------------------------------------------------- #
# row → event mappers: one corrupt row must not lose the good rows
# --------------------------------------------------------------------------- #


def test_map_event_rows_one_corrupt_keeps_good_events() -> None:
    rows = [
        _FakeRow(event={"ok": 1}, created_at=None),
        _FakeRow(event="this is not json {{{", created_at=None),
        _FakeRow(event='{"ok": 2}', created_at=None),
    ]
    events, decode_errors = _map_event_rows_to_events("llm_call", rows)

    assert len(events) == 3  # no good event lost
    assert decode_errors == 1
    assert events[0]["event"].get("ok") == 1
    assert events[1]["event"].get("_decode_error") is True
    assert events[2]["event"].get("ok") == 2
    assert all(e["kind"] == "llm_call" for e in events)


def test_map_step_rows_one_corrupt_keeps_good_events() -> None:
    rows = [
        _FakeRow(event={"detail": "a"}, created_at=None, step_name="s1", status="ok"),
        _FakeRow(event="bad}}}", created_at=None, step_name="s2", status="ok"),
        _FakeRow(event=b'{"detail": "c"}', created_at=None, step_name="s3", status="ok"),
    ]
    events, decode_errors = _map_step_rows_to_events("step", rows)

    assert len(events) == 3
    assert decode_errors == 1
    assert events[0]["event"].get("detail") == "a"
    assert events[1]["event"].get("_decode_error") is True
    assert events[2]["event"].get("detail") == "c"
    assert [e["step_name"] for e in events] == ["s1", "s2", "s3"]


def test_map_event_rows_none_event_becomes_empty_dict() -> None:
    rows = [_FakeRow(event=None, created_at=None)]
    events, decode_errors = _map_event_rows_to_events("rag_retrieval", rows)
    assert decode_errors == 0
    assert events[0]["event"] == {}


def test_map_event_rows_all_good_zero_decode_errors() -> None:
    rows = [
        _FakeRow(event={"a": 1}, created_at=None),
        _FakeRow(event='{"b": 2}', created_at=None),
    ]
    events, decode_errors = _map_event_rows_to_events("step", rows)
    assert decode_errors == 0
    assert len(events) == 2


# --------------------------------------------------------------------------- #
# Text-metadata recovery (previously silently dropped by isinstance guards)
# --------------------------------------------------------------------------- #


def test_serialize_run_recovers_text_metadata() -> None:
    row = _FakeRow(
        trace_id="t1",
        run_id="r1",
        user_id=None,
        entrypoint="chat",
        status="ok",
        metadata='{"answer_mode": "full_answer", "selected_skill": "alert_summary"}',
        started_at=None,
        ended_at=None,
    )
    run = read_store._serialize_run(row)
    # Previously dict(text) raised; now text metadata is recovered, not dropped.
    assert run["answer_mode"] == "full_answer"
    assert run["selected_skill"] == "alert_summary"
