"""Live-path SPL smoke tests (SPL audit landing).

Locks the *running* `/chat` pipeline behaviour the eval harnesses missed:
  1. EDR and DNS governed templates render AND pass deterministic validation —
     i.e. the SPL policy default actually allows `pgcil:edr` / `pgcil:dns`. A
     regression to the allowed-sourcetype set (the env-drift that broke these in
     prod) flips `approved` to False and fails here.
  2. Network/SMB analytics drafts (no governed template) degrade to a review-only
     lab-tier draft: family-aware source-resolve keeps the placeholder index/
     sourcetype (no blanket `pgcil:auth` substitution), stays `approved=False`,
     and never becomes execution-eligible.
  3. q0.q010 (SMB top-talkers) keeps its frozen clarification contract: lab-tier,
     approved=False, source-profile clarification surfaced (the lab-draft degrade
     must not promote it to an executable answer).

These run through `build_live_chat_response`, the real pipeline entry.
"""
from __future__ import annotations

import pytest

import app.chat  # noqa: F401  warm the chat package (resolves draft_preview import cycle)
from app.chat.pipeline import build_live_chat_response
from app.schemas.requests import ChatRequest


@pytest.fixture(autouse=True)
def _spl_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    # Match the prod `.env` posture: EDR + DNS sourcetypes allowed.
    monkeypatch.setattr(
        "app.config.settings.spl_allowed_sourcetypes",
        "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns",
    )


def _prod_spl_posture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Relevance-first failover + draft preview, as in prod `.env`.

    The lab-draft last resort lives in the LLM-failover degrade chain (gated on
    this flag, default off in test config). The local LLM client is unreachable
    under test, so failover falls straight through to the deterministic lab draft
    — exactly the prod degrade path when the model is down.
    """
    monkeypatch.setattr("app.config.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_spl_draft_preview_enabled", True)


def _candidate(message: str) -> tuple[dict, dict, dict]:
    response = build_live_chat_response(ChatRequest(message=message, session_id="spl-live-test"))
    payload = response.model_dump()
    candidate = payload.get("candidate_spl") or {}
    validation = payload.get("spl_validation") or {}
    human_review = payload.get("human_review") or {}
    return candidate, validation, human_review


def test_edr_powershell_template_renders_and_validates() -> None:
    candidate, validation, _ = _candidate("Which hosts ran suspicious PowerShell?")
    assert candidate.get("generation_mode") == "deterministic_template_render"
    assert candidate.get("template_id") == "edr_powershell_suspicious_command"
    spl = candidate.get("candidate_spl") or ""
    assert "sourcetype=pgcil:edr" in spl
    # The env-drift that dropped pgcil:edr from SPL_ALLOWED_SOURCETYPES surfaced
    # here as approved=False / template_spl_validation_failed.
    assert validation.get("approved") is True
    assert "template_spl_validation_failed" not in (candidate.get("warnings") or [])
    assert candidate.get("execution_eligible") is False


def test_dns_beaconing_template_renders_and_validates() -> None:
    candidate, validation, _ = _candidate(
        "Show me hosts beaconing to newly registered domains over Kerberos."
    )
    assert candidate.get("generation_mode") == "deterministic_template_render"
    assert candidate.get("template_id") == "dns_beaconing_candidate"
    spl = candidate.get("candidate_spl") or ""
    assert "sourcetype=pgcil:dns" in spl
    assert validation.get("approved") is True
    assert candidate.get("execution_eligible") is False


def test_network_smb_draft_stays_lab_tier_without_auth_fallback(monkeypatch) -> None:
    _prod_spl_posture(monkeypatch)
    candidate, validation, _ = _candidate("Which hosts made SMB connections to many peers?")
    # No governed template for this analytics intent -> deterministic lab draft.
    assert candidate.get("generation_mode") == "deterministic_lab_draft"
    spl = candidate.get("candidate_spl") or ""
    # Family-aware source-resolve must NOT substitute the auth sourcetype for a
    # network/SMB placeholder; the slot stays unresolved for analyst review.
    assert "sourcetype=pgcil:auth" not in spl
    assert "<" in spl  # placeholder remains
    # Lab-tier stays review-only: never approved, never execution-eligible.
    assert validation.get("approved") is False
    assert candidate.get("execution_eligible") is False


def test_q010_smb_top_talkers_keeps_clarification_contract(monkeypatch) -> None:
    _prod_spl_posture(monkeypatch)
    candidate, validation, human_review = _candidate(
        "Which hosts are generating the most SMB traffic?"
    )
    # Lab-tier degrade must not promote q0.q010 to an executable answer.
    assert validation.get("approved") is False
    assert candidate.get("execution_eligible") is False
    spl = candidate.get("candidate_spl") or ""
    assert "sourcetype=pgcil:auth" not in spl
    # Source-profile clarification must survive the execution stage.
    assert human_review.get("required") is True
    assert human_review.get("review_type") == "spl_source_profile_clarification"
