from __future__ import annotations

from app.evals.answer_efficacy_checks import (
    evaluate_probe_expectations,
    evaluate_universal_efficacy,
    normalize_action_text,
)


def test_normalize_action_strips_priority_prefix() -> None:
    assert normalize_action_text("P2 — Correlate VPN sessions") == "correlate vpn sessions"


def test_duplicate_actions_detected() -> None:
    payload = {
        "selected_skill": "guided_investigation",
        "analyst_response": {
            "direct_answer_summary": "Guided investigation review-only with signal class identity anomaly.",
            "recommended_actions": [
                "P2 — Check VPN logs",
                "P2 — Check VPN logs",
            ],
            "investigation_steps": ["P2 — Check VPN logs"],
        },
    }
    violations = evaluate_universal_efficacy(query="remote access substation", payload=payload)
    assert any(v.startswith("duplicate_recommended_actions") for v in violations)
    probe_v = evaluate_probe_expectations(
        query="remote access substation",
        payload=payload,
        expect={"no_action_step_overlap": True},
    )
    assert any(v.startswith("action_step_overlap") for v in probe_v)


def test_probe_expectation_signal_class_mismatch() -> None:
    payload = {
        "selected_skill": "guided_investigation",
        "query_to_intent": {"candidate_mappings": {"match_path": "out_of_registry"}},
        "analyst_response": {
            "direct_answer_summary": "signal class network beacon review-only " + ("x" * 300),
            "recommended_actions": ["a", "b", "c"],
        },
    }
    violations = evaluate_probe_expectations(
        query="substation plc telemetry gap",
        payload=payload,
        expect={"signal_class": "identity_anomaly", "forbid_signal_classes": ["network_beacon"]},
    )
    assert any(v.startswith("signal_class_mismatch") for v in violations)
