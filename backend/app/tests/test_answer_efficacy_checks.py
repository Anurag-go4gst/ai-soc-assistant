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


def _base_payload_with_run_contract() -> dict:
    return {
        "message": "Review-only / no live execution.",
        "route_authority": {"authority_holder": "canonical_run_contract"},
        "run_contract": {
            "execution_status": "skipped",
            "collected_evidence_count": 0,
            "source_evidence_available": False,
            "allow_live_result_language": False,
            "allow_results_table": False,
            "effective_hil_required": True,
            "routing": {
                "canonical_skill": "spl_generation",
                "legacy_skill": None,
                "legacy_authoritative": False,
                "authority_holder": "canonical_run_contract",
            },
        },
        "analyst_response": {
            "direct_answer_summary": "Review-only SPL draft - no live query was executed.",
            "severity_label": "Not assigned from this question alone",
            "recommended_actions": ["Confirm source profile"],
            "splunk_results_table": [],
        },
    }


def test_universal_efficacy_requires_run_contract() -> None:
    payload = {"message": "Review-only / no live execution.", "analyst_response": {}}
    violations = evaluate_universal_efficacy(query="show substation sessions", payload=payload)
    assert "run_contract_missing" in violations


def test_universal_efficacy_blocks_live_backed_without_execution() -> None:
    payload = _base_payload_with_run_contract()
    payload["message"] = "How this answer was produced: live-backed"
    violations = evaluate_universal_efficacy(query="show substation sessions", payload=payload)
    assert "live_backed_without_execution" in violations


def test_universal_efficacy_blocks_disallowed_results_table() -> None:
    payload = _base_payload_with_run_contract()
    payload["analyst_response"]["splunk_results_table"] = [{"src": "10.0.0.1"}]
    violations = evaluate_universal_efficacy(query="show substation sessions", payload=payload)
    assert "results_table_not_allowed" in violations


def test_universal_efficacy_blocks_route_authority_contradiction() -> None:
    payload = _base_payload_with_run_contract()
    payload["route_authority"] = {"authority_holder": "legacy_selected_skill"}
    violations = evaluate_universal_efficacy(query="show substation sessions", payload=payload)
    assert "route_authority_holder_contradiction" in violations


def test_universal_efficacy_blocks_priority_prefix_without_severity() -> None:
    payload = _base_payload_with_run_contract()
    payload["analyst_response"]["recommended_actions"] = ["P2 — Confirm firewall owner"]
    violations = evaluate_universal_efficacy(query="show substation sessions", payload=payload)
    assert "priority_prefix_without_severity" in violations
