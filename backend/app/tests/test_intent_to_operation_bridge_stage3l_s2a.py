from __future__ import annotations

from app.routing.intent_to_operation_bridge import (
    INTENT_TO_ALLOWED_PRIMARY_SKILLS,
    evaluate_intent_operation_bridge,
    list_bridge_legacy_intents,
)
from app.routing.skills import SKILL_ENUM


def test_all_skill_enum_intents_have_bridge_mapping() -> None:
    assert set(list_bridge_legacy_intents()) == set(SKILL_ENUM)
    assert set(INTENT_TO_ALLOWED_PRIMARY_SKILLS) == set(SKILL_ENUM)


def test_unknown_legacy_intent_rejected() -> None:
    result = evaluate_intent_operation_bridge("not_a_legacy_intent", "aggregate_and_rank")

    assert result.compatible is False
    assert result.rejection_reason == "unknown_legacy_intent"
    assert not result.disagreements


def test_unknown_primary_skill_rejected() -> None:
    result = evaluate_intent_operation_bridge("attack_discovery", "not_a_runtime_skill")

    assert result.compatible is False
    assert result.rejection_reason == "unknown_primary_skill"


def test_valid_attack_discovery_pair_passes() -> None:
    result = evaluate_intent_operation_bridge("attack_discovery", "sequence_detection")

    assert result.compatible is True
    assert not result.disagreements
    assert "sequence_detection" in result.allowed_primary_skills


def test_invalid_attack_discovery_pair_records_disagreement_not_rewrite() -> None:
    result = evaluate_intent_operation_bridge("attack_discovery", "metadata_discovery")

    assert result.compatible is False
    assert len(result.disagreements) == 1
    entry = result.disagreements[0]
    assert entry["field"] == "intent_to_operation_bridge"
    assert entry["llm_value"] == "metadata_discovery"
    assert entry["deterministic_value"] == "attack_discovery"
    assert "legacy_intent_not_compatible_with_primary_skill" in entry["reason_for_deterministic_win"]


def test_knowledge_recall_allowed_skills_exact_ids() -> None:
    result = evaluate_intent_operation_bridge("knowledge_recall", "metadata_discovery")

    assert result.compatible is True
    assert set(result.allowed_primary_skills) == {
        "metadata_discovery",
        "entity_context_lookup",
        "notable_risk_lookup",
    }


def test_alert_summary_valid_pair() -> None:
    result = evaluate_intent_operation_bridge("alert_summary", "entity_timeline")

    assert result.compatible is True


def test_spl_generation_modifier_no_operation_restriction() -> None:
    for skill in ("aggregate_and_rank", "lookup_correlation", "metadata_discovery"):
        result = evaluate_intent_operation_bridge("spl_generation", skill)

        assert result.compatible is True
        assert result.spl_generation_modifier_detected is True
        assert result.output_artifacts_deferred_to_s2b is True
        assert result.intent_modifier == "candidate_spl_requested"
        assert result.output_artifact_hint == "candidate_spl_visible"
        assert result.underlying_operation == skill
        assert result.allowed_primary_skills == []


def test_spl_generation_unknown_primary_skill_still_rejected() -> None:
    result = evaluate_intent_operation_bridge("spl_generation", "invalid_skill_xyz")

    assert result.compatible is False
    assert result.rejection_reason == "unknown_primary_skill"


def test_null_primary_skill_compatible_when_intent_known() -> None:
    result = evaluate_intent_operation_bridge("knowledge_recall", None)

    assert result.compatible is True
    assert not result.disagreements
