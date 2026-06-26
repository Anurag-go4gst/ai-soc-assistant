from __future__ import annotations

import json
from types import SimpleNamespace

from app.safeguards.spl_validator import validate_spl
from app.spl.source_profile_catalog import (
    canonical_source_profile_slot,
    list_source_profile_slot_definitions,
)
from app.spl.source_profile_resolver import (
    _pick_sourcetype,
    build_policy_derived_profile,
    extract_placeholder_slots,
    load_static_source_profile,
    substitute_placeholders,
)
from app.spl.rag_source_profile_bridge import extract_rag_source_profile
from app.spl.spl_source_resolve import build_spl_source_profile_review, resolve_spl_source_profile


def test_pick_sourcetype_matches_family_keyword(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.spl_allowed_sourcetypes",
        "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns",
    )
    assert _pick_sourcetype(["pgcil:auth", "pgcil:dns"], ("dns",)) == "pgcil:dns"
    assert _pick_sourcetype(["pgcil:auth", "pgcil:edr"], ("edr", "endpoint")) == "pgcil:edr"


def test_pick_sourcetype_does_not_fallback_to_first_for_network(monkeypatch) -> None:
    """Network/SMB placeholders must stay unresolved — never substitute auth."""
    monkeypatch.setattr(
        "app.config.settings.spl_allowed_sourcetypes",
        "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns",
    )
    assert _pick_sourcetype(["pgcil:auth", "pgcil:edr", "pgcil:dns"], ("traffic", "network", "flow")) is None
    profile = build_policy_derived_profile()
    assert "network_traffic_sourcetype" not in profile


def test_extract_placeholder_slots() -> None:
    spl = "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now | stats count"
    assert extract_placeholder_slots(spl) == ["auth_index", "auth_sourcetype"]


def test_source_profile_catalog_exposes_remote_access_slots() -> None:
    slots = {item["slot_id"]: item for item in list_source_profile_slot_definitions()}
    for slot_id in (
        "jump_host_index",
        "jump_host_sourcetype",
        "pam_index",
        "pam_sourcetype",
        "approved_jump_host_ips",
        "approved_external_systems",
        "substation_mapping_lookup",
        "external_system_registry_lookup",
    ):
        assert slot_id in slots
    assert slots["approved_jump_host_ips"]["category"] == "remote_access"
    assert slots["substation_mapping_lookup"]["category"] == "lookup"
    assert canonical_source_profile_slot("esp_firewall_index") == "firewall_index"
    assert canonical_source_profile_slot("vendor_vpn_zone") == "vpn_pool_zone"


def test_substitute_placeholders_reports_missing() -> None:
    spl = "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now"
    resolved, missing = substitute_placeholders(
        spl,
        {"auth_index": "pgcil_soc"},
    )
    assert "index=pgcil_soc" in resolved
    assert missing == ["auth_sourcetype"]


def test_legacy_remote_access_placeholders_resolve_via_canonical_slots() -> None:
    spl = (
        "search index=<esp_firewall_index> sourcetype=<esp_firewall_sourcetype> "
        "| where src_zone=\"<vendor_vpn_zone>\" AND dest_zone=\"<ot_jump_zone>\" "
        "AND cidrmatch(\"<ot_control_center_cidr>\", dest_ip)"
    )
    resolved, missing = substitute_placeholders(
        spl,
        {
            "firewall_index": "pgcil_soc",
            "firewall_sourcetype": "pgcil:firewall",
            "vpn_pool_zone": "CORP_VPN",
            "jump_host_zone": "I-DMZ",
            "ot_asset_cidr": "10.40.0.0/16",
        },
    )
    assert missing == []
    assert "index=pgcil_soc" in resolved
    assert "sourcetype=pgcil:firewall" in resolved
    assert 'src_zone="CORP_VPN"' in resolved
    assert 'dest_zone="I-DMZ"' in resolved
    assert 'cidrmatch("10.40.0.0/16", dest_ip)' in resolved


