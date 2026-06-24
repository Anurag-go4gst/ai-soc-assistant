"""Experience Center overhaul tests (plan 2026-06-24): resolver aliasing + fail-fast
uniqueness, curated registry, capture loader + fallback, and the multi-turn MITRE FSM.

These exercise only the EC fixture path; no live LLM/MCP is called.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.demo import ec_fsm_store
from app.demo import scenarios as S
from app.demo.capture_loader import (
    CAPTURE_SCHEMA_VERSION,
    CaptureArtifactError,
    capture_path_for,
    load_capture_artifact,
    normalize_stage_latencies,
)

_MITRE_TURN1 = "Map this alert to MITRE"
_MITRE_TURN2 = (
    "Map this alert to MITRE: notable signature=brute_force_success_after_failures "
    "index=pgcil_soc sourcetype=pgcil:auth host=APP-01"
)


@pytest.fixture(autouse=True)
def _reset_fsm() -> None:
    ec_fsm_store.clear_all_for_tests()
    yield
    ec_fsm_store.clear_all_for_tests()


# --- Phase 2: curated registry --------------------------------------------------


def test_registry_has_ten_pickable_scenarios() -> None:
    pickable = S.list_demo_scenarios()
    assert len(pickable) == 10
    # The clarification (fsm_step==0) turn is internal, not pickable.
    ids = {item["scenario_id"] for item in pickable}
    assert "mitre_mapping_requires_context" not in ids
    assert "mitre_mapping_auth_alert" in ids


def test_categories_match_plan_buckets() -> None:
    categories = {item["category"] for item in S.list_demo_scenarios()}
    expected = {
        "Alert Triage",
        "Threat Hunt",
        "SPL",
        "MITRE",
        "Knowledge & Compliance",
        "OT/ICS",
        "Guided (out-of-catalog)",
    }
    assert categories == expected


def test_breadth_includes_ot_and_regulatory() -> None:
    ids = set(S.SCENARIOS.keys())
    assert "cert_in_ot_reporting_obligation" in ids
    assert "ot_modbus_scada_rtu_anomaly" in ids
    assert "ot_hmi_unauthorized_access" in ids


def test_auth_near_duplicates_removed() -> None:
    ids = set(S.SCENARIOS.keys())
    for removed in (
        "new_source_ip_logins",
        "account_lockouts_over_time_spl",
        "successful_login_after_failures_run",
        "airgapped_no_saia_success_after_failures",
        "mcp_metadata_discovery_app01",
        "dns_beaconing_c2_hunt_run",
    ):
        assert removed not in ids


# --- Phase 1 / Track D1: resolver aliasing + fail-fast uniqueness ---------------


def test_every_query_and_alias_resolves_to_exactly_one_scenario() -> None:
    for scenario in S.SCENARIOS.values():
        for phrase in (scenario.query, *scenario.aliases):
            resolved = S.resolve_demo_scenario_id_for_query(phrase)
            # fsm_step==0 (clarification) resolves to itself; others to themselves.
            assert resolved == scenario.scenario_id, (phrase, resolved)


def test_no_alias_overlap_across_scenarios() -> None:
    seen: dict[str, str] = {}
    for scenario in S.SCENARIOS.values():
        for phrase in (scenario.query, *scenario.aliases):
            normalized = S._normalize_query(phrase)
            assert normalized not in seen or seen[normalized] == scenario.scenario_id, (
                normalized,
                seen.get(normalized),
                scenario.scenario_id,
            )
            seen[normalized] = scenario.scenario_id


def test_build_alias_index_fails_fast_on_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    a = next(iter(S.SCENARIOS.values()))
    b = next(s for s in S.SCENARIOS.values() if s.scenario_id != a.scenario_id)
    # Force a collision: give b an alias equal to a's query.
    colliding = b.__class__(**{**b.__dict__, "aliases": (a.query,)})
    patched = dict(S.SCENARIOS)
    patched[b.scenario_id] = colliding
    monkeypatch.setattr(S, "SCENARIOS", patched)
    with pytest.raises(RuntimeError, match="alias collision"):
        S._build_alias_index()


def test_unknown_query_resolves_to_none() -> None:
    assert S.resolve_demo_scenario_id_for_query("what is the capital of france") is None


# --- Phase 4 / Track D2: multi-turn MITRE FSM -----------------------------------


def test_mitre_fsm_turn1_then_turn2_happy_path() -> None:
    session = "sess-happy"
    assert (
        S.resolve_demo_scenario_id_for_query(_MITRE_TURN1, session_id=session)
        == "mitre_mapping_requires_context"
    )
    assert (
        S.resolve_demo_scenario_id_for_query(_MITRE_TURN2, session_id=session)
        == "mitre_mapping_auth_alert"
    )


def test_mitre_fsm_partial_turn2_reclarifies() -> None:
    session = "sess-partial"
    S.resolve_demo_scenario_id_for_query(_MITRE_TURN1, session_id=session)
    # No signature / insufficient fields -> re-serve clarification, not a wrong scenario.
    assert (
        S.resolve_demo_scenario_id_for_query(
            "please just map it for me", session_id=session
        )
        == "mitre_mapping_requires_context"
    )


def test_mitre_fsm_sessions_isolated() -> None:
    S.resolve_demo_scenario_id_for_query(_MITRE_TURN1, session_id="S1")
    # A different session asking an unrelated question is unaffected by S1's FSM state.
    assert (
        S.resolve_demo_scenario_id_for_query(
            "Investigate failed login spike on APP-01", session_id="S2"
        )
        == "failed_login_spike_app01"
    )


def test_mitre_fsm_new_turn1_resets_step() -> None:
    session = "sess-reset"
    S.resolve_demo_scenario_id_for_query(_MITRE_TURN1, session_id=session)
    # A fresh turn-1 keeps the family awaiting input (does not advance to the answer).
    assert (
        S.resolve_demo_scenario_id_for_query(_MITRE_TURN1, session_id=session)
        == "mitre_mapping_requires_context"
    )
    # Then a valid turn-2 still advances.
    assert (
        S.resolve_demo_scenario_id_for_query(_MITRE_TURN2, session_id=session)
        == "mitre_mapping_auth_alert"
    )


def test_mitre_fsm_unrelated_query_is_not_hijacked() -> None:
    """A different scenario typed mid-clarification must win, not re-clarify.

    Regression: an awaiting MITRE family used to re-serve its clarification for ANY
    non-context query, trapping every subsequent unrelated question in the session.
    """
    session = "sess-no-trap"
    assert (
        S.resolve_demo_scenario_id_for_query(_MITRE_TURN1, session_id=session)
        == "mitre_mapping_requires_context"
    )
    # Same session, but an exact match for a different scenario — must resolve to it.
    assert (
        S.resolve_demo_scenario_id_for_query(
            "Hunt for possible DNS beaconing or C2 from internal hosts in the last 24 hours",
            session_id=session,
        )
        == "dns_beaconing_c2_hunt"
    )
    # The stale family is now reset: a fresh turn-1 starts it cleanly again.
    assert (
        S.resolve_demo_scenario_id_for_query(_MITRE_TURN1, session_id=session)
        == "mitre_mapping_requires_context"
    )


def test_every_curated_canonical_query_resolves_to_itself() -> None:
    """Each pickable scenario's own button text must resolve back to it (fresh session)."""
    for scenario_id, scenario in S.SCENARIOS.items():
        query = getattr(scenario, "query", None)
        if not query:
            continue
        resolved = S.resolve_demo_scenario_id_for_query(
            query, session_id=f"canon-{scenario_id}"
        )
        assert resolved == scenario_id, f"{scenario_id} resolved to {resolved}"


