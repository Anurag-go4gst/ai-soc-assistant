from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.config import settings
from app.schemas.requests import ChatRequest
from app.chat.pipeline import build_live_chat_response


PROBES = Path(__file__).resolve().parent / "fixtures" / "reference_knowledge" / "probes.json"
ID_RE = re.compile(r"\b(?:AML\.T\d{4}(?:\.\d{3})?|T\d{4}(?:\.\d{3})?|CVE-\d{4}-\d{4,7})\b")


@pytest.fixture(autouse=True)
def _offline_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEMETRY_MODE", "none")
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)


def _probe_rows(kind: str) -> list[dict[str, Any]]:
    rows = json.loads(PROBES.read_text(encoding="utf-8"))
    return [row for row in rows if row["kind"] == kind or (kind == "positive" and row["id"] in {"P1", "P2", "P3", "P4"})]


def _payload(query: str) -> dict[str, Any]:
    return build_live_chat_response(ChatRequest(message=query)).model_dump(mode="json")


def _answer_text(payload: dict[str, Any]) -> str:
    analyst = payload.get("analyst_response") or {}
    chunks = [
        payload.get("message"),
        analyst.get("direct_answer_summary"),
        analyst.get("one_sentence_finding"),
    ]
    return "\n".join(str(chunk) for chunk in chunks if chunk)


def _reference_facts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    analyst = payload.get("analyst_response") or {}
    facts = analyst.get("reference_facts") or (payload.get("structured_context") or {}).get("reference_facts") or []
    return [item for item in facts if isinstance(item, dict)]


@pytest.mark.parametrize("probe", _probe_rows("positive"), ids=lambda row: row["id"])
def test_positive_reference_answers_are_grounded(probe: dict[str, Any]) -> None:
    payload = _payload(str(probe["query"]))
    text = _answer_text(payload)
    facts = _reference_facts(payload)
    fact_ids = {str(fact.get("reference_id") or fact.get("technique_id") or "") for fact in facts}

    assert facts, probe["id"]
    assert any(str(fact.get("name") or "").strip() for fact in facts), probe["id"]
    assert all(str(fact.get("citation") or "").strip() for fact in facts), probe["id"]
    assert (payload.get("human_review") or {}).get("review_type") != "intent_clarification"
    assert "alert context before mapping" not in text.lower()
    for token in set(ID_RE.findall(text)):
        assert token in fact_ids, (probe["id"], token, sorted(fact_ids))


def test_cve_reference_answer_states_environment_gap() -> None:
    probe = next(row for row in _probe_rows("positive") if row["id"] == "P4")
    text = _answer_text(_payload(str(probe["query"]))).lower()
    assert "cve-2024-3400" in text
    assert "not found in the local cve snapshot" in text
    assert "reference taxonomy only" in text or "not confirmed activity" in text


@pytest.mark.parametrize("probe", _probe_rows("negative"), ids=lambda row: row["id"])
def test_negative_reference_probes_do_not_use_reference_path(probe: dict[str, Any]) -> None:
    payload = _payload(str(probe["query"]))
    trace = ((payload.get("control_plane_trace") or {}).get("plan_dispatch") or {})
    request_mode = ((payload.get("control_plane_trace") or {}).get("pipeline_dispatch") or {}).get("decision", {}).get(
        "request_mode"
    )
    assert not _reference_facts(payload), probe["id"]
    assert request_mode != "reference_knowledge"
    assert "reference_finalize" not in (trace.get("dispatch_schedule") or [])
