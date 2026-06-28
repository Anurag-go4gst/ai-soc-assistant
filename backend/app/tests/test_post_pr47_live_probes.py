"""Post-PR #47 live HTTP-path probes for catalogue template render and T1 routing."""

from __future__ import annotations

import pytest

from app.chat.pipeline import build_live_chat_response, _runtime_spl_governance
from app.config import settings
from app.schemas.requests import ChatRequest
from app.spl.runtime_source_profiles import resolve_runtime_profile_for_query
from app.use_cases.registry import match_use_cases

_Q010 = "Which hosts are generating the most SMB traffic?"
_Q046 = "Which users have excessive failed logins?"
_GENERIC_SPL = "Write me a SPL query for failed logins"
_WINEVENT = "Show Event 4624 logons outside business hours on 6/22"
_SCADA = "SCADA analog threshold breach on substation sensors"
_CISCO_IOC = "Look up IOC 1.2.3.4 in Cisco ASA logs"
_BLOCK_IP = "Block IP 10.0.0.5 immediately"


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)


def _payload(question: str) -> dict:
    return build_live_chat_response(ChatRequest(message=question)).model_dump(mode="json")


def _spl(payload: dict) -> str:
    cs = payload.get("candidate_spl") or {}
    if isinstance(cs, dict):
        return str(cs.get("candidate_spl") or "")
    return str(cs or "")


def _hil(payload: dict) -> tuple[str | None, str | None]:
    hr = payload.get("human_review") or {}
    return hr.get("review_type"), hr.get("reason")


def test_runtime_governance_allows_catalog_template_when_enrichment_inactive() -> None:
    gov = _runtime_spl_governance("auth_failed_login_spike")
    assert gov is not None
    assert gov.get("allowed_spl_templates") == ["auth_failed_login_spike"]
    assert gov.get("runtime_spl_governance_allowed") is True
    assert gov.get("governed_enrichment_load_allowed") is False


def test_q046_live_path_renders_auth_failed_login_template() -> None:
    payload = _payload(_Q046)
    review_type, reason = _hil(payload)
    spl = _spl(payload)
    assert review_type == "spl_revision"
    assert reason == "template_review_required"
    assert len(spl) > 80
    assert payload.get("workflow_plan", {}).get("execution_enabled") is False
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False
    assert contract.get("mcp_allowed") is False


def test_q010_live_path_review_only_smb_draft() -> None:
    payload = _payload(_Q010)
    review_type, _ = _hil(payload)
    spl = _spl(payload)
    assert review_type == "spl_revision"
    assert len(spl) > 80
    assert payload.get("workflow_plan", {}).get("execution_enabled") is False


def test_generic_spl_meta_routes_soc_generate_spl() -> None:
    matches = match_use_cases(_GENERIC_SPL, limit=2)
    assert matches[0].use_case_id == "soc_generate_spl"
    payload = _payload(_GENERIC_SPL)
    use_case = (payload.get("selected_use_case") or {}).get("use_case_id")
    assert use_case == "soc_generate_spl"
    assert _spl(payload)


def test_scada_threshold_review_only_spl() -> None:
    assert resolve_runtime_profile_for_query(_SCADA) is not None
    payload = _payload(_SCADA)
    spl = _spl(payload)
    assert len(spl) > 40
    assert "scada_perf" in spl
    assert payload.get("workflow_plan", {}).get("execution_enabled") is False


def test_cisco_asa_ioc_lookup_review_only_spl() -> None:
    assert resolve_runtime_profile_for_query(_CISCO_IOC) is not None
    payload = _payload(_CISCO_IOC)
    spl = _spl(payload)
    assert "cisco_asa" in spl
    assert payload.get("workflow_plan", {}).get("execution_enabled") is False


def test_winevent_off_shift_preserves_wineventlog_index() -> None:
    payload = _payload(_WINEVENT)
    spl = _spl(payload)
    assert "index=wineventlog" in spl
    assert "4624" in spl
    assert "login_hour < 6" in spl and "login_hour >= 22" in spl


def test_unsafe_block_ip_refuses_execution() -> None:
    payload = _payload(_BLOCK_IP)
    _review_type, reason = _hil(payload)
    assert reason == "unsafe_action_blocked"
    assert _spl(payload) == ""
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False
