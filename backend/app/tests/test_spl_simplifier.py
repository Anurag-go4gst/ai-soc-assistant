from __future__ import annotations

from app.safeguards.spl_validator import validate_spl
from app.spl.spl_relevance_check import check_spl_relevance
from app.spl.spl_simplifier import simplify_spl, simplify_spl_safe


def test_simplify_drops_table_before_stats() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth action=failure earliest=-60m latest=now "
        "| table user | stats count by user | sort -count"
    )
    result = simplify_spl(spl)
    assert result.applied
    assert "drop_table_before_stats" in result.steps
    assert "| table " not in result.simplified_spl.lower()
    assert "| stats count by user" in result.simplified_spl


def test_simplify_safe_accepts_table_drop_when_relevance_not_checked() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth action=failure earliest=-60m latest=now "
        "| table user | stats count by user | sort -count"
    )
    safe = simplify_spl_safe(spl)
    assert safe.applied
    assert not safe.rejected
    assert "| table " not in safe.simplified_spl.lower()
    assert validate_spl(safe.simplified_spl)["approved"]


def test_simplify_safe_preserves_original_on_relevance_regression() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth action=failure earliest=-60m latest=now "
        "| table user | stats count by user | sort -count"
    )
    safe = simplify_spl_safe(spl, user_query="Which hosts generated the most DNS queries?")
    assert safe.rejected
    assert safe.reject_reason == "relevance_regressed"
    assert safe.simplified_spl == spl.strip()


def test_simplify_safe_noop_when_no_rules_apply() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth action=failure earliest=-60m latest=now "
        "| stats count by user | sort -count | head 100"
    )
    safe = simplify_spl_safe(spl, user_query="failed login spike")
    assert not safe.applied
    assert not safe.rejected
    assert safe.simplified_spl == spl
