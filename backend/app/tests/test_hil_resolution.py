"""Unit tests for canonical HIL resolution."""

from __future__ import annotations

from app.chat.contracts.answer_contract import AnswerContract
from app.chat.hil_resolution import resolve_effective_hil_required


def test_effective_hil_from_evidence_plan_needs_hil() -> None:
    assert resolve_effective_hil_required(evidence_plan={"needs_hil": True}) is True


def test_effective_hil_from_answer_contract_status() -> None:
    contract = AnswerContract(hil_status="required", answer_goal=["spl_artifact"])
    assert resolve_effective_hil_required(answer_contract=contract) is True


def test_effective_hil_live_data_without_execution() -> None:
    assert resolve_effective_hil_required(live_data_request=True, execution_authorized=False) is True
    assert resolve_effective_hil_required(live_data_request=True, execution_authorized=True) is False


def test_effective_hil_from_human_review_gate() -> None:
    assert resolve_effective_hil_required(human_review={"required": True}) is True
