from __future__ import annotations

from app.spl.mcp_source_discovery import map_discovery_to_profile, run_mcp_source_discovery


def test_map_discovery_to_profile_from_mock_indexes_and_sourcetypes() -> None:
    profile = map_discovery_to_profile(
        indexes=["pgcil_soc"],
        sourcetypes=["pgcil:auth", "pgcil:dns", "pgcil:edr"],
        required_slots=["auth_index", "auth_sourcetype", "dns_sourcetype"],
    )
    assert profile["auth_index"] == "pgcil_soc"
    assert profile["auth_sourcetype"] == "pgcil:auth"
    assert profile["dns_sourcetype"] == "pgcil:dns"


def test_run_mcp_source_discovery_uses_mock_connector() -> None:
    profile, trace = run_mcp_source_discovery(required_slots=["auth_index", "auth_sourcetype"])
    assert "splunk_get_indexes" in trace.get("tools_called", [])
    assert "splunk_get_metadata" in trace.get("tools_called", [])
    assert profile.get("auth_index") == "pgcil_soc"
    assert profile.get("auth_sourcetype") == "pgcil:auth"
