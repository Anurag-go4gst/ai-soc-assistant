from __future__ import annotations

from app.chat.intent_classifier import classify_intent
from app.chat.planning_decision import _resolve_path_type
from app.chat.query_signals import extract_query_signals
from app.query_understanding.parser import understand_query


def test_explicit_run_spl_routes_spl_review_not_unsafe_blocked() -> None:
    query = "Run the SPL and give me results."
    signals = extract_query_signals(query)
    intent = classify_intent(
        query=query,
        signals=signals,
        candidate_mappings={},
        query_understanding=understand_query(query),
    ).model_dump()
    qu = understand_query(query)
    path = _resolve_path_type(intent, {"needs_spl": True}, {}, None, qu)
    assert path == "spl_review"


def test_containment_still_routes_unsafe_blocked() -> None:
    query = "Block this IP on the firewall immediately."
    signals = extract_query_signals(query)
    intent = classify_intent(
        query=query,
        signals=signals,
        candidate_mappings={},
        query_understanding=understand_query(query),
    ).model_dump()
    qu = understand_query(query)
    path = _resolve_path_type(intent, {}, {}, None, qu)
    assert path == "unsafe_blocked"
