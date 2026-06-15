from __future__ import annotations

from app.demo.scenarios import run_demo_scenario


def test_critical_alerts_scenario_runs_with_governance_posture() -> None:
    payload = run_demo_scenario("critical_alerts_mitre_cve_review")

    assert payload["selected_skill"] == "attack_discovery"
    assert payload["selected_use_case"]["use_case_id"] == "critical_notable_mitre_review"
    provenance = payload["control_plane_trace"]["experience_center_provenance"]
    assert provenance["future_state_preview"] is False
    assert provenance["live_llm_called"] is False
    assert provenance["live_mcp_called"] is False


def test_critical_alerts_no_fabricated_cve_rows() -> None:
    payload = run_demo_scenario("critical_alerts_mitre_cve_review")
    for item in payload["source_evidence"]:
        for row in item.get("preview_rows") or []:
            assert "cve_id" not in row
            assert "cvss" not in row
            assert "cve" not in {str(key).lower() for key in row.keys()}


def test_critical_alerts_mitre_and_risk_rankings() -> None:
    payload = run_demo_scenario("critical_alerts_mitre_cve_review")
    mitre_decision = payload["mitre_decision"]
    technique_ids = {
        str(item.get("technique_id") or item.get("Technique") or "")
        for item in mitre_decision.get("techniques") or []
    }
    assert len(technique_ids) >= 2

    analyst = payload["analyst_response"]
    assert len(analyst.get("mitre_mappings") or []) >= 2
    top_hosts = analyst.get("top_risky_hosts") or []
    assert len(top_hosts) >= 2
    assert top_hosts[0]["Host"] == "VPN-GW-01"
    assert top_hosts[0]["Risk score"] > top_hosts[1]["Risk score"]


def test_critical_alerts_cve_degrade_resource_plan_present() -> None:
    payload = run_demo_scenario("critical_alerts_mitre_cve_review")
    steps = (payload["evidence_plan"].get("resource_plan") or {}).get("steps") or []
    vuln_steps = [step for step in steps if step.get("resource") == "vulnerability_source"]
    assert vuln_steps
    assert vuln_steps[0]["status"] == "not_onboarded"
    assert "vulnerability_source" in (payload["evidence_plan"].get("missing_evidence") or [])

    analyst = payload["analyst_response"]
    limitations = " ".join(analyst.get("limitations") or []).lower()
    assert "not onboarded" in limitations or "vulnerability" in limitations


def test_critical_alerts_mcp_tool_plan_shadow_ec_parity() -> None:
    payload = run_demo_scenario("critical_alerts_mitre_cve_review")
    shadow = payload["control_plane_trace"].get("mcp_tool_plan_shadow")
    assert shadow is not None
    assert shadow["shadow_only"] is True
    assert shadow["promotion_blocked"] is True
    assert shadow["rbac_role"] == "analyst"
    assert shadow["approved_tools"][-1] == "splunk_run_query"
    assert payload["llm_sidecars"]["mcp_tool_plan_shadow"] == shadow
    panel = payload["experience_center_governance"]["llm_sidecar_panel"]
    assert isinstance(panel.get("mcp_tool_plan_shadow"), str)
    assert "splunk_run_query" not in panel["mcp_tool_plan_shadow"]  # summary prose, not raw tool list
    assert "RBAC role analyst" in panel["mcp_tool_plan_shadow"]
