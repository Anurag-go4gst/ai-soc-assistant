"""OPTIONAL_PHASE_S H3 — Layer 3 semantic safety bank.

Every negative here corresponds to something the live six-case evaluation either
accepted or nearly accepted. The bar is deterministic: the guard rejects, or the
governed outcome is NO_SAFE_OPTIMIZATION. The model's own claim is never sufficient.

If a positive case (P1-P3) goes red, the new invariant is wrong. Do NOT relax the
positive and do NOT weaken the guard to make Layer 3 pass -- that inverts the whole
point of the hardening loop.
"""

from __future__ import annotations

import json

import pytest

from app.config import settings
from app.spl.rewrite_guard import assert_rewrite_preserves
from app.spl.spl_optimization_llm import apply_optimization_llm


def _guard(v1: str, v2: str) -> dict:
    return assert_rewrite_preserves(v1, v2)


def _governed(v1: str, proposed: str, *, status: str = "OPTIMIZED") -> object:
    """Drive the real governed path with an injected model payload."""

    def _provider() -> str:
        return json.dumps({"status": status, "candidate_spl": proposed})

    return apply_optimization_llm(
        v1,
        classification="OPTIMIZATION_LLM_REQUIRED",
        llm_raw_output_provider=_provider,
    )


@pytest.fixture(autouse=True)
def _enable_layer3(monkeypatch: pytest.MonkeyPatch) -> None:
    # Exercising the governed path requires the flag; production default stays false.
    monkeypatch.setattr(settings, "ai_soc_spl_optimization_llm_enabled", True)


# --- negatives -----------------------------------------------------------------------


def test_n1_not_to_bang_equals_is_not_an_optimization() -> None:
    v1 = "search index=auth NOT status=success | stats count by user"
    v2 = 'search index=auth status!="success" | stats count by user'
    # NOT field=v and field!=v differ on missing/null fields; a swap is cosmetic.
    assert _guard(v1, v2)["verdict"] == "FAIL"
    assert _governed(v1, v2).outcome != "OPTIMIZED"


def test_n2_wildcard_removal_fails_the_guard() -> None:
    v1 = 'search index=network host="*it*" | stats count'
    v2 = 'search index=network host="it" | stats count'
    assert _guard(v1, v2)["verdict"] == "FAIL"
    assert _governed(v1, v2).outcome == "GUARD_FAILED"


def test_n3_wildcard_addition_fails_the_guard() -> None:
    v1 = 'search index=network host="it" | stats count'
    v2 = 'search index=network host="*it*" | stats count'
    assert _guard(v1, v2)["verdict"] == "FAIL"


def test_n4_invented_time_fails_the_guard() -> None:
    v1 = "search index=auth earliest=-1h latest=now action=failure | stats count by src_ip"
    v2 = (
        "search index=auth action=failure "
        '| eval window=relative_time(now(), "-1h") | stats count by src_ip'
    )
    result = _guard(v1, v2)
    assert result["verdict"] == "FAIL"
    assert "time_scope_earliest" in result["violations"]
    assert "time_scope_latest" in result["violations"]
    assert _governed(v1, v2).outcome == "GUARD_FAILED"


def test_n5_unchanged_candidate_claimed_optimized_normalizes_to_abstain() -> None:
    v1 = "search index=auth earliest=-1h latest=now action=failure | stats count by src_ip"
    # Same SPL, reformatted whitespace only, model insists it optimized it.
    reformatted = "search   index=auth  earliest=-1h latest=now action=failure |  stats count by src_ip"
    result = _governed(v1, reformatted, status="OPTIMIZED")
    assert result.outcome == "NO_SAFE_OPTIMIZATION"
    assert result.candidate_spl_v2 is None


def test_n6_altered_boolean_grouping_fails_the_guard() -> None:
    v1 = "search index=auth (a=1 OR b=2) c=3 | stats count"
    v2 = "search index=auth a=1 OR (b=2 c=3) | stats count"
    result = _guard(v1, v2)
    assert result["verdict"] == "FAIL"
    assert "boolean_grouping" in result["violations"]


def test_n7_changed_index_or_sourcetype_fails_the_guard() -> None:
    v1 = "search index=auth sourcetype=linux_secure a=1 | stats count"
    assert "index" in _guard(v1, "search index=web sourcetype=linux_secure a=1 | stats count")["violations"]
    assert "sourcetype" in _guard(v1, "search index=auth sourcetype=other a=1 | stats count")["violations"]


