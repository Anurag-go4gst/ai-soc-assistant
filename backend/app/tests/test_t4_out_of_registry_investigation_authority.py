"""Out-of-registry investigation-shaped requests must ABSTAIN so T4 can run.

T1–T3 may ACCEPT a complete governed match. They must not declare semantic
completeness merely because a phrase resembles a known detection family, then
collapse a compound investigation into review-only SPL generation.

No query-specific routing keywords. No catalogue entry. Reuses
``detect_investigation_request`` + complete-or-abstain.
"""

from __future__ import annotations

import json

import pytest

from app.chat.resolved_query_builder import build_resolved_query_contract
from app.chat.semantic_t4_understanding import (
    _permits_t4_call,
    abstain_acceptance,
    maybe_enrich_t4_semantic,
)
from app.config import settings
from app.query_understanding.parser import understand_query
from app.query_understanding.soc_investigation_shape import detect_investigation_request
from app.routing.select_route_from_understanding import select_route_from_understanding

# Exact reviewer query — regression pin, not a catalogue row.
_COMPOUND_INVESTIGATION = (
    "A user account logged into a workstation it does not normally use, and shortly "
    "afterward that workstation launched cmd.exe and made outbound connections to an "
    "unfamiliar external IP. Investigate whether these events are related, check the "
    "relevant authentication, endpoint, and network evidence, and tell me whether "
    "this looks like account compromise. Recommend the next action but do not execute "
    "remediation."
)

_SPL_AUTHORING = (
    "Without using any specific company templates, write a standard, universal SPL "
    "block that extracts the hour of the day and day of the week from an event "
    "timestamp, filtering only for weekend events."
)

_DETECTION_FAMILY_NOT_INVESTIGATION = (
    "Flag any Modbus TCP traffic on non-standard ports other than 502"
)

_T1_KNOWN = "What incident or alert network events are high or critical right now?"

_OTHER_UNSEEN = (
    "A contractor VPN session from a city this account has never used was followed "
    "within minutes by a mailbox forwarding-rule change and an OAuth consent grant. "
    "Investigate whether those events are related, check identity, mailbox, and cloud "
    "audit evidence, and tell me whether this looks like account takeover. Recommend "
    "the next action but do not execute remediation.",
    "A previously quiet service account authenticated to a jump host and then that "
    "host started scheduled-task creation plus SMB shares to several file servers. "
    "Investigate whether the authentication, process, and file-share events are one "
    "incident, check the relevant evidence, and tell me whether this looks like "
    "privilege abuse. Recommend the next action but do not execute remediation.",
    "An admin portal login from a new device was followed by firewall-rule edits and "
    "DNS queries to an unregistered domain. Investigate whether login, change, and "
    "DNS events are related, check authentication, change-management, and network "
    "evidence, and tell me whether this looks like a compromised admin. Recommend "
    "the next action but do not execute remediation.",
)


def _t4_contract(query: str, *, tier: str = "T4", source: str | None = None):
    qu = understand_query(query)
    return build_resolved_query_contract(
        query=query,
        query_understanding=qu,
        qualification_tier=tier,  # type: ignore[arg-type]
        qualification_source=source or qu.deterministic_match_path,
    ), qu


def test_compound_investigation_is_investigation_shaped_not_spl_authoring() -> None:
    assert detect_investigation_request(_COMPOUND_INVESTIGATION) is True
    contract, qu = _t4_contract(_COMPOUND_INVESTIGATION)
    assert qu.deterministic_match_path == "out_of_registry"
    assert contract.answer_goal != "spl_artifact"


def test_compound_investigation_abstains_and_permits_t4() -> None:
    contract, _ = _t4_contract(_COMPOUND_INVESTIGATION)
    acceptance = abstain_acceptance(contract)
    assert acceptance.decision == "ABSTAIN"
    assert "not_governed_tier" in acceptance.reason_codes
    assert _permits_t4_call(contract) is True


