"""Unified catalogue T0–T4 adapter tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.catalogue.match_tiers import (
    CatalogueMatchResult,
    match_catalogue_tier,
    normalize_query_aliases,
)

_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "catalogue" / "entries.schema.json"


def test_entries_schema_documents_tiers() -> None:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    tiers = schema["properties"]["tier"]["enum"]
    assert tiers == ["T0", "T1", "T2", "T3", "T4"]


def test_normalize_query_aliases_fixes_failed_login_typo() -> None:
    normalized, changed = normalize_query_aliases("failed lgon spike top users last hour")
    assert changed is True
    assert "login" in normalized
    assert "lgon" not in normalized.lower()


def test_reference_query_maps_to_t0() -> None:
    result = match_catalogue_tier("What is AML.T0043?")
    assert isinstance(result, CatalogueMatchResult)
    assert result.tier == "T0"
    assert result.match_path == "reference_knowledge"
    assert result.use_case_id is None


@pytest.mark.parametrize(
    ("query", "expected_use_case"),
    [
        ("Investigate failed login spike on APP-01", "auth_failed_login_spike"),
        ("Show top users with failed login count in the last 24 hours and exclude service accounts", "auth_failed_login_top_users_exclude_service_accounts"),
    ],
)
def test_use_case_catalog_maps_to_t2(query: str, expected_use_case: str) -> None:
    result = match_catalogue_tier(query)
    assert result.tier in {"T1", "T2", "T3"}
    assert result.use_case_id == expected_use_case


def test_typo_failed_login_query_binds_via_t3_fuzzy_alias() -> None:
    result = match_catalogue_tier("failed lgon spike top users last hour")
    assert result.tier == "T3"
    assert result.alias_applied is True
    assert result.use_case_id in {
        "auth_failed_login_spike",
        "auth_failed_login_top_users_exclude_service_accounts",
    }
    assert result.match_path == "fuzzy_alias_catalog"


def test_out_of_registry_query_maps_to_t4() -> None:
    result = match_catalogue_tier("What is the weather in Paris tomorrow?")
    assert result.tier == "T4"
    assert result.match_path == "out_of_registry"
    assert result.use_case_id is None
