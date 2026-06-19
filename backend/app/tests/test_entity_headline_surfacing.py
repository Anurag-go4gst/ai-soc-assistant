"""WS-7b entity-bound + WS-7c T1 headline surfacing tests."""

from __future__ import annotations

from app.chat.entity_headline_surfacing import (
    apply_entity_and_headline_surfacing,
    build_entity_bound_checklist,
    extract_named_assets,
    is_status_only_message,
)
from app.config import settings


def test_extract_named_assets_relay_and_substation() -> None:
    assets = extract_named_assets("Relay RLY-4401 at Gandhinagar substation shows odd syslog")
    assert any("RLY-4401" in a for a in assets)
    assert any("Gandhinagar substation" in a for a in assets)


def test_status_only_detection() -> None:
    assert is_status_only_message("Governed SPL draft ready. It has passed deterministic validation.")
    assert not is_status_only_message(
        "Asset-scoped investigation — RLY-4401 (review-only)\n\nChecklist:\n- " + "x" * 400
    )


def test_entity_checklist_states_compromise_not_confirmed() -> None:
    text = build_entity_bound_checklist("is RLY-4401 compromised", ["RLY-4401"])
    assert "does not confirm compromise" in text.lower() or "not confirm compromise" in text.lower()
    assert "RLY-4401" in text


def test_ws7b_enriches_entity_query(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    message, _ = apply_entity_and_headline_surfacing(
        message="Investigation planning is complete.",
        answer_contract=None,
        analyst_response=None,
        spl_validation=None,
        candidate_spl=None,
        user_query="Relay RLY-4401 at Gandhinagar substation shows odd syslog — is it compromised?",
    )
    assert "RLY-4401" in message
    assert "asset-scoped" in message.lower()


def test_ws7c_enriches_status_stub_with_spl(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    message, _ = apply_entity_and_headline_surfacing(
        message="Governed SPL draft ready. It has passed deterministic validation and has not been executed.",
        answer_contract=None,
        analyst_response=None,
        spl_validation={"normalized_spl": "index=ot sourcetype=auth action=failure | stats count"},
        candidate_spl=None,
        user_query="Pull the failed login count from Splunk for OT jump hosts in the last hour.",
    )
    assert "objective:" in message.lower()
    assert "review steps" in message.lower()


def test_passthrough_when_not_stub(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    rich = "Guided investigation — signal class: protocol command (review-only)\n\n" + "Hypotheses\n- " + "x" * 400
    message, _ = apply_entity_and_headline_surfacing(
        message=rich,
        answer_contract=None,
        analyst_response=None,
        spl_validation=None,
        candidate_spl=None,
        user_query="hunt for modbus writes",
    )
    assert message == rich
