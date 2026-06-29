"""Unit tests for the review-only SPL utility postprocessor (no live LLM)."""

from __future__ import annotations

from app.spl.review_only_spl_postprocessor import normalize_review_only_spl

_CLEAN_SKELETON = """
search index=<your_index> earliest=-24h latest=now
| eval hour_of_day=strftime(_time,"%H")
| eval day_of_week_num=strftime(_time,"%w")
| eval day_of_week=strftime(_time,"%A")
| where day_of_week_num IN ("0","6")
| table _time hour_of_day day_of_week sourcetype host
| head 100
""".strip()

_CANONICAL_WEEKEND_UTILITY = """
index=<your_index> earliest=-24h latest=now
| eval hour_of_day=strftime(_time,"%H")
| eval day_of_week_num=strftime(_time,"%w")
| eval day_of_week=strftime(_time,"%A")
| where day_of_week_num IN ("0","6")
| head 100
| table _time hour_of_day day_of_week sourcetype host
""".strip()



def _ctx(**over):
    base = {
        "is_explicit_spl_authoring": True,
        "is_universal_spl": True,
        "is_template_free": True,
        "deterministic_generated": True,
        "execution_authorized": False,
    }
    base.update(over)
    return base


def test_non_authoring_context_is_noop():
    out = normalize_review_only_spl("index=foo | head 5", {"is_explicit_spl_authoring": False})
    assert out.normalized_spl == "index=foo | head 5"
    assert out.trace["deterministic_postprocessor_applied"] is False


def test_clean_skeleton_polished_to_canonical_weekend_shape():
    out = normalize_review_only_spl(_CLEAN_SKELETON, _ctx())
    assert out.normalized_spl == _CANONICAL_WEEKEND_UTILITY
    assert out.normalized_spl.startswith("index=<your_index> earliest=-24h latest=now")
    assert not out.normalized_spl.lower().startswith("search index=")
    assert out.trace["resolved_index"] == "<your_index>"
    assert out.trace["utility_spl_shape_polish_applied"] is True
    assert out.trace["utility_spl_shape"] == "canonical_weekend_timestamp"
    assert '"%H"' in out.normalized_spl
    assert '"%w"' in out.normalized_spl
    assert '"%A"' in out.normalized_spl
    assert 'day_of_week_num IN ("0","6")' in out.normalized_spl
    assert out.normalized_spl.index("| head 100") < out.normalized_spl.index("| table")
    assert "sort 0" not in out.normalized_spl
    assert "sourcetype=" not in out.normalized_spl.splitlines()[0]


def test_pgcil_soc_weekend_utility_shape_polish():
    out = normalize_review_only_spl(
        _CLEAN_SKELETON.replace("<your_index>", "pgcil_soc"),
        _ctx(coe_generic_utility_default_index="pgcil_soc"),
    )
    assert out.normalized_spl.startswith("index=pgcil_soc earliest=-24h latest=now")
    assert "sourcetype=" not in out.normalized_spl.splitlines()[0]


def test_placeholder_used_when_no_index_mapping():
    spl = "search index=* earliest=-7d latest=now | head 100"
    out = normalize_review_only_spl(spl, _ctx())
    assert "index=<your_index>" in out.normalized_spl
    assert "earliest=-24h latest=now" in out.normalized_spl
    assert out.trace["index_resolution_source"] == "placeholder"


def test_user_explicit_index_preserved():
    out = normalize_review_only_spl(
        "search index=<your_index> earliest=-24h latest=now | head 100",
        _ctx(user_explicit_index="wineventlog"),
    )
    assert "index=wineventlog" in out.normalized_spl
    assert out.trace["index_resolution_source"] == "user_explicit"


def test_coe_environment_index_wins_over_placeholder():
    out = normalize_review_only_spl(
        "search index=<your_index> earliest=-24h latest=now | head 100",
        _ctx(coe_environment_index="soc_main"),
    )
    assert "index=soc_main" in out.normalized_spl
    assert out.trace["index_resolution_source"] == "coe_environment_kb"


