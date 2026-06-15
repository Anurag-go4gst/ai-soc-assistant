"""Regression: catalog use-case matches must not collapse to clarification_required.

Before the rescue branch, any query that matched a registry use case but not an
exact-105 question fell through to clarification_required, which the route
adjudicator then forced to knowledge_recall — so alert-summary, attack-discovery,
and in-catalog hunt queries all mis-classified as knowledge_recall.
"""

from __future__ import annotations

import pytest

from app.chat.intent_classifier import build_query_to_intent
from app.query_understanding.parser import understand_query

_CATALOG_INVESTIGATION_QUERIES = [
    "Summarize the failed login spike alert for user jdoe in the last hour",
    "Are there signs of lateral movement across our windows hosts today?",
    "Help me hunt for unusual outbound DNS tunneling we have no detection for",
]


@pytest.mark.parametrize("query", _CATALOG_INVESTIGATION_QUERIES)
def test_catalog_match_not_clarification(query: str) -> None:
    understanding = understand_query(query)
    result = build_query_to_intent(query=query, query_understanding=understanding)
    intent = result.intent_classification
    # Must reach a real investigation family, not the clarification default.
    assert intent.intent_family != "clarification_required", query
    assert intent.requires_clarification is False, query
    assert intent.confidence_band in {"medium", "high"}, query


def test_alert_summary_shape_maps_to_hybrid_alert_review() -> None:
    understanding = understand_query(
        "Summarize the failed login spike alert for user jdoe in the last hour"
    )
    result = build_query_to_intent(query="Summarize the failed login spike alert for user jdoe in the last hour", query_understanding=understanding)
    assert result.intent_classification.intent_family == "hybrid_alert_review"


def test_catalog_knowledge_query_stays_knowledge_not_investigation() -> None:
    # A MITRE/knowledge use-case match must classify as knowledge, not investigation.
    understanding = understand_query("What does MITRE ATT&CK T1110 cover?")
    result = build_query_to_intent(query="What does MITRE ATT&CK T1110 cover?", query_understanding=understanding)
    assert result.intent_classification.intent_family in {"knowledge_only", "mitre_explanation"}


def test_alert_with_mitre_context_is_alert_review_not_knowledge() -> None:
    # explicit_mitre_context on an alert query must NOT divert it to knowledge.
    q = "Summarize the failed login spike alert for user jdoe in the last hour"
    result = build_query_to_intent(query=q, query_understanding=understand_query(q))
    assert result.intent_classification.intent_family == "hybrid_alert_review"


def test_truly_ambiguous_query_still_clarifies() -> None:
    # No registry use-case match → clarification default must still apply.
    understanding = understand_query("hello what can you do for me exactly")
    result = build_query_to_intent(query="hello what can you do for me exactly", query_understanding=understanding)
    intent = result.intent_classification
    assert intent.intent_family == "clarification_required"
    assert intent.requires_clarification is True