def test_other_scenarios_are_one_shot() -> None:
    session = "sess-oneshot"
    first = S.resolve_demo_scenario_id_for_query(
        "Hunt for possible DNS beaconing or C2 from internal hosts in the last 24 hours",
        session_id=session,
    )
    assert first == "dns_beaconing_c2_hunt"
    # Re-asking resolves identically; no FSM state lingers for one-shot scenarios.
    assert (
        S.resolve_demo_scenario_id_for_query(
            "Hunt for possible DNS beaconing or C2 from internal hosts in the last 24 hours",
            session_id=session,
        )
        == "dns_beaconing_c2_hunt"
    )


# --- Phase 3 / B2.1: capture loader + fallback ----------------------------------


def test_every_scenario_has_artifact_or_working_legacy_fixture() -> None:
    for scenario_id in S.SCENARIOS:
        # Either a schema-valid artifact loads, or the legacy fixture renders a body.
        try:
            artifact = load_capture_artifact(scenario_id)
        except CaptureArtifactError as exc:  # pragma: no cover - guards a broken artifact
            pytest.fail(f"artifact for {scenario_id} is invalid: {exc}")
        out = S.run_demo_scenario(scenario_id)
        assert out.get("message"), scenario_id
        assert out["live_llm_called"] is False
        assert out["live_mcp_called"] is False
        assert out["evidence_origin"] == "coe_synthetic_fixture"
        assert out["ec_answer_source"] in {"captured_artifact", "legacy_fixture"}
        if artifact is not None:
            assert out["ec_answer_source"] == "captured_artifact"


