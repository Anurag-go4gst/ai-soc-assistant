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


def test_simplify_preserves_literal_pipe_inside_quoted_regex() -> None:
    # A `|` inside a quoted rex/regex must not be treated as a stage delimiter.
    spl = (
        'search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now '
        '| rex field=_raw "(?<a>foo|bar)" | table user | stats count by user'
    )
    result = simplify_spl(spl)
    assert 'rex field=_raw "(?<a>foo|bar)"' in result.simplified_spl
    assert "| table " not in result.simplified_spl.lower()


def test_simplify_drop_table_before_stats_keeps_table_after_stats() -> None:
    # Only the table stage *before* stats is verbosity; a table stage *after*
    # stats is a real output-projection stage and must survive.
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
        "| table a | stats count by user | table user count"
    )
    result = simplify_spl(spl)
    assert "| table a " not in f" {result.simplified_spl} "
    assert "| table user count" in result.simplified_spl


def test_simplify_smb_where_drop_requires_both_smb_and_app_norm() -> None:
    # A where clause referencing app_norm for an unrelated reason (no %smb%
    # term) must not be dropped just because %smb% appears elsewhere.
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth dest_port=445 earliest=-60m latest=now "
        '| where app_norm!="ftp" | stats count by user'
    )
    result = simplify_spl(spl)
    assert "app_norm" in result.simplified_spl.lower()
    assert "drop_redundant_smb_where" not in result.steps


def test_simplify_converts_post_stats_search_comparison_to_where() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
        "| stats count by host | search count > 5"
    )
    result = simplify_spl(spl)
    assert "convert_post_stats_search_to_where" in result.steps
    assert "| where count > 5" in result.simplified_spl
    assert "| search count > 5" not in result.simplified_spl


def test_simplify_time_bounds_insertion_preserves_quoted_pipe_in_head_stage() -> None:
    # append_default_time_bounds locates the first stage boundary; it must not
    # blind-split on a `|` that lives inside a quoted value in the head stage.
    spl = 'search index=pgcil_soc sourcetype=pgcil:auth title="a|b" | stats count by user'
    result = simplify_spl(spl)
    assert "append_default_time_bounds" in result.steps
    assert 'title="a|b"' in result.simplified_spl
    assert "earliest=-60m latest=now" in result.simplified_spl
    assert "| stats count by user" in result.simplified_spl


def test_simplify_does_not_convert_wildcard_search_after_stats() -> None:
    # `where field="*val*"` does not glob-match like `search` does — converting
    # a wildcarded post-stats search filter to `where` would silently change
    # which rows match.
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
        '| stats values(host) as host by user | search host=*prod*'
    )
    result = simplify_spl(spl)
    assert "convert_post_stats_search_to_where" not in result.steps
    assert "| search host=*prod*" in result.simplified_spl
