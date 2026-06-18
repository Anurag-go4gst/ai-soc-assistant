from __future__ import annotations

from app.chat.intent_classifier import build_candidate_mappings, classify_intent
from app.chat.query_signals import extract_query_signals
from app.coverage.question_runtime_map import list_cisco_question_runtime_entries
from app.query_understanding.parser import understand_query


def test_cisco_metadata_questions_classify_as_knowledge_only_not_spl() -> None:
    rows = {
        row["question_id"]: row
        for row in list_cisco_question_runtime_entries()
        if row.get("pattern_type") == "environment_hygiene"
    }
    assert set(rows) == {f"cisco.endpoint.{n:03d}" for n in range(44, 49)}
    for row in rows.values():
        qu = understand_query(row["question"])
        classification = classify_intent(
            query=row["question"],
            signals=extract_query_signals(row["question"], qu),
            candidate_mappings=build_candidate_mappings(qu),
            query_understanding=qu,
        )
        assert classification.intent_family == "knowledge_only", row["question_id"]
        assert classification.primary_intent == "knowledge_recall", row["question_id"]
        assert "spl_artifact" not in classification.answer_goal, row["question_id"]