def test_legacy_placeholder_missing_reports_canonical_slot() -> None:
    resolved, missing = substitute_placeholders(
        "search index=<esp_firewall_index> sourcetype=<esp_firewall_sourcetype>",
        {},
    )
    assert "<esp_firewall_index>" in resolved
    assert missing == ["firewall_index", "firewall_sourcetype"]


def test_rag_bridge_maps_auth_source() -> None:
    retrieval = {
        "entries": [
            {
                "splunk_indexes": ["pgcil_soc"],
                "sourcetypes": ["pgcil:auth"],
            }
        ]
    }
    profile = extract_rag_source_profile(
        retrieval,
        required_sources=["auth"],
        required_slots=["auth_index", "auth_sourcetype"],
    )
    assert profile["auth_index"] == "pgcil_soc"
    assert profile["auth_sourcetype"] == "pgcil:auth"


def test_resolve_upgrades_lab_placeholder_to_normalized_spl(monkeypatch) -> None:
    monkeypatch.setenv(
        "AI_SOC_SOURCE_PROFILE_MAP",
        json.dumps({"auth_index": "pgcil_soc", "auth_sourcetype": "pgcil:auth"}),
    )
    from app.config import settings
    from app.spl.source_profile_resolver import _explicit_profile_map

    settings.ai_soc_source_profile_map = json.dumps(
        {"auth_index": "pgcil_soc", "auth_sourcetype": "pgcil:auth"}
    )
    _explicit_profile_map.cache_clear()
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> action=failure "
        "earliest=-24h latest=now | stats count by user | sort -count | head 100"
    )
    result = resolve_spl_source_profile(spl, user_query="failed login spike")
    assert result.fully_resolved
    assert result.validation is not None
    assert result.validation["approved"]
    assert result.validation["normalized_spl"]
    assert validate_spl(result.spl)["approved"]


def test_resolve_missing_slots_returns_hil_review() -> None:
    spl = "search index=<ot_segment_a_zone> earliest=-24h latest=now | stats count"
    result = resolve_spl_source_profile(spl, user_query="ot segment crossing")
    assert not result.fully_resolved
    assert "ot_segment_a_zone" in result.missing_slots
    review = build_spl_source_profile_review(result.missing_slots)
    assert review["review_type"] == "spl_source_profile_clarification"
    assert review["required"] is True
    assert "open_source_profile_settings" in review["allowed_actions"]


def test_resolve_revalidation_uses_template_profile(monkeypatch) -> None:
    template = SimpleNamespace(
        validation_rules={
            "allowed_lookups": ["ot_asset_inventory.csv"],
            "allowed_indexes": ["pgcil_soc"],
            "allowed_sourcetypes": ["pgcil:network"],
        }
    )
    monkeypatch.setattr("app.spl.spl_source_resolve.get_spl_template", lambda template_id: template)
    spl = (
        "search index=<network_index> sourcetype=<network_traffic_sourcetype> earliest=-24h latest=now "
        "| lookup ot_asset_inventory.csv ip as dest_ip OUTPUT asset_name "
        "| stats count by asset_name | head 50"
    )
    result = resolve_spl_source_profile(
        spl,
        user_query="asset enrichment",
        session_slots={"network_index": "pgcil_soc", "network_traffic_sourcetype": "pgcil:network"},
        run_mcp_discovery=False,
        template_id="lookup_template",
    )
    assert result.fully_resolved
    assert result.validation is not None
    assert result.validation["approved"] is True


def test_coe_store_wins_over_mcp_discovery(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.spl import source_profile_store as store

    monkeypatch.setattr(settings, "mcp_discovery_enabled", True)
    store_path = tmp_path / "source_profile_map.json"
    monkeypatch.setattr(settings, "ai_soc_source_profile_store_path", str(store_path))
    store.save_persisted_source_profile(
        {"auth_index": "pgcil_soc", "auth_sourcetype": "pgcil:auth"},
        updated_by="coe_ui",
    )
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> action=failure "
        "earliest=-24h latest=now | stats count by user | sort -count | head 100"
    )
    result = resolve_spl_source_profile(spl, user_query="failed login spike")
    assert result.fully_resolved
    assert result.resolved_slots["auth_index"] == "pgcil_soc"
    assert result.slot_sources["auth_index"] == "coe_ui"
    assert "mcp_discovery" in result.tiers_used