def test_t4_disabled_keeps_deterministic_guided_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T4-off must not invent a referent handoff that fail-closes investigations."""
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", False)
    contract, _ = _t4_contract(_COMPOUND_INVESTIGATION)
    out = maybe_enrich_t4_semantic(contract, query=_COMPOUND_INVESTIGATION)
    assert out.clarification_required is False
    assert out.understanding_source == "deterministic_qualification"
    assert (out.provenance or {}).get("semantic_t4") is None


def test_compound_investigation_does_not_route_detection_family_spl() -> None:
    qu = understand_query(_COMPOUND_INVESTIGATION)
    route, provenance = select_route_from_understanding(qu, _COMPOUND_INVESTIGATION)
    assert route["skill"] == "guided_investigation"
    assert provenance["authority_source"] != "out_of_registry_detection_family_floor"
    assert "out_of_registry_investigation_request_floor" in (route.get("reasons") or [])
    assert "review_only" not in (route.get("reasons") or [])


def test_compound_investigation_invokes_injected_t4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    contract, _ = _t4_contract(_COMPOUND_INVESTIGATION)
    calls: list[str] = []

    def _provider(query: str, _contract: object) -> str:
        calls.append(query)
        return json.dumps(
            {
                "normalized_goal": (
                    "correlate unusual workstation authentication with subsequent "
                    "cmd.exe execution and outbound connections, then assess "
                    "account-compromise likelihood without executing remediation"
                ),
                "evidence_requirements": [
                    "authentication to the unusual workstation",
                    "cmd.exe / process execution on that workstation",
                    "outbound connections from that workstation to the unfamiliar IP",
                    "temporal and entity correlation across those events",
                ],
                "competing_hypotheses": [
                    "legitimate admin troubleshooting from an unusual workstation",
                    "account compromise leading to interactive execution and callback",
                ],
                "semantic_ambiguity": "unambiguous",
                "clarification_required": False,
                "clarification_reason": None,
                "semantic_confidence": 0.7,
            }
        )

    out = maybe_enrich_t4_semantic(
        contract, query=_COMPOUND_INVESTIGATION, raw_output_provider=_provider
    )
    assert calls == [_COMPOUND_INVESTIGATION]
    trace = (out.provenance or {}).get("semantic_t4") or {}
    assert trace.get("invoked") is True
    assert out.understanding_source == "semantic_t4" or trace.get("accepted") is True
    text = " ".join(
        [
            out.normalized_goal or "",
            " ".join(out.evidence_requirements or []),
            " ".join(out.competing_hypotheses or []),
        ]
    ).lower()
    assert "web shell" not in text
    assert "failed-login" not in text and "failed login spike" not in text
    assert " ot " not in f" {text} "


def test_t4_unavailable_fail_closes_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    contract, _ = _t4_contract(_COMPOUND_INVESTIGATION)
    out = maybe_enrich_t4_semantic(
        contract,
        query=_COMPOUND_INVESTIGATION,
        raw_output_provider=lambda _q, _c: (_ for _ in ()).throw(RuntimeError("down")),
    )
    assert out.clarification_required is True
    assert out.understanding_source == "deterministic_qualification"
    assert str(out.clarification_reason or "").startswith("t4_semantic_unavailable:")


def test_malformed_t4_output_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    contract, _ = _t4_contract(_COMPOUND_INVESTIGATION)
    out = maybe_enrich_t4_semantic(
        contract,
        query=_COMPOUND_INVESTIGATION,
        raw_output_provider=lambda _q, _c: "not-json {{{",
    )
    assert out.clarification_required is True
    assert out.clarification_reason == "t4_semantic_invalid_response"
    assert out.understanding_source == "deterministic_qualification"


def test_t4_cannot_grant_mcp_or_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    contract, _ = _t4_contract(_COMPOUND_INVESTIGATION)
    out = maybe_enrich_t4_semantic(
        contract,
        query=_COMPOUND_INVESTIGATION,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "normalized_goal": "run searches and isolate the host",
                "mcp": "splunk_run_query",
                "execute": True,
                "skill": "spl_generation",
            }
        ),
    )
    assert out.clarification_required is True
    reasons = ((out.provenance or {}).get("semantic_t4") or {}).get("rejected_reasons") or []
    assert "authority_key_present" in reasons
    assert out.understanding_source == "deterministic_qualification"


def test_spl_authoring_still_accepts_and_skips_t4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    contract, _ = _t4_contract(_SPL_AUTHORING)
    assert abstain_acceptance(contract).decision == "ACCEPT"
    assert _permits_t4_call(contract) is False
    calls: list[int] = []
    maybe_enrich_t4_semantic(
        contract,
        query=_SPL_AUTHORING,
        raw_output_provider=lambda _q, _c: calls.append(1) or "{}",
    )
    assert calls == []


def test_detection_family_without_investigation_stays_spl_and_skips_t4() -> None:
    qu = understand_query(_DETECTION_FAMILY_NOT_INVESTIGATION)
    route, provenance = select_route_from_understanding(
        qu, _DETECTION_FAMILY_NOT_INVESTIGATION
    )
    assert route["skill"] == "spl_generation"
    assert provenance["authority_source"] == "out_of_registry_detection_family_floor"
    contract, _ = _t4_contract(_DETECTION_FAMILY_NOT_INVESTIGATION)
    assert _permits_t4_call(contract) is False


def test_known_catalog_investigation_skips_t4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    query = "Investigate failed login spike on APP-01"
    qu = understand_query(query)
    assert qu.deterministic_match_path != "out_of_registry"
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=qu,
        qualification_tier="T2",
        qualification_source=qu.deterministic_match_path,
    )
    calls: list[int] = []

    def _provider(_query: str, _contract: object) -> str:
        calls.append(1)
        return "{}"

    out = maybe_enrich_t4_semantic(contract, query=query, raw_output_provider=_provider)
    assert calls == []
    assert _permits_t4_call(contract) is False or contract.qualification_tier != "T4"
    assert out.understanding_source == "deterministic_qualification"


def test_known_t1_question_skips_t4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t4_semantic_understanding_enabled", True)
    contract, qu = _t4_contract(_T1_KNOWN, tier="T1")
    assert qu.deterministic_match_path == "exact_105_question"
    assert contract.qualification_tier == "T1"
    calls: list[int] = []

    def _provider(_query: str, _contract: object) -> str:
        calls.append(1)
        return "{}"

    out = maybe_enrich_t4_semantic(contract, query=_T1_KNOWN, raw_output_provider=_provider)
    assert calls == []
    assert out.understanding_source == "deterministic_qualification"


@pytest.mark.parametrize("query", _OTHER_UNSEEN)
def test_additional_unseen_investigations_permit_t4_and_avoid_detection_family(
    query: str,
) -> None:
    qu = understand_query(query)
    assert qu.deterministic_match_path == "out_of_registry"
    route, provenance = select_route_from_understanding(qu, query)
    assert route["skill"] == "guided_investigation"
    assert provenance["authority_source"] != "out_of_registry_detection_family_floor"
    contract, _ = _t4_contract(query)
    assert abstain_acceptance(contract).decision == "ABSTAIN"
    assert _permits_t4_call(contract) is True
