"""Tolerant JSON parser net for the LLM SPL producer."""

from __future__ import annotations

from app.spl.llm_fallback import (
    _extract_first_json_object,
    _repair_json_text,
    _strict_json_payload,
)


def test_clean_json_parses() -> None:
    payload, errors = _strict_json_payload('{"status": "candidate_generated", "governed": false}')
    assert errors == []
    assert payload and payload["status"] == "candidate_generated"


def test_fenced_and_prose_wrapped_json_parses() -> None:
    raw = 'Here you go:\n```json\n{"status": "candidate_generated", "candidate_spl": "search index=<x>"}\n```\nDone.'
    payload, errors = _strict_json_payload(raw)
    assert errors == []
    assert payload and payload["candidate_spl"] == "search index=<x>"


def test_trailing_comma_repaired() -> None:
    payload, errors = _strict_json_payload('{"status": "candidate_generated", "governed": false,}')
    assert errors == []
    assert payload and payload["governed"] is False


def test_truncated_fails_closed() -> None:
    payload, errors = _strict_json_payload('{"status": "candidate_generated", "candidate_spl":')
    assert payload is None
    assert errors and "strict_json_parse_failed" in errors[0]


def test_missing_delimiter_fails_closed() -> None:
    # The parser must not invent a missing comma — fail closed, never guess values.
    payload, errors = _strict_json_payload('{"a": "1" "b": "2"}')
    assert payload is None


def test_extract_ignores_braces_in_strings() -> None:
    extracted = _extract_first_json_object('{"spl": "search foo | eval x={bad}"} trailing')
    assert extracted == '{"spl": "search foo | eval x={bad}"}'


def test_repair_only_removes_trailing_commas() -> None:
    assert _repair_json_text('{"a":1,}') == '{"a":1}'
    assert _repair_json_text('{"a":1}') == '{"a":1}'
