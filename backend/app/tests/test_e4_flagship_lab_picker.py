"""E4 — seven flagships plus lab picker organization."""

from __future__ import annotations

from app.demo.fixtures.registry import FLAGSHIP_SCENARIO_IDS
from app.demo.scenarios import list_demo_scenarios


LAB_IDS = {
    "mitre_mapping_auth_alert",
    "guided_investigation_supply_chain",
    "cert_in_ot_reporting_obligation",
    "scada_critical_telemetry_health",
    "ot_modbus_scada_rtu_anomaly",
    "ot_hmi_unauthorized_access",
    "failed_login_spike_app01",
    "successful_login_after_failures",
    "brute_force_sop_guidance",
    "dns_beaconing_c2_hunt",
}


def test_e4_seven_flagships_and_lab_present() -> None:
    pickable = list_demo_scenarios()
    ids = {item["scenario_id"] for item in pickable}
    for scenario_id in FLAGSHIP_SCENARIO_IDS:
        assert scenario_id in ids, scenario_id
    flagship = [item for item in pickable if item["category"] == "Flagship"]
    assert len(flagship) == 7
    assert [item["scenario_id"] for item in flagship] == list(FLAGSHIP_SCENARIO_IDS)
    present_lab = ids & LAB_IDS
    assert "mitre_mapping_auth_alert" in present_lab
    assert "guided_investigation_supply_chain" in present_lab
    assert "cert_in_ot_reporting_obligation" in present_lab
    assert "scada_critical_telemetry_health" in present_lab
    assert len(present_lab) >= 4