def test_source_profile_index_used():
    out = normalize_review_only_spl(
        "search index=<your_index> earliest=-24h latest=now | head 100",
        _ctx(source_profile_index="scada_perf"),
    )
    assert "index=scada_perf" in out.normalized_spl
    assert out.trace["index_resolution_source"] == "source_profile_resolver"


def test_llm_invented_index_dropped_to_placeholder():
    out = normalize_review_only_spl(
        "search index=secret_corp_idx earliest=-24h latest=now | head 100",
        _ctx(llm_generated=True, deterministic_generated=False, target_log_family=""),
    )
    assert "index=<your_index>" in out.normalized_spl
    assert out.trace["raw_llm_index_dropped"] is True


def test_wineventlog_only_when_windows_family():
    # family supports it → kept
    kept = normalize_review_only_spl(
        "search index=wineventlog earliest=-24h latest=now | head 100",
        _ctx(llm_generated=True, target_log_family="windows authentication"),
    )
    assert "index=wineventlog" in kept.normalized_spl
    assert kept.trace["index_resolution_source"] == "draft_family_supported"
    # no windows family → dropped
    dropped = normalize_review_only_spl(
        "search index=wineventlog earliest=-24h latest=now | head 100",
        _ctx(llm_generated=True, target_log_family="generic"),
    )
    assert "index=<your_index>" in dropped.normalized_spl


def test_wide_lookback_shrunk_for_placeholder():
    out = normalize_review_only_spl(
        "search index=<your_index> earliest=-30d latest=now | head 100",
        _ctx(),
    )
    assert "earliest=-24h" in out.normalized_spl
    assert out.trace["lookback_rewrite_applied"] is True


def test_user_explicit_long_lookback_preserved_with_warning():
    out = normalize_review_only_spl(
        "search index=<your_index> earliest=-30d latest=now | head 100",
        _ctx(user_explicit_time_window=True),
    )
    assert "earliest=-30d" in out.normalized_spl
    assert "broad_scope_warning" in out.warnings


def test_sort_zero_before_filter_removed():
    spl = (
        "search index=<your_index> earliest=-24h latest=now\n"
        "| sort 0 -_time\n"
        '| eval day_of_week_num=strftime(_time,"%w")\n'
        '| where day_of_week_num IN ("0","6")\n'
        "| head 100"
    )
    out = normalize_review_only_spl(spl, _ctx())
    assert "sort 0" not in out.normalized_spl
    assert out.trace["command_reorder_applied"] is True
    # dependency preserved: where stays after its eval
    body = out.normalized_spl
    assert body.index("eval day_of_week_num") < body.index("where day_of_week_num")


def test_locale_name_filter_normalized_to_pct_w():
    spl = (
        "search index=<your_index> earliest=-24h latest=now\n"
        '| eval day_of_week=strftime(_time,"%A")\n'
        '| where day_of_week="Saturday"\n'
        "| head 100"
    )
    out = normalize_review_only_spl(spl, _ctx(llm_generated=True))
    assert out.trace["locale_normalization_applied"] is True
    assert out.trace["display_field_preserved"] is True
    assert 'day_of_week_num IN ("0","6")' in out.normalized_spl
    assert 'where day_of_week="Saturday"' not in out.normalized_spl


def test_pct_a_display_preserved_when_pct_w_present():
    out = normalize_review_only_spl(_CLEAN_SKELETON, _ctx())
    assert '"%A"' in out.normalized_spl
    assert out.trace["locale_normalization_applied"] is False


def test_execution_never_authorized_field_untouched():
    out = normalize_review_only_spl(_CLEAN_SKELETON, _ctx())
    # postprocessor never emits an execution-authorizing claim
    assert "execution_authorized" not in out.normalized_spl.lower()


def test_sort_hundred_before_filter_removed():
    spl = (
        "search index=<your_index> earliest=-24h latest=now\n"
        "| sort 100 -_time\n"
        '| eval day_of_week_num=strftime(_time,"%w")\n'
        '| where day_of_week_num IN ("0","6")\n'
        "| head 100"
    )
    out = normalize_review_only_spl(spl, _ctx())
    assert "sort 100" not in out.normalized_spl
    assert out.trace["command_reorder_applied"] is True
