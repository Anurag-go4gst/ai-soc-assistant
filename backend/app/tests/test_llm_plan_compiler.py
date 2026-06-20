"""Plan-plus-compiler path: deterministic, SOC-STD-compliant, lab-tier exposure."""

from __future__ import annotations

import json

import pytest

from app.config import settings
from app.spl.llm_plan_compiler import compile_plan_to_spl, generate_llm_spl_via_plan

_PLAN = {
    "detection_family": "ot_modbus_unauthorized_write",
    "data_domain": "ot_network",
    "time_window_hours": 24,
    "filters": [
        {"field": "protocol", "match": "modbus"},
        {"field": "function_code", "match": "16"},
    ],
    "group_by": ["src_ip", "dest_ip"],
    "metric": "count",
    "assumptions": ["<ot_network_index> is the OT network telemetry source"],
    "required_fields": ["src_ip", "dest_ip", "protocol", "function_code"],
}


@pytest.fixture
def _llm_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")


def test_compile_is_socstd_shaped() -> None:
    spl = compile_plan_to_spl(_PLAN)
    # placeholders, time bound, stats, strftime AFTER stats, sort, head 100
    assert "index=<ot_network_index>" in spl and "sourcetype=<ot_network_sourcetype>" in spl
    assert "earliest=-24h latest=now" in spl
    assert "| stats count as event_count" in spl
    assert spl.index("stats") < spl.index("strftime")  # ordering rule
    assert spl.rstrip().endswith("head 100")
    # only allowlisted commands; no from/tstats/subsearch
    for forbidden in ("tstats", "| from ", "delete", "outputlookup", "["):
        assert forbidden not in spl


def test_compile_is_deterministic() -> None:
    assert compile_plan_to_spl(_PLAN) == compile_plan_to_spl(_PLAN)


def test_compile_sanitizes_injection() -> None:
    plan = {**_PLAN, "filters": [{"field": "src_ip", "match": '10.0.0.1" | delete'}]}
    spl = compile_plan_to_spl(plan)
    # The pipe and quote are stripped, so the payload cannot break out of the
    # quoted term into a new command. "delete" survives only as an inert quoted
    # search value, never as `| delete`.
    assert "| delete" not in spl
    assert 'src_ip="10.0.0.1 delete"' in spl


def test_plan_path_reaches_lab_tier(_llm_on: None) -> None:
    result = generate_llm_spl_via_plan(
        user_query="Detect Modbus writes to PLCs from unapproved hosts",
        plan_raw_output_provider=lambda: json.dumps(_PLAN),
    )
    assert result is not None
    # compiled SPL passes quality + is exposed as a review-only lab candidate
    assert result.quality_status == "passed"
    assert result.lab_tier is True
    # governance invariants — never executable
    assert result.validation.get("approved") is False
    assert result.validation.get("normalized_spl") is None
    assert result.validation.get("execution_eligible") in (False, None)


def test_plan_path_disabled_without_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    result = generate_llm_spl_via_plan(
        user_query="x", plan_raw_output_provider=lambda: json.dumps(_PLAN)
    )
    assert result is not None
    assert result.lab_tier is False
