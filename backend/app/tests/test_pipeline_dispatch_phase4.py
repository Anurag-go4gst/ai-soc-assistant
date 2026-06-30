"""Phase 4 — LLM SPL input/output preservation + persistence."""

from __future__ import annotations

import json

import pytest

from app.spl.llm_plan_compiler import (
    _grounding_block,
    _plan_user_prompt,
    _redacted_detection_plan,
    generate_llm_spl_via_plan,
)


_PLAN = {
    "data_domain": "auth",
    "filters": [{"field": "action", "match": "failure"}],
    "group_by": ["src_ip"],
    "metric": "count",
    "detection_family": "auth_failed_login_spike",
    "required_fields": ["src_ip", "action"],
}


@pytest.fixture
def _llm_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.spl.llm_plan_compiler.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr("app.spl.llm_plan_compiler.settings.ai_soc_llm_enabled", True)
    monkeypatch.setattr("app.spl.llm_plan_compiler.settings.ai_soc_llm_mode", "shadow")


def test_grounding_block_renders_slots_and_advisory() -> None:
    block = _grounding_block(
        slot_handoff={"normalized_slots": {"host": "web01", "user": "alice"}},
        mcp_discovery_context={"indexes": ["pgcil_soc"], "sourcetypes": ["wineventlog"]},
        llm_intent_advisory={"entity_slots_candidate": {"event_code": "4625"}},
    )
    assert "host=web01" in block
    assert "pgcil_soc" in block
    assert "event_code=4625" in block


def test_plan_user_prompt_includes_grounding() -> None:
    prompt = _plan_user_prompt("find spikes", "Resolved slots (advisory): host=web01")
    assert "find spikes" in prompt
    assert "host=web01" in prompt
    assert _plan_user_prompt("q") == "Investigation request:\nq\n\nReturn only the detection plan JSON."


def test_redacted_detection_plan_maps_domain_placeholders() -> None:
    snap = _redacted_detection_plan(_PLAN)
    assert snap["data_domain"] == "auth"
    assert snap["index"].startswith("<")
    assert "action=failure" in snap["filters"]
    assert snap["detection_family"] == "auth_failed_login_spike"


def test_generate_via_plan_populates_detection_plan(_llm_on: None) -> None:
    result = generate_llm_spl_via_plan(
        user_query="failed logins by source",
        plan_raw_output_provider=lambda: json.dumps(_PLAN),
    )
    assert result is not None
    assert result.detection_plan is not None
    assert result.detection_plan["data_domain"] == "auth"
    assert result.candidate_spl.strip()


def test_persist_llm_spl_plan_writes_state_and_dispatch() -> None:
    from app.chat.pipeline import persist_llm_spl_plan

    plan = {"index": "<auth_index>", "sourcetype": "<auth_sourcetype>", "data_domain": "auth"}
    state = {"pipeline_dispatch": {"decision": {}, "runtime_context": {}}}
    out = persist_llm_spl_plan(state, plan)  # type: ignore[arg-type]
    assert out["llm_spl_plan"]["index"] == "<auth_index>"
    assert out["llm_spl_plan"]["consumed_by"] == [
        "spl_source_resolve",
        "mcp_execution",
        "mitre_finalize",
        "narration",
    ]
    assert out["pipeline_dispatch"]["runtime_context"]["llm_spl_plan"]["data_domain"] == "auth"


def test_persist_llm_spl_plan_noop_on_empty() -> None:
    from app.chat.pipeline import persist_llm_spl_plan

    state = {"foo": 1}
    assert persist_llm_spl_plan(state, None) is state  # type: ignore[arg-type]
    assert persist_llm_spl_plan(state, {}) is state  # type: ignore[arg-type]