def test_corrupt_artifact_falls_back_to_legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scenario_id = "guided_investigation_supply_chain"  # known to have no artifact -> legacy
    # Point the loader at a temp captures dir and drop a corrupt file there.
    monkeypatch.setattr("app.demo.capture_loader.CAPTURES_DIR", tmp_path)
    (tmp_path / f"{scenario_id}.json").write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(CaptureArtifactError):
        load_capture_artifact(scenario_id)
    # The serving path swallows the error and serves the legacy fixture.
    out = S.run_demo_scenario(scenario_id)
    assert out["ec_answer_source"] == "legacy_fixture"
    assert out.get("message")


def test_schema_version_mismatch_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.demo.capture_loader.CAPTURES_DIR", tmp_path)
    artifact = _minimal_artifact()
    artifact["schema_version"] = CAPTURE_SCHEMA_VERSION + 99
    (tmp_path / "x.json").write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(CaptureArtifactError, match="schema_version"):
        load_capture_artifact("x")


def test_artifact_with_volatile_keys_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.demo.capture_loader.CAPTURES_DIR", tmp_path)
    artifact = _minimal_artifact()
    artifact["final_response"]["trace_id"] = "pinned"
    (tmp_path / "x.json").write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(CaptureArtifactError, match="trace_id"):
        load_capture_artifact("x")


def test_missing_artifact_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.demo.capture_loader.CAPTURES_DIR", tmp_path)
    assert load_capture_artifact("nope") is None


def test_normalize_stage_latencies_caps_replayed_ms() -> None:
    stages = normalize_stage_latencies(
        [
            {"stage": "llm", "recorded_ms": 120000},
            {"stage": "route", "recorded_ms": 1200},
        ]
    )
    assert stages[0]["replayed_ms"] == 6000
    assert stages[0]["recorded_ms"] == 120000  # honesty: real value retained
    assert stages[1]["replayed_ms"] == 1200


def test_served_artifact_restamps_ids_and_keeps_posture() -> None:
    scenario_id = "failed_login_spike_app01"
    if not capture_path_for(scenario_id).is_file():
        pytest.skip("no captured artifact present for restamp check")
    a = S.run_demo_scenario(scenario_id)
    b = S.run_demo_scenario(scenario_id)
    assert a["trace_id"] != b["trace_id"]  # fresh per run
    assert a["ec_answer_source"] == "captured_artifact"
    assert a["live_llm_called"] is False and a["live_mcp_called"] is False
    assert a["ec_provenance"]["mcp_label"] == "simulated MCP lifecycle replay"


def _minimal_artifact() -> dict[str, Any]:
    return {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "final_response": {"message": "hi", "analyst_response": {}},
        "stage_latencies": [{"stage": "end_to_end", "recorded_ms": 100}],
        "provenance": {
            "model_id": "m",
            "captured_at": "2026-06-24T00:00:00Z",
            "transport": "fake",
            "live_llm_called": False,
            "live_mcp_called": False,
        },
    }
