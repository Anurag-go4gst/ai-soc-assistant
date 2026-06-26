from __future__ import annotations

import pytest

from app.config import settings
from app.coverage.question_runtime_map import load_cisco_question_runtime_map
from app.spl.draft_preview import build_draft_preview, match_detection_family

# Part 12.4 wave2 question -> draft family matrix (pattern_type == family_id).
WAVE2_EXPECTED_FAMILY: dict[str, str] = {
    "cisco.perim.002": "cisco_routing_protocol_anomaly",
    "cisco.perim.004": "cisco_ios_port_security",
    "cisco.perim.006": "cisco_firewall_geo_egress",
    "cisco.perim.007": "cisco_sgt_classification_failure",
    "cisco.perim.008": "cisco_icmp_anomaly",
    "cisco.perim.009": "cisco_ios_config_change",
    "cisco.perim.010": "cisco_firewall_dns_bypass",
    "cisco.identity.011": "cisco_tacacs_privilege",
    "cisco.identity.012": "cisco_ise_mab",
    "cisco.identity.013": "cisco_ise_posture",
    "cisco.identity.016": "cisco_ise_quarantine",
    "cisco.identity.017": "cisco_wlc_rogue_ap",
    "cisco.identity.019": "cisco_ise_profile_shift",
    "cisco.identity.020": "cisco_tacacs_stale_session",
    "cisco.ot.021": "ot_goose_burst",
    "cisco.ot.022": "ot_mms_write",
    "cisco.ot.023": "iccp_disconnect",
    "cisco.ot.024": "ot_modbus_exception",
    "cisco.ot.027": "ot_ems_db_change",
    "cisco.ot.028": "ot_dpi_malformed",
    "cisco.ot.029": "ot_solar_setpoint_change",
    "cisco.compliance.031": "ssh_weak_cipher",
    "cisco.compliance.035": "ot_dual_master_conflict",
    "cisco.compliance.036": "ntp_stratum_change",
    "cisco.compliance.038": "agc_frequency_anomaly",
    "cisco.compliance.039": "endpoint_tooling_install",
    "cisco.endpoint.042": "cisco_amp_process_injection",
    "cisco.endpoint.043": "endpoint_hosts_file_change",
}


@pytest.fixture(autouse=True)
def _enable_draft_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)


@pytest.mark.parametrize(
    ("question_id", "expected_family"),
    sorted(WAVE2_EXPECTED_FAMILY.items()),
)
def test_wave2_draft_family_matches_matrix(question_id: str, expected_family: str) -> None:
    entries = {
        row["question_id"]: row
        for row in load_cisco_question_runtime_map(reload=True).get("entries", [])
    }
    entry = entries[question_id]
    assert entry.get("template_wave") == "wave2"

    pattern_type = entry.get("pattern_type")
    assert isinstance(pattern_type, str) and pattern_type
    assert pattern_type == expected_family

    preview = build_draft_preview(
        entry["question"],
        pattern_type=pattern_type,
        spl_validation={"approved": False, "normalized_spl": None},
    )
    assert preview is not None, f"no draft preview for {question_id}"
    assert preview["detection_family"] == expected_family
    assert preview.get("execution_enabled") is False
    assert preview.get("execution_eligible") is False


def test_dns_query_window_paraphrase_routes_to_review_family() -> None:
    paraphrase = "list all dns requests during the observation window"
    assert match_detection_family(paraphrase) == "dns_query_window_review"
    preview = build_draft_preview(
        paraphrase,
        pattern_type="dns_query_window_review",
        spl_validation={"approved": False, "normalized_spl": None},
    )
    assert preview is not None
    assert preview["detection_family"] == "dns_query_window_review"
    assert "stats" in preview["draft_spl"]
    assert "head 100" in preview["draft_spl"]
