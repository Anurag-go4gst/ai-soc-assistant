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


def test_token_spl_has_no_hardcoded_index_or_sourcetype() -> None:
    for spl in (build_scada_threshold_token_spl(), build_cisco_firewall_token_spl()):
        assert "index=<index>" in spl
        assert "<enter_your_" in spl  # analyst-guiding fallback placeholder
        assert "pgcil_soc" not in spl
        assert "cisco:" not in spl
        assert "coalesce(" in spl  # graceful field drift


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
