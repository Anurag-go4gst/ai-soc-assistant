"""P0 — semantic fidelity initial/repair matrix for utility SPL authoring."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.config import settings
from app.spl.utility_spl_authoring import candidate_from_universal_utility_authoring

DENIED_TOP_SRC_QUERY = (
    "Give me an SPL query to show the top source IPs generating denied firewall "
    "traffic in the last 24 hours."
)
FAITHFUL_SPL = """
search index=pgcil_soc sourcetype=cisco:firepower earliest=-24h latest=now
(action=denied OR action=blocked)
| stats count as event_count by src_ip
| sort - event_count
| head 10
""".strip()
UNFAITHFUL_SPL = (
    "search index=pgcil_soc sourcetype=cisco:firepower earliest=-24h latest=now "
    "| table _time src_ip | head 100"
)
WORSE_SPL = "search index=pgcil_soc earliest=-24h latest=now | head 100"


class _Telemetry:
    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_spl_validation(self, *args: Any, **kwargs: Any) -> None:
        return None


def _llm_payload(spl: str) -> str:
    return json.dumps(
        {
            "status": "candidate_generated",
            "confidence_score": 0.72,
            "confidence_label": "medium",
            "detection_family": "firewall_denied_top_src",
            "candidate_spl": spl,
            "assumptions": ["Denied firewall top-source review draft"],
            "required_fields": ["src_ip", "action"],
            "missing_details": [],
            "clarifying_questions": [],
            "validation_notes": [],
            "soc_std_rules_applied": [],
            "risk_notes": [],
            "execution_eligible": False,
            "governed": False,
            "catalog_approved": False,
        }
    )


@pytest.fixture
def spl_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", True)
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )


def _run_authoring(
    *,
    provider,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    profile = __import__(
        "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
    ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl")
    return candidate_from_universal_utility_authoring(
        trace_id="p0-fidelity",
        skill="spl_generation",
        user_query=DENIED_TOP_SRC_QUERY,
        telemetry=_Telemetry(),
        profile=profile,
        spl_governance=None,
        llm_raw_output_provider=provider,
    )


def test_a_initial_passes_fidelity_emits_candidate(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    candidate, validation = _run_authoring(
        provider=lambda: _llm_payload(FAITHFUL_SPL),
        monkeypatch=monkeypatch,
    )
    assert candidate is not None and validation is not None
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("semantic_fidelity_final", {}).get("passed") is True
    assert candidate.get("spl_authoring_unavailable") is False
    assert candidate.get("candidate_spl")
    assert "semantic_fidelity_unresolved" not in (validation.get("reject_reasons") or [])


def test_b_initial_fails_repair_succeeds(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def provider() -> str:
        calls["n"] += 1
        return _llm_payload(UNFAITHFUL_SPL if calls["n"] == 1 else FAITHFUL_SPL)

    candidate, validation = _run_authoring(provider=provider, monkeypatch=monkeypatch)
    assert candidate is not None and validation is not None
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("bounded_repair_used") is True
    assert trace.get("semantic_fidelity_final", {}).get("passed") is True
    assert candidate.get("candidate_spl")
    assert candidate.get("spl_authoring_unavailable") is False


def test_c_repair_improves_but_fidelity_still_unresolved(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    slightly_better = (
        "search index=pgcil_soc sourcetype=cisco:firepower earliest=-24h latest=now "
        "| stats count by src_ip | head 10"
    )
    calls = {"n": 0}

    def provider() -> str:
        calls["n"] += 1
        return _llm_payload(UNFAITHFUL_SPL if calls["n"] == 1 else slightly_better)

    candidate, validation = _run_authoring(provider=provider, monkeypatch=monkeypatch)
    assert candidate is not None and validation is not None
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("semantic_fidelity_unresolved") is True
    assert candidate.get("candidate_spl") == ""
    assert candidate.get("spl_authoring_unavailable") is True
    assert "semantic_fidelity_unresolved" in (validation.get("reject_reasons") or [])


def test_d_repair_makes_semantics_worse_stays_unavailable(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def provider() -> str:
        calls["n"] += 1
        return _llm_payload(UNFAITHFUL_SPL if calls["n"] == 1 else WORSE_SPL)

    candidate, validation = _run_authoring(provider=provider, monkeypatch=monkeypatch)
    assert candidate is not None and validation is not None
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("semantic_fidelity_unresolved") is True
    assert candidate.get("candidate_spl") == ""
    assert "semantic_fidelity_unresolved" in (validation.get("reject_reasons") or [])


def test_e_repair_schema_invalid_stays_unresolved(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def provider() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return _llm_payload(UNFAITHFUL_SPL)
        return "not-json"

    candidate, validation = _run_authoring(provider=provider, monkeypatch=monkeypatch)
    assert candidate is not None and validation is not None
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("semantic_fidelity_unresolved") is True
    assert candidate.get("candidate_spl") == ""


def test_f_repair_timeout_stays_unresolved(spl_flags: None, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def provider() -> str:
        calls["n"] += 1
        return _llm_payload(UNFAITHFUL_SPL)

    def fake_fallback(**kwargs: Any):
        if kwargs.get("repair_attempt"):
            return None
        from app.spl.llm_fallback import generate_llm_spl_fallback

        return generate_llm_spl_fallback(
            user_query=kwargs.get("user_query") or DENIED_TOP_SRC_QUERY,
            utility_authoring=True,
            llm_raw_output_provider=provider,
        )

    monkeypatch.setattr("app.spl.utility_spl_authoring.generate_llm_spl_fallback", fake_fallback)
    candidate, validation = _run_authoring(provider=provider, monkeypatch=monkeypatch)
    assert candidate is not None and validation is not None
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("semantic_fidelity_unresolved") is True
    assert candidate.get("candidate_spl") == ""
