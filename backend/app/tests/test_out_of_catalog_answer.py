"""T1.4 — honest out-of-catalog answers: notice, suggestions, fail-closed guard."""

from __future__ import annotations

from app.api.routes_chat import chat
from app.chat.final_answer_validator import validate_final_answer
from app.evals.golden_answer_runner import _model_to_dict
from app.evals.sentinel_eval import sentinel_runtime
from app.schemas.requests import ChatRequest

OUT_OF_SET = "Strange OT chatter to a brand new external host overnight, anything to hunt?"
IN_REGISTRY = "Which hosts are generating the most SMB traffic?"


def _payload(question: str) -> dict:
    with sentinel_runtime():
        return _model_to_dict(chat(ChatRequest(message=question)))


def test_out_of_set_answer_carries_notice_and_suggestions() -> None:
    payload = _payload(OUT_OF_SET)
    contract = payload.get("answer_contract") or {}
    assert contract.get("out_of_catalog_notice"), "notice missing"
    assert "outside the governed question catalog" in contract["out_of_catalog_notice"]
    assert (contract.get("render_sections") or {}).get("out_of_catalog_notice") is True
    suggestions = contract.get("nearest_questions") or []
    assert len(suggestions) <= 3
    for item in suggestions:
        assert item.get("question_ref", "").startswith("q0.")
    validation = payload.get("final_answer_validation") or {}
    assert validation.get("guard_status") != "blocked"


def test_registry_matched_answer_has_no_notice() -> None:
    payload = _payload(IN_REGISTRY)
    contract = payload.get("answer_contract") or {}
    assert contract.get("out_of_catalog_notice") is None
    assert not (contract.get("render_sections") or {}).get("out_of_catalog_notice")


def test_unsafe_request_still_overrides() -> None:
    payload = _payload("Block this IP on the firewall immediately.")
    contract = payload.get("answer_contract") or {}
    assert contract.get("human_review_required") is True


def test_validator_fails_closed_when_notice_missing() -> None:
    class _Analyst:
        mitre_mappings: list = []
        spl_code = None
        response_profile = ""
        recommended_actions: list = []

    status = validate_final_answer(
        analyst_response=_Analyst(),
        answer_contract={"not_claimed_technique_ids": [], "answer_goal": []},
        evidence_plan={
            "answer_mode": "live_investigation",
            "resource_plan": {"provenance": {"match_path": "out_of_registry"}, "steps": []},
        },
        mitre_decision={},
    )
    payload = status.model_dump() if hasattr(status, "model_dump") else status.__dict__
    text = str(payload)
    assert "out_of_catalog_notice_missing" in text


def test_validator_passes_when_notice_present() -> None:
    class _Analyst:
        mitre_mappings: list = []
        spl_code = None
        response_profile = ""
        recommended_actions: list = []

    status = validate_final_answer(
        analyst_response=_Analyst(),
        answer_contract={
            "not_claimed_technique_ids": [],
            "answer_goal": [],
            "out_of_catalog_notice": "This question is outside the governed question catalog.",
        },
        evidence_plan={
            "answer_mode": "live_investigation",
            "resource_plan": {"provenance": {"match_path": "out_of_registry"}, "steps": []},
        },
        mitre_decision={},
    )
    text = str(status.model_dump() if hasattr(status, "model_dump") else status.__dict__)
    assert "out_of_catalog_notice_missing" not in text
