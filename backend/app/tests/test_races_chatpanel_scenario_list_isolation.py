"""EC expanded catalog does not change legacy ChatPanel scenario list."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.demo.fixtures.registry import FLAGSHIP_SCENARIO_IDS
from app.demo.scenarios import list_demo_scenarios, list_experience_center_scenarios
from app.main import app

LEAKED_LAB_IDS = {
    "failed_login_spike_app01",
    "successful_login_after_failures",
    "brute_force_sop_guidance",
    "dns_beaconing_c2_hunt",
    "critical_alerts_mitre_cve_review",
    "ot_modbus_scada_rtu_anomaly",
    "ot_hmi_unauthorized_access",
}

LEGACY_CHATPANEL_IDS = {
    "firewall_deny_coordinated_attack",
    "firewall_baseline_template_spl",
    "splunk_env_asa_ti_readiness",
    "network_blast_radius_attacker_ip",
    "scada_critical_telemetry_health",
    "ir_containment_advisory_firewall_incident",
    "executive_incident_mitre_summary",
    "mitre_mapping_auth_alert",
    "cert_in_ot_reporting_obligation",
    "guided_investigation_supply_chain",
}


def test_ec_expanded_catalog_does_not_change_legacy_chatpanel_scenario_list() -> None:
    legacy_ids = {item["scenario_id"] for item in list_demo_scenarios()}
    assert "Flagship" not in {item["category"] for item in list_demo_scenarios()}
    for scenario_id in FLAGSHIP_SCENARIO_IDS:
        assert scenario_id not in legacy_ids, scenario_id
    for scenario_id in LEAKED_LAB_IDS:
        assert scenario_id not in legacy_ids, scenario_id
    assert LEGACY_CHATPANEL_IDS <= legacy_ids


def test_experience_center_catalog_includes_flagship_and_lab() -> None:
    catalog_ids = {item["scenario_id"] for item in list_experience_center_scenarios()}
    for scenario_id in FLAGSHIP_SCENARIO_IDS:
        assert scenario_id in catalog_ids, scenario_id
    for scenario_id in LEAKED_LAB_IDS:
        assert scenario_id in catalog_ids, scenario_id
    assert "mitre_mapping_auth_alert" in catalog_ids


def test_http_legacy_list_does_not_leak_ec_catalog(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "app_auth_enabled", False)
    client = TestClient(app)
    legacy = client.get("/demo/scenarios")
    assert legacy.status_code == 200
    legacy_ids = {item["scenario_id"] for item in legacy.json()["scenarios"]}
    for scenario_id in (*FLAGSHIP_SCENARIO_IDS, *LEAKED_LAB_IDS):
        assert scenario_id not in legacy_ids, scenario_id

    catalog = client.get("/demo/experience-center/scenarios")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body.get("catalog") == "experience_center"
    catalog_ids = {item["scenario_id"] for item in body["scenarios"]}
    for scenario_id in FLAGSHIP_SCENARIO_IDS:
        assert scenario_id in catalog_ids, scenario_id
    for scenario_id in LEAKED_LAB_IDS:
        assert scenario_id in catalog_ids, scenario_id
