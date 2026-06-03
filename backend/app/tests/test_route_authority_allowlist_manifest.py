from __future__ import annotations

from app.routing.route_authority_allowlist import (
    ALLOWLISTABLE_COVERAGE_IDS,
    BLOCKED_AUTHORITY_COVERAGE_IDS,
    COV_Q046_PILOT_COVERAGE_ID,
    validate_allowlist_ids,
)


def test_manifest_coverage_ids_allowlistable_except_blocked() -> None:
    assert COV_Q046_PILOT_COVERAGE_ID in ALLOWLISTABLE_COVERAGE_IDS
    assert "cov.q002.top_outbound_source_ips" in ALLOWLISTABLE_COVERAGE_IDS
    for blocked in BLOCKED_AUTHORITY_COVERAGE_IDS:
        assert blocked not in ALLOWLISTABLE_COVERAGE_IDS


def test_validate_allowlist_accepts_manifest_subset() -> None:
    validate_allowlist_ids(frozenset({COV_Q046_PILOT_COVERAGE_ID, "cov.q002.top_outbound_source_ips"}))
