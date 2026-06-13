from __future__ import annotations

import json

from app.safeguards.spl_validator import validate_spl
from app.spl.source_profile_resolver import (
    extract_placeholder_slots,
    load_static_source_profile,
    substitute_placeholders,
)
from app.spl.rag_source_profile_bridge import extract_rag_source_profile
from app.spl.spl_source_resolve import build_spl_source_profile_review, resolve_spl_source_profile


def test_extract_placeholder_slots() -> None:
    spl = "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now | stats count"
    assert extract_placeholder_slots(spl) == ["auth_index", "auth_sourcetype"]


def test_substitute_placeholders_reports_missing() -> None:
    spl = "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now"
    resolved, missing = substitute_placeholders(
        spl,
        {"auth_index": "pgcil_soc"},
    )
    assert "index=pgcil_soc" in resolved
    assert missing == ["auth_sourcetype"]


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
