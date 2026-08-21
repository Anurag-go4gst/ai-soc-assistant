from __future__ import annotations

import pytest

from app.chat.pipeline import build_live_chat_response
from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.resolved_query_builder import apply_session_continuity, attach_understanding_authority
from app.chat.session_context import _generic_scope_delta
from app.schemas.requests import ChatRequest


EXPLICIT_REVIEW_ONLY_SPL = (
    "Give me only a review-only SPL query for index=pgcil_soc and "
    "sourcetype=cisco:firepower for the last 30 days. Do not execute it."
)


@pytest.fixture(autouse=True)
def _allow_firepower_sourcetype(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    allowed_indexes = "pgcil_soc"
    allowed_sourcetypes = "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns,cisco:firepower"
    monkeypatch.setenv("SPL_ALLOWED_INDEXES", allowed_indexes)
    monkeypatch.setenv("SPL_ALLOWED_SOURCETYPES", allowed_sourcetypes)
    monkeypatch.setattr(settings, "spl_allowed_indexes", allowed_indexes)
    monkeypatch.setattr(settings, "spl_allowed_sourcetypes", allowed_sourcetypes)


def test_explicit_review_only_spl_uses_user_bound_artifact_not_catalog_semantics() -> None:
    payload = build_live_chat_response(ChatRequest(message=EXPLICIT_REVIEW_ONLY_SPL)).model_dump(mode="json")

    assert payload["selected_use_case"] is None
    candidate = payload["candidate_spl"]
    spl = candidate["candidate_spl"]
    assert candidate["generation_mode"] == "deterministic_user_bound_skeleton"
    assert "index=pgcil_soc" in spl
    assert "sourcetype=cisco:firepower" in spl
    assert "earliest=-30d latest=now" in spl
    assert "dest_port=80" not in spl
    assert "dest_port=5900" not in spl
    assert "app=HTTP" not in spl
    assert "app=VNC" not in spl
    assert "pgcil:network" not in spl
    assert "phase1_rtu" not in spl
    assert "earliest=-7d" not in spl

    assert payload["spl_validation"]["approved"] is True
    assert payload["execution"]["status"] == "skipped"
    assert payload["execution"]["executed_spl"] is None
    assert payload["human_review"]["required"] is False, payload["human_review"]
    assert payload["run_contract"]["effective_hil_required"] is False
    assert payload["run_contract"]["execution_needed_for_answer"] is False
    assert payload["response_packaging_status"] != "blocked_review_required"
    assert payload["source_evidence"] == []
    assert payload["message"].startswith("Review-only - not executed")


def test_multi_turn_time_replacement_does_not_retain_stale_template_scope() -> None:
    prior = {
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "entities": {
            "source_product": "firepower",
            "sourcetype": "cisco:firepower",
            "time_window": "earliest=-30d latest=now",
        },
        "time_scope": "earliest=-30d latest=now",
    }
    current = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="No, use only the last 3 days.",
            intent_family="clarification_required",
            answer_goal="clarification",
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="scope replacement",
            entities={},
            time_scope="earliest=-3d latest=now",
            qualification_tier="T4",
            qualification_source="out_of_registry",
            confidence=0.2,
        )
    )

    merged = apply_session_continuity(
        current,
        prior_rqc=prior,
        delta_remainder=_generic_scope_delta("no, use only the last 3 days."),
        follow_up_kind="scope_delta",
    )

    assert merged.time_scope == "earliest=-3d latest=now"
    assert merged.entities["time_window"] == "earliest=-3d latest=now"
    assert merged.time_scope != "earliest=-30d latest=now"
    assert "earliest=-30d" not in str(merged.entities)
    assert merged.entities["source_product"] == "firepower"
    assert merged.entities["sourcetype"] == "cisco:firepower"
    assert "dest_port" not in merged.entities
    assert "app" not in merged.entities
    assert "tag" not in merged.entities
    assert "phase1_rtu" not in str(merged.entities).lower()


def test_multi_turn_entity_and_time_replacement_preserves_only_applicable_context() -> None:
    prior = {
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "entities": {
            "dest_ip": ["10.0.0.5"],
            "service": "ssh",
            "action_semantic": "failed_login",
            "time_window": "earliest=-24h latest=now",
        },
        "time_scope": "earliest=-24h latest=now",
    }
    current = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="Actually check 10.0.0.8 for the last 2 hours.",
            intent_family="clarification_required",
            answer_goal="clarification",
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="scope replacement",
            entities={"dest_ip": ["10.0.0.8"]},
            time_scope="earliest=-2h latest=now",
            qualification_tier="T4",
            qualification_source="out_of_registry",
            confidence=0.2,
        )
    )

    merged = apply_session_continuity(
        current,
        prior_rqc=prior,
        delta_remainder=_generic_scope_delta("actually check 10.0.0.8 for the last 2 hours."),
        follow_up_kind="scope_delta",
    )

    assert merged.time_scope == "earliest=-2h latest=now"
    assert merged.entities["dest_ip"] == ["10.0.0.8"]
    assert "10.0.0.5" not in str(merged.entities)
    assert merged.entities["service"] == "ssh"
    assert merged.entities["action_semantic"] == "failed_login"
    assert "dest_port" not in merged.entities
    assert "app" not in merged.entities
    assert "tag" not in merged.entities