def test_n8_removed_required_output_field_fails_the_guard() -> None:
    v1 = "search index=auth action=failure | stats count by src_ip user"
    v2 = "search index=auth action=failure | stats count by src_ip"
    result = _guard(v1, v2)
    assert result["verdict"] == "FAIL"
    assert any(v.startswith("required_output_fields:") for v in result["violations"])


def test_n9_opt05_wildcard_case_can_never_be_accepted() -> None:
    """The exact case the live run accepted. Regression pin."""
    v1 = (
        "search index=fw sourcetype=fwlog earliest=-24h latest=now "
        "(*it* OR *ot*) action=allowed | stats count by src_ip dest_ip | head 100"
    )
    v2 = (
        "search index=fw sourcetype=fwlog earliest=-24h latest=now "
        "(it OR ot) action=allowed | stats count by src_ip dest_ip | head 100"
    )
    assert _guard(v1, v2)["verdict"] == "FAIL"
    assert _governed(v1, v2).outcome == "GUARD_FAILED"


def test_n10_tokenization_and_operator_swaps_fail_the_guard() -> None:
    # TERM() is not a substitute for pattern matching.
    assert (
        _guard(
            'search index=proxy url="*login.corp*" | stats count',
            "search index=proxy TERM(login.corp) | stats count",
        )["verdict"]
        == "FAIL"
    )
    # CIDR mask change.
    assert (
        _guard(
            'search index=fw | where cidrmatch("10.0.0.0/8", src_ip) | stats count',
            'search index=fw | where cidrmatch("10.0.0.0/16", src_ip) | stats count',
        )["verdict"]
        == "FAIL"
    )
    # Comparison operator change.
    assert (
        _guard(
            "search index=auth | where status>500 | stats count",
            "search index=auth | where status>=500 | stats count",
        )["verdict"]
        == "FAIL"
    )


# --- positives -----------------------------------------------------------------------


def test_p1_same_field_or_to_in_with_exact_values_passes() -> None:
    """The accepted S4 rewrite. If this goes red the new invariant is wrong."""
    parenthesised = (
        "search index=auth (user=alice OR user=bob OR user=carol) | stats count by user",
        "search index=auth (user IN (alice,bob,carol)) | stats count by user",
    )
    bare = (
        "search index=auth user=alice OR user=bob OR user=carol | stats count by user",
        "search index=auth user IN (alice,bob,carol) | stats count by user",
    )
    for v1, v2 in (parenthesised, bare):
        assert _guard(v1, v2)["verdict"] == "PASS", (v1, v2)

    # And an invented IN member must still fail.
    invented = "search index=auth user IN (alice,bob,carol,dave) | stats count by user"
    assert _guard(parenthesised[0], invented)["verdict"] == "FAIL"


def test_p2_selective_filter_shift_left_passes() -> None:
    v1 = (
        "search index=auth earliest=-1h latest=now "
        "| search action=failure | stats count by src_ip"
    )
    v2 = "search index=auth earliest=-1h latest=now action=failure | stats count by src_ip"
    assert _guard(v1, v2)["verdict"] == "PASS"


def test_p3_early_projection_outside_auto_fix_safe_passes() -> None:
    """A genuine Layer-3 win: Q18 early projection, not reachable by AUTO_FIX_SAFE.

    Drops an unused eval and projects before the aggregation. Match semantics are
    untouched, so the guard proves preservation rather than being relaxed for it.
    """
    v1 = (
        "search index=auth sourcetype=linux_secure earliest=-1h latest=now action=failure "
        "| eval noise=1 | stats count by src_ip | head 100"
    )
    v2 = (
        "search index=auth sourcetype=linux_secure earliest=-1h latest=now action=failure "
        "| fields src_ip | stats count by src_ip | head 100"
    )
    assert _guard(v1, v2)["verdict"] == "PASS"
    result = _governed(v1, v2)
    assert result.outcome == "OPTIMIZED"
    assert result.candidate_spl_v2 == v2


def test_positive_capability_is_not_abstained_away() -> None:
    """Anti-overfit pin: hardening must not reduce Layer 3 to always-abstain."""
    accepted = 0
    for v1, v2 in (
        (
            "search index=auth (user=alice OR user=bob) | stats count by user",
            "search index=auth user IN (alice,bob) | stats count by user",
        ),
        (
            "search index=auth earliest=-1h latest=now action=failure "
            "| eval noise=1 | stats count by src_ip | head 100",
            "search index=auth earliest=-1h latest=now action=failure "
            "| fields src_ip | stats count by src_ip | head 100",
        ),
    ):
        if _guard(v1, v2)["verdict"] == "PASS":
            accepted += 1
    assert accepted == 2, "guard rejects every legitimate positive — invariant too strict"
