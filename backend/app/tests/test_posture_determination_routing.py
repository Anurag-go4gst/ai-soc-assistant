"""Posture-determination signal: investigation objective → guided, not SPL floor."""

from __future__ import annotations

import pytest

from app.chat.intent_classifier import classify_intent
from app.chat.query_signals import (
    _DETECTION_VERB_RE,
    extract_query_signals,
)
from app.query_understanding.parser import understand_query

_POSITIVE = (
    "Determine whether we are exposed to this campaign.",
    "Assess whether these hosts are affected.",
    "Evaluate whether this activity represents compromise.",
    (
        "A critical zero-day affects our internet-facing VPN gateways. We have no "
        "detection rule or SOAR playbook yet for VPN detection. Determine whether we "
        "are exposed and what immediate controls we should apply."
    ),
)

# Captured against HEAD before this change — must remain unchanged.
_NEGATIVE_PRESERVED = (
    ("Show failed SSH logins.", {"soc_actionable_hunt"}),
    ("Search Splunk for denied firewall traffic.", {"explicit_search_intent"}),
    ("Generate SPL for failed logins.", {"spl_generation"}),
    ("List top source IPs generating denied traffic.", {"soc_actionable_hunt"}),
    ("What is credential stuffing?", {"knowledge_definition"}),
    ("Explain our brute-force SOP.", {"playbook_procedure", "sop_show_request", "guidance_request"}),
)

_NEGATIVE_INTENT_FAMILY = {
    "Show failed SSH logins.": {"spl_generation_only", "live_investigation", "spl_generation_and_run"},
    "Search Splunk for denied firewall traffic.": {
        "spl_generation_only",
        "live_investigation",
        "spl_generation_and_run",
    },
    "Generate SPL for failed logins.": {"spl_generation_only", "spl_generation_and_run"},
    "List top source IPs generating denied traffic.": {
        "spl_generation_only",
        "live_investigation",
        "spl_generation_and_run",
    },
    "What is credential stuffing?": {"knowledge_only"},
    "Explain our brute-force SOP.": {"knowledge_only", "playbook_guidance", "sop_or_playbook"},
}


def _classify(query: str):
    signals = extract_query_signals(query)
    intent = classify_intent(
        query=query,
        signals=signals,
        candidate_mappings={},
        query_understanding=understand_query(query),
    )
    return signals, intent


@pytest.mark.parametrize("query", _POSITIVE)
def test_posture_positive_routes_guided_investigation(query: str) -> None:
    signals, intent = _classify(query)
    assert signals["posture_determination"] is True
    assert intent.intent_family == "guided_investigation"
    assert intent.primary_intent == "investigation_guidance"
    assert intent.action_mode == "recommend_only"
    assert intent.requires_hil is True
    # Investigation objective must not broaden the SPL / live-data floors.
    assert signals["soc_actionable_hunt"] is False
    assert signals["live_data_request"] is False
    assert signals["soc_detection_intent"] is False
    assert not intent.intent_family.startswith("spl_generation")


@pytest.mark.parametrize("query,expected_signals", _NEGATIVE_PRESERVED)
def test_posture_negatives_keep_retrieval_or_knowledge(
    query: str, expected_signals: set[str]
) -> None:
    signals, intent = _classify(query)
    assert signals["posture_determination"] is False
    assert any(signals.get(name) for name in expected_signals), (
        f"expected one of {expected_signals} for {query!r}; got "
        f"hunt={signals.get('soc_actionable_hunt')} "
        f"search={signals.get('explicit_search_intent')} "
        f"spl={signals.get('spl_generation')} "
        f"know={signals.get('knowledge_definition')} "
        f"playbook={signals.get('playbook_procedure')} "
        f"sop={signals.get('sop_show_request')}"
    )
    allowed = _NEGATIVE_INTENT_FAMILY[query]
    assert intent.intent_family in allowed, (
        f"{query!r} routed to {intent.intent_family!r}, expected one of {allowed}"
    )
    assert intent.intent_family != "guided_investigation"


def test_case4_campaign_escalation_not_knowledge_recall_via_gap() -> None:
    """§9.5 case 4: posture False (explicit_search); must not be terminal knowledge_only gap.

    Packet notes this query already trips ``explicit_search_intent``, so
    ``posture_determination`` stays False. Current classifier may still land on
    ``policy_knowledge`` via the escalation keyword — that is a pre-existing
    precedence quirk, out of scope for the posture signal. What this change
    must not do is leave the row on terminal ``knowledge_only`` /
    ``clarification_required`` solely because the objective verb was missing.
    """
    query = (
        "Determine whether the current activity is the same campaign escalated last month."
    )
    signals, intent = _classify(query)
    assert signals["posture_determination"] is False
    assert signals["explicit_search_intent"] is True
    assert intent.intent_family != "knowledge_only"
    assert "Insufficient deterministic intent signals" not in (intent.reason or "")
    assert intent.intent_family in {
        "spl_generation_only",
        "spl_generation_and_run",
        "live_investigation",
        "guided_investigation",
        "clarification_required",
        "policy_knowledge",  # pre-existing escalation-keyword precedence
    }


def test_posture_does_not_imply_hunt_or_live_or_spl() -> None:
    for query in _POSITIVE[:3]:
        signals, intent = _classify(query)
        assert signals["posture_determination"] is True
        assert signals["soc_actionable_hunt"] is False
        assert signals["live_data_request"] is False
        assert not intent.intent_family.startswith("spl_generation")
        assert intent.requested_output_type == "INVESTIGATION"


def test_detection_verb_re_still_rejects_posture_verbs() -> None:
    """Rejected fix must stay rejected: do not widen _DETECTION_VERB_RE."""
    for verb in ("determine", "assess", "evaluate", "ascertain"):
        assert _DETECTION_VERB_RE.search(verb) is None
        assert _DETECTION_VERB_RE.search(f"{verb} whether we are exposed") is None
