"""Deferral 3 — tenant-portable token SPL + tenant-aware allowlist."""

from __future__ import annotations

import json

import pytest

from app.spl.policy import load_spl_policy
from app.spl.tenant_token_spl import (
    build_cisco_firewall_token_spl,
    build_scada_threshold_token_spl,
    token_spl_for_validator_profile,
)


def test_token_spl_uses_coe_stems_not_hardcoded() -> None:
    scada = build_scada_threshold_token_spl()
    cisco = build_cisco_firewall_token_spl()
    # Abstract COE placeholder stems (resolved at chat time from the COE map).
    assert "index=<scada_index>" in scada and "sourcetype=<scada_sourcetype>" in scada
    assert "index=<cisco_firewall_index>" in cisco
    assert "sourcetype=<cisco_firewall_sourcetype>" in cisco
    for spl in (scada, cisco):
        assert "pgcil_soc" not in spl and "cisco:" not in spl
        assert "<enter_your_" not in spl  # no literal placeholder fallback; missing -> HIL
        assert "coalesce(" in spl  # graceful field drift (fields are not <> tokens)


def test_token_spl_missing_coe_slot_triggers_hil_not_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env knowledge for the stem -> missing slot (-> HIL), never a hardcoded placeholder."""
    from app.spl import spl_source_resolve as ssr
    from app.spl import source_profile_resolver as spr

    spr._explicit_profile_map.cache_clear()
    monkeypatch.setattr("app.spl.source_profile_resolver.settings.ai_soc_source_profile_map", "")
    # No allowlist-derived env knowledge, no COE store, no discovery.
    monkeypatch.setattr(ssr, "build_policy_derived_profile", lambda: {})
    monkeypatch.setattr(ssr, "load_persisted_source_profile", lambda: {})
    result = ssr.resolve_spl_source_profile(
        build_cisco_firewall_token_spl(), user_query="cisco firewall denies", run_mcp_discovery=False
    )
    spr._explicit_profile_map.cache_clear()
    assert result.fully_resolved is False
    assert any("cisco_firewall" in s for s in result.missing_slots)


def test_coe_env_value_wins_over_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """COE env map (AI_SOC_SOURCE_PROFILE_MAP) is honored at chat time and authoritative."""
    import json as _json
    from app.spl import spl_source_resolve as ssr
    from app.spl import source_profile_resolver as spr

    spr._explicit_profile_map.cache_clear()
    monkeypatch.setattr(
        "app.spl.source_profile_resolver.settings.ai_soc_source_profile_map",
        _json.dumps({"cisco_firewall_sourcetype": "coe:cisco:asa", "cisco_firewall_index": "coe_idx"}),
    )
    # No allowlist auto-derivation and no on-disk COE store, so the env COE map is
    # the authoritative source; discovery would guess something else and must lose.
    monkeypatch.setattr(ssr, "build_policy_derived_profile", lambda: {})
    monkeypatch.setattr(ssr, "load_persisted_source_profile", lambda: {})
    monkeypatch.setattr(
        ssr, "run_mcp_source_discovery",
        lambda **_kw: ({"cisco_firewall_sourcetype": "guessed:st", "cisco_firewall_index": "guessed_idx"}, {}),
    )
    monkeypatch.setattr(ssr.settings, "mcp_discovery_enabled", True)
    result = ssr.resolve_spl_source_profile(
        build_cisco_firewall_token_spl(), user_query="cisco firewall denies", run_mcp_discovery=True
    )
    spr._explicit_profile_map.cache_clear()
    assert "coe:cisco:asa" in result.spl and "coe_idx" in result.spl
    assert "guessed" not in result.spl


def test_token_spl_resolves_by_validator_profile() -> None:
    assert token_spl_for_validator_profile("ot_scada_performance")
    assert token_spl_for_validator_profile("network_firewall")
    assert token_spl_for_validator_profile("unknown_profile") is None
    assert token_spl_for_validator_profile(None) is None


def test_allowlist_global_by_default() -> None:
    policy = load_spl_policy()
    # No tenant -> global SPL_ALLOWED_* policy (single-tenant default).
    assert "pgcil_soc" in policy.allowed_indexes


def test_allowlist_tenant_overlay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.spl.policy.settings.ai_soc_tenant_sourcetype_map",
        json.dumps({"tenantA": {"indexes": ["acme_idx"], "sourcetypes": ["acme:fw"]}}),
    )
    base = load_spl_policy()
    tenant = load_spl_policy(tenant_id="tenantA")
    assert tenant.allowed_indexes == ("acme_idx",)
    assert tenant.allowed_sourcetypes == ("acme:fw",)
    # Unknown tenant falls back to the global policy (byte-identical).
    assert load_spl_policy(tenant_id="ghost").allowed_indexes == base.allowed_indexes


def test_allowlist_unknown_tenant_is_global_when_map_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.spl.policy.settings.ai_soc_tenant_sourcetype_map", "")
    assert load_spl_policy(tenant_id="tenantA").allowed_indexes == load_spl_policy().allowed_indexes
