"""OPTIONAL_PHASE_S S2 — assert_rewrite_preserves unit coverage."""

from __future__ import annotations

from app.spl.rewrite_guard import assert_rewrite_preserves


def test_pass_equivalent_or_to_in() -> None:
    v1 = (
        "search index=auth sourcetype=linux earliest=-1h latest=now "
        "user=a OR user=b | stats count by user | head 100"
    )
    v2 = (
        "search index=auth sourcetype=linux earliest=-1h latest=now "
        "user IN (a,b) | stats count by user | head 100"
    )
    result = assert_rewrite_preserves(v1, v2, rqc=None)
    assert result["verdict"] == "PASS"
    assert result["retain_v1"] is False


def test_fail_drops_index() -> None:
    v1 = "search index=auth sourcetype=linux earliest=-1h latest=now | stats count | head 100"
    v2 = "search sourcetype=linux earliest=-1h latest=now | stats count | head 100"
    result = assert_rewrite_preserves(v1, v2)
    assert result["verdict"] == "FAIL"
    assert "index" in result["violations"]
    assert result["retain_v1"] is True


def test_fail_drops_sourcetype() -> None:
    v1 = "search index=auth sourcetype=linux earliest=-1h latest=now | stats count | head 100"
    v2 = "search index=auth earliest=-1h latest=now | stats count | head 100"
    result = assert_rewrite_preserves(v1, v2)
    assert result["verdict"] == "FAIL"
    assert "sourcetype" in result["violations"]


def test_fail_changes_time_scope() -> None:
    v1 = "search index=auth sourcetype=linux earliest=-1h latest=now | stats count | head 100"
    v2 = "search index=auth sourcetype=linux earliest=-7d latest=now | stats count | head 100"
    result = assert_rewrite_preserves(v1, v2)
    assert result["verdict"] == "FAIL"
    assert "time_scope_earliest" in result["violations"]


def test_fail_drops_result_limit() -> None:
    v1 = "search index=auth sourcetype=linux earliest=-1h latest=now | stats count | head 100"
    v2 = "search index=auth sourcetype=linux earliest=-1h latest=now | stats count"
    result = assert_rewrite_preserves(v1, v2)
    assert result["verdict"] == "FAIL"
    assert "result_limit" in result["violations"]


def test_fail_drops_aggregation() -> None:
    v1 = "search index=auth sourcetype=linux earliest=-1h latest=now | stats count by user | head 100"
    v2 = "search index=auth sourcetype=linux earliest=-1h latest=now | head 100"
    result = assert_rewrite_preserves(v1, v2)
    assert result["verdict"] == "FAIL"
    assert "aggregation_meaning" in result["violations"]


def test_fail_drops_rqc_governed_filter() -> None:
    rqc = {"entities": {"source_ip": "198.51.100.42", "user": "admin"}}
    v1 = (
        "search index=auth sourcetype=linux earliest=-1h latest=now "
        "src_ip=198.51.100.42 user=admin | stats count | head 100"
    )
    v2 = (
        "search index=auth sourcetype=linux earliest=-1h latest=now "
        "user=admin | stats count | head 100"
    )
    result = assert_rewrite_preserves(v1, v2, rqc=rqc)
    assert result["verdict"] == "FAIL"
    assert any(v.startswith("governed_filters") for v in result["violations"])


def test_pass_preserves_rqc_slots() -> None:
    rqc = {"entities": {"source_ip": "198.51.100.42"}}
    v1 = (
        "search index=auth sourcetype=linux earliest=-1h latest=now "
        "src_ip=198.51.100.42 EventCode=4625 | stats count | head 100"
    )
    v2 = (
        "search index=auth sourcetype=linux earliest=-1h latest=now "
        "EventCode=4625 src_ip=198.51.100.42 | stats count | head 100"
    )
    result = assert_rewrite_preserves(v1, v2, rqc=rqc)
    assert result["verdict"] == "PASS"


def test_s2_does_not_mutate_freeze_authority() -> None:
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
        # Guard not wired to rewrite yet — identity rewrite must PASS and leave authority.
        result = assert_rewrite_preserves(row["candidate_spl"], row["candidate_spl"])
        assert result["verdict"] == "PASS"
        v = validate_spl(row["candidate_spl"])
        d = v if isinstance(v, dict) else v.model_dump()
        assert bool(d.get("approved")) == bool(row["approved"])
        assert bool(d.get("execution_eligible") or False) == bool(row["execution_eligible"])
