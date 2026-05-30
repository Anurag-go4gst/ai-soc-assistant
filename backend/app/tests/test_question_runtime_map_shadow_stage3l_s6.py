"""Stage 3L-S6.1: Question runtime map on route_plan_shadow (observational)."""

from __future__ import annotations

from app.coverage.question_runtime_map_shadow import apply_question_runtime_map_to_shadow


def test_shadow_enriches_cov_q046_map_row() -> None:
    shadow = {
        "pattern_id": "top_failed_okta_login_users",
        "route_authority_compare": {
            "coverage_id_resolved": "cov.q046.excessive_failed_logins_sample",
        },
    }
    payload = apply_question_runtime_map_to_shadow(shadow)
    assert payload is not None
    assert payload["map_entry_found"] is True
    assert payload["question_ref"] == "q0.q046"
    assert payload["observation_only"] is True
    assert shadow["question_runtime_map"]["proposed_primary_skill"] == "threshold_anomaly"


def test_shadow_map_does_not_mutate_primary_skill() -> None:
    shadow = {
        "primary_skill": "attack_discovery",
        "pattern_id": "top_failed_okta_login_users",
        "route_authority_compare": {
            "coverage_id_resolved": "cov.q046.excessive_failed_logins_sample",
        },
    }
    apply_question_runtime_map_to_shadow(shadow)
    assert shadow["primary_skill"] == "attack_discovery"
