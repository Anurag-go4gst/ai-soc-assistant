"""OPTIONAL_PHASE_S S1 — advisory efficiency detectors + optimization classification."""

from __future__ import annotations

from app.spl.draft_quality import (
    classify_optimization,
    evaluate_draft_quality,
    lint_draft_spl,
)


def _ids(report) -> set[str]:
    return {item.rule_id for item in report.findings}


def test_q03_not_advisory_fires() -> None:
    spl = (
        "search index=auth sourcetype=linux earliest=-1h latest=now NOT user=root "
        "| stats count by user | head 100"
    )
    report = evaluate_draft_quality(spl)
    assert "SOC-STD-SPL-001-Q03" in _ids(report)
    assert all(
        item.severity == "advisory"
        for item in report.findings
        if item.rule_id == "SOC-STD-SPL-001-Q03"
    )
    assert report.optimization_classification == "OPTIMIZATION_LLM_REQUIRED"


def test_q04_excessive_or_autofix_safe() -> None:
    arms = " OR ".join(f"user={i}" for i in range(12))
    spl = f"search index=auth sourcetype=linux earliest=-1h latest=now {arms} | stats count by user | head 100"
    report = evaluate_draft_quality(spl)
    assert "SOC-STD-SPL-001-Q04" in _ids(report)
    assert report.optimization_classification == "AUTO_FIX_SAFE"


def test_q15_term_candidate() -> None:
    spl = (
        "search index=auth sourcetype=linux earliest=-1h latest=now failed.login "
        "| stats count by user | head 100"
    )
    report = evaluate_draft_quality(spl)
    assert "SOC-STD-SPL-001-Q15" in _ids(report)


def test_q16_leading_wildcard_advisory_does_not_change_q13() -> None:
    # Generic leading wildcard — advisory Q16, not Q13 hard_fail (Q13 is family-scoped).
    spl = (
        "search index=fw sourcetype=pan earliest=-1h latest=now *corp "
        "| stats count by src | head 100"
    )
    report = evaluate_draft_quality(spl, detection_family="firewall_it_ot_rdp")
    assert "SOC-STD-SPL-001-Q16" in _ids(report)
    assert "SOC-STD-SPL-001-Q13" not in _ids(report)


def test_q13_untouched_family_hard_fail() -> None:
    spl = (
        'search index=fw sourcetype=pan earliest=-1h latest=now (*it* OR *ot*) '
        'session_state_norm="" | stats count by src | head 100'
    )
    report = evaluate_draft_quality(spl, detection_family="esp_it_to_ot_connection")
    assert any(item.rule_id == "SOC-STD-SPL-001-Q13" and item.severity == "hard_fail" for item in report.findings)


def test_q17_carves_out_q11_sort_before_streamstats() -> None:
    spl = (
        "search index=auth sourcetype=linux earliest=-1h latest=now\n"
        "| sort 0 + _time\n"
        "| streamstats time_window=10m dc(user) as distinct_count by src_ip\n"
        "| where distinct_count > 5"
    )
    report = evaluate_draft_quality(spl)
    assert "SOC-STD-SPL-001-Q11" not in _ids(report) or all(
        item.severity != "hard_fail" or item.rule_id != "SOC-STD-SPL-001-Q11"
        for item in report.findings
    )
    # Required early sort must not trigger Q17.
    assert "SOC-STD-SPL-001-Q17" not in _ids(report)


def test_q17_flags_early_nonstreaming_before_filters() -> None:
    spl = (
        "search index=auth sourcetype=linux earliest=-1h latest=now\n"
        "| stats count by user\n"
        "| search count>5\n"
        "| stats sum(count) as total by user\n"
        "| head 100"
    )
    report = evaluate_draft_quality(spl)
    assert "SOC-STD-SPL-001-Q17" in _ids(report)


def test_q18_early_projection_compatible_with_u03() -> None:
    # Wide pipeline, no fields before stats — Q18 advisory; U03 only if table refs missing.
    spl = (
        "search index=auth sourcetype=linux earliest=-1h latest=now EventCode=4625\n"
        "| eval user_norm=lower(user)\n"
        "| stats count by user_norm\n"
        "| table user_norm count\n"
        "| head 100"
    )
    report = evaluate_draft_quality(spl)
    assert "SOC-STD-SPL-001-Q18" in _ids(report)
    assert not any(
        item.rule_id == "SOC-STD-SPL-001-U03" and item.severity == "hard_fail"
        for item in report.findings
    )


def test_new_rules_never_enter_lint_draft_spl() -> None:
    spl = (
        "search index=auth sourcetype=linux earliest=-1h latest=now NOT user=root *corp "
        "| stats count by user | head 100"
    )
    # lint_draft_spl returns only hard_fail/warning — advisories must not appear.
    lint_ids = lint_draft_spl(spl)
    assert "SOC-STD-SPL-001-Q03" not in lint_ids
    assert "SOC-STD-SPL-001-Q16" not in lint_ids


def test_classify_pass_when_no_efficiency_advisories() -> None:
    spl = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-1h latest=now "
        "EventCode=4625 | stats count by user | head 100"
    )
    report = evaluate_draft_quality(spl)
    assert report.optimization_classification == "PASS"
    assert classify_optimization(report) == "PASS"


def test_s1_does_not_change_authority_on_freeze_rows() -> None:
    """S1 is detect-only — freeze authority fields unchanged (re-check via validate)."""
    import json
    from pathlib import Path

    from app.safeguards.spl_validator import validate_spl

    freeze = json.loads(
        Path(__file__).resolve().parents[3]
        .joinpath("docs/evals/spl_optimization/authority_baseline_v1.json")
        .read_text(encoding="utf-8")
    )
    for row in freeze["rows"]:
        if row["bank"] != "spl_golden" or not row.get("candidate_spl"):
            continue
        report = evaluate_draft_quality(row["candidate_spl"])
        assert report.optimization_classification in {
            "PASS",
            "AUTO_FIX_SAFE",
            "OPTIMIZATION_LLM_REQUIRED",
            "NO_SAFE_OPTIMIZATION",
        }
        v = validate_spl(row["candidate_spl"])
        d = v if isinstance(v, dict) else v.model_dump()
        assert bool(d.get("approved")) == bool(row["approved"])
        assert (d.get("normalized_spl") or None) == (row["normalized_spl"] or None)
        assert bool(d.get("execution_eligible") or False) == bool(row["execution_eligible"])
