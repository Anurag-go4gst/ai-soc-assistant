"""T2.3 — skill-derived answer sections are content-driven contract sections."""

from __future__ import annotations

import uuid

from app.api.routes_chat import chat
from app.evals.golden_answer_runner import _model_to_dict
from app.evals.sentinel_eval import sentinel_runtime
from app.schemas.requests import ChatRequest


def _contract(question: str) -> dict:
    with sentinel_runtime():
        payload = _model_to_dict(
            chat(ChatRequest(message=question, session_id=f"t23-{uuid.uuid4()}"))
        )
    return payload.get("answer_contract") or {}


def test_enriched_use_case_carries_both_checklist_sections() -> None:
    contract = _contract("Which hosts ran suspicious PowerShell?")
    render = contract.get("render_sections") or {}
    assert render.get("triage_checklist") is True
    assert render.get("evidence_checklist") is True
    assert contract.get("analyst_checklist_safe")
    assert contract.get("required_evidence")


def test_sections_absent_without_backing_content() -> None:
    contract = _contract("What happened for this specific notable event?")
    render = contract.get("render_sections") or {}
    assert not render.get("triage_checklist")
    assert not render.get("evidence_checklist")