def test_mcp_discovery_fills_blank_coe_slots(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.spl import source_profile_store as store

    monkeypatch.setattr(settings, "mcp_discovery_enabled", True)
    store_path = tmp_path / "source_profile_map.json"
    monkeypatch.setattr(settings, "ai_soc_source_profile_store_path", str(store_path))
    store.save_persisted_source_profile({}, updated_by="coe_ui")
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> action=failure "
        "earliest=-24h latest=now | stats count by user | sort -count | head 100"
    )
    result = resolve_spl_source_profile(spl, user_query="failed login spike")
    assert result.fully_resolved
    assert result.resolved_slots["auth_index"] == "pgcil_soc"
    assert result.slot_sources["auth_index"] == "mcp_discovery"
    assert "mcp_discovery" in result.tiers_used


def test_resolve_skips_mcp_when_discovery_disabled(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.spl import source_profile_store as store

    store_path = tmp_path / "source_profile_map.json"
    monkeypatch.setattr(settings, "ai_soc_source_profile_store_path", str(store_path))
    monkeypatch.setattr(settings, "mcp_discovery_enabled", False)
    store.save_persisted_source_profile(
        {"auth_index": "pgcil_soc", "auth_sourcetype": "pgcil:auth"},
        updated_by="coe_ui",
    )
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> action=failure "
        "earliest=-24h latest=now | stats count by user | sort -count | head 100"
    )
    result = resolve_spl_source_profile(spl, user_query="failed login spike", run_mcp_discovery=True)
    assert result.fully_resolved
    assert result.slot_sources["auth_index"] == "coe_ui"
    assert "mcp_discovery" not in result.tiers_used


def test_coe_store_fills_slots_when_mcp_disabled(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.spl import source_profile_store as store

    store_path = tmp_path / "source_profile_map.json"
    monkeypatch.setattr(settings, "ai_soc_source_profile_store_path", str(store_path))
    store.save_persisted_source_profile(
        {"auth_index": "pgcil_soc", "auth_sourcetype": "pgcil:auth"},
        updated_by="coe_ui",
    )
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> action=failure "
        "earliest=-24h latest=now | stats count by user | sort -count | head 100"
    )
    result = resolve_spl_source_profile(spl, user_query="failed login spike", run_mcp_discovery=False)
    assert result.fully_resolved
    assert result.slot_sources["auth_index"] == "coe_ui"
    assert "coe_store" in result.tiers_used


def test_source_resolve_reports_legacy_alias_source_from_canonical_store(monkeypatch, tmp_path) -> None:
    from app.config import settings
    from app.spl import source_profile_store as store

    store_path = tmp_path / "source_profile_map.json"
    monkeypatch.setattr(settings, "ai_soc_source_profile_store_path", str(store_path))
    store.save_persisted_source_profile(
        {
            "firewall_index": "pgcil_soc",
            "firewall_sourcetype": "pgcil:firewall",
            "vpn_pool_zone": "CORP_VPN",
            "jump_host_zone": "I-DMZ",
        },
        updated_by="coe_ui",
    )
    spl = (
        "search index=<esp_firewall_index> sourcetype=<esp_firewall_sourcetype> "
        'earliest=-24h latest=now | where src_zone="<vendor_vpn_zone>" '
        'AND dest_zone="<ot_jump_zone>" | head 100'
    )
    result = resolve_spl_source_profile(spl, user_query="vpn to jump host", run_mcp_discovery=False)
    assert "index=pgcil_soc" in result.spl
    assert "sourcetype=pgcil:firewall" in result.spl
    assert result.missing_slots == []
    assert result.resolved_slots["esp_firewall_index"] == "pgcil_soc"
    assert result.resolved_slots["vendor_vpn_zone"] == "CORP_VPN"
    assert result.slot_sources["esp_firewall_index"] == "coe_ui"
    assert result.slot_sources["vendor_vpn_zone"] == "coe_ui"
