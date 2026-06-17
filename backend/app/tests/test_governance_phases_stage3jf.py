from __future__ import annotations

from app.api.routes_chat import chat
from app.demo.scenarios import run_demo_scenario
from app.risk.severity_policy import decide_severity
from app.schemas.requests import ChatRequest
from app.spl.template_registry import get_spl_template, load_spl_templates
from app.threat.mitre_kb import map_mitre_for_use_case, mitre_metadata


def test_spl_templates_are_strict_and_planned_until_scd_exists() -> None:
    templates = load_spl_templates()
    failed = get_spl_template("auth_failed_login_spike")
    firewall = get_spl_template("firewall_deny_spike")

    assert len(templates) >= 10
    assert failed is not None
    assert failed.status == "active"
    assert failed.validation_rules["allowed_indexes"] == ["pgcil_soc"]
    assert failed.validation_rules["allowed_sourcetypes"] == ["pgcil:auth"]
    assert failed.returned_fields == ["host", "src", "failed_logins", "distinct_users", "first_seen", "last_seen", "action"]
    assert "head 100" in (failed.spl_text or "")
    # firewall_deny_spike was promoted to a governed template (WS-B) once the
    # pgcil:firewall sourcetype was added to the allowlist; it is now active and
    # constrained to that single sourcetype/index.
    assert firewall is not None
    assert firewall.status == "active"
    assert firewall.validation_rules["allowed_indexes"] == ["pgcil_soc"]
    assert firewall.validation_rules["allowed_sourcetypes"] == ["pgcil:firewall"]
    assert "head 100" in (firewall.spl_text or "")


def test_local_mitre_kb_is_versioned_and_uses_supported_not_confirmed_for_failed_login() -> None:
    metadata = mitre_metadata()
    mappings = map_mitre_for_use_case("auth_failed_login_spike", ["ev-1"])

    assert metadata["domain"] == "enterprise"
    assert metadata["version"]
    assert metadata["release_date"]
    assert metadata["checksum"]
    t1110 = next(item for item in mappings if item.technique_id == "T1110.001")
    assert t1110.status == "supported"
    assert "confirmation requires" in t1110.why


def test_severity_degrades_when_p1_evidence_is_missing() -> None:
    decision = decide_severity(
        "auth_failed_login_spike",
        {"metrics": {"failed_logins": 51, "distinct_users": 4}},
        ["ev-1"],
    )

    assert decision.severity_label == "P2 High"
    assert "success_after_failure" in decision.missing_evidence
    assert decision.why_not_higher
    assert decision.allowed_action_tier == 1


def test_production_chat_exposes_remaining_phase_metadata_without_enabling_synthesis(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.routing.skill_router.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.workflow_planner.get_telemetry_connector", lambda: _FakeTelemetry())

    response = chat(ChatRequest(message="Show SOP for brute-force investigation"))

    assert response.investigation_lineage is not None
    assert response.investigation_lineage.stages[0].current_mode_source == "live"
    assert response.synthesis_status is not None
    assert response.synthesis_status.enabled is False
    assert response.answer_guard is not None
    assert response.answer_guard.enabled is False
    assert response.action_capability is not None
    assert response.action_capability.current_tier == 1


def test_demo_scenario_exposes_same_metadata_and_never_claims_live_mode() -> None:
    payload = run_demo_scenario("failed_login_spike_app01")

    assert payload["spl_template"]["template_id"] == "auth_failed_login_spike"
    assert payload["mitre_mappings"][0]["status"] == "supported"
    assert payload["severity_decision"]["severity_label"]
    assert payload["synthesis_status"]["enabled"] is False
    assert payload["answer_guard"]["enabled"] is False
    assert payload["action_capability"]["current_tier"] == 1
    assert all(stage["current_mode_source"] != "live" for stage in payload["investigation_lineage"]["stages"])


class _FakeTelemetry:
    def record_routing_decision(self, *args: object, **kwargs: object) -> None:
        return None

    def record_routing_disagreement(self, *args: object, **kwargs: object) -> None:
        return None

    def record_step(self, *args: object, **kwargs: object) -> None:
        return None

    def record_spl_validation(self, *args: object, **kwargs: object) -> None:
        return None
