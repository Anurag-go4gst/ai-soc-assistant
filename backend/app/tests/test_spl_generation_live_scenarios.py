"""Live /chat SPL generation scenarios: governed template vs out-of-catalog guidance."""

from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.schemas.requests import ChatRequest

TEMPLATE_QUERY = "Show failed login spike by user in the last 24 hours"
OUT_OF_TEMPLATE_QUERY = "Strange OT chatter to a new external host overnight, anything to hunt?"
HYPOTHESIS_QUERY = (
    "What hunting hypotheses should I validate for cobalt strike beaconing "
    "across VPN and DNS logs without a known IOC list?"
)


@pytest.fixture(autouse=True)
def _spl_policy_for_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.spl_allowed_sourcetypes",
        "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns",
    )
    monkeypatch.setattr("app.config.settings.mcp_discovery_enabled", True)
    monkeypatch.setattr("app.config.settings.mcp_global_execution_enabled", False)


def test_template_query_renders_governed_auth_failed_login_spike() -> None:
    response = chat(ChatRequest(message=TEMPLATE_QUERY))

    assert response.candidate_spl is not None
    assert response.spl_validation is not None
    assert response.candidate_spl.generation_mode == "deterministic_template_render"
    assert response.candidate_spl.template_id == "auth_failed_login_spike"
    assert response.spl_validation.approved is False
    assert "missing_binding:group_by_user" in (response.spl_validation.reject_reasons or [])
    assert response.human_review is not None
    assert response.human_review.review_type == "spl_revision"


def test_hypothesis_guidance_query_avoids_dns_template_spl() -> None:
    response = chat(ChatRequest(message=HYPOTHESIS_QUERY))

    assert response.selected_skill == "guided_investigation"
    assert response.candidate_spl is None
    assert response.spl_validation is None


def test_out_of_template_query_routes_to_guided_investigation_without_spl() -> None:
    response = chat(ChatRequest(message=OUT_OF_TEMPLATE_QUERY))

    assert response.selected_skill == "guided_investigation"
    assert response.candidate_spl is None
    assert response.spl_validation is None

    contract = response.answer_contract
    assert contract is not None
    notice = contract.get("out_of_catalog_notice") if isinstance(contract, dict) else getattr(contract, "out_of_catalog_notice", None)
    assert notice
    assert "outside the governed question catalog" in str(notice).lower()

    assert response.execution is not None
    assert response.execution.status != "executed"
