from __future__ import annotations

from app.analysis.soc_aggregates import (
    alert_summary_aggregate,
    rules_coverage_map,
    top_risky_hosts,
    urgency_risk_weight,
)

ROWS = [
    {"host": "h1", "urgency": "critical", "alert_count": 2, "rule_name": "r1", "mitre_technique": "T1110"},
    {"host": "h2", "urgency": "high", "alert_count": 1, "rule_name": "r2", "mitre_technique": "T1078"},
    {"host": "h1", "urgency": "medium", "alert_count": 3, "rule_name": "r1", "mitre_technique": "T1110"},
]


def test_urgency_risk_weight_mapping() -> None:
    assert urgency_risk_weight("critical") == 10
    assert urgency_risk_weight("unknown") == 1


def test_top_risky_hosts_ranks_by_weighted_score() -> None:
    ranked = top_risky_hosts(ROWS, count_field="alert_count")
    assert ranked[0]["Host"] == "h1"
    assert ranked[0]["Risk score"] == 26


def test_rules_coverage_map_inverts_framework_index() -> None:
    coverage = rules_coverage_map(
        [
            {"framework_id": "MITRE", "rule_id": "1001"},
            {"framework_id": "MITRE", "rule_id": "1002"},
            {"framework_id": "PCI", "rule_id": "2001"},
        ]
    )
    assert coverage["MITRE"] == ["1001", "1002"]
    assert coverage["PCI"] == ["2001"]


def test_alert_summary_aggregate_shape() -> None:
    summary = alert_summary_aggregate(ROWS, severity_field="urgency")
    assert summary["total_alerts"] == 3
    assert summary["severity_distribution"]["critical"] == 1
    assert summary["top_rules"][0]["value"] == "r1"
