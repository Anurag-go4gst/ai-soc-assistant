"""Deterministic SOC aggregate shapes adopted from Wazuh MCP review (A2–A4).

Pure functions — no MCP I/O, no LLM. Used by Experience Center fixtures and
live answer builders for shift-handoff / prioritization cards.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

# Splunk-native urgency weights (plan §3.3 GAP-4); extend with CVE weights when onboarded.
DEFAULT_URGENCY_WEIGHTS: dict[str, int] = {
    "critical": 10,
    "high": 5,
    "medium": 2,
    "med": 2,
    "low": 1,
}


def urgency_risk_weight(urgency: str, *, weights: dict[str, int] | None = None) -> int:
    table = weights or DEFAULT_URGENCY_WEIGHTS
    return int(table.get(str(urgency).lower(), 1))


def top_risky_hosts(
    rows: list[dict[str, Any]],
    *,
    host_field: str = "host",
    urgency_field: str = "urgency",
    count_field: str = "alert_count",
    weights: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """A2: urgency-weighted host heatmap (crit*10 + high*5 + med*2 + low*1)."""
    scores: dict[str, int] = {}
    for row in rows:
        host = str(row.get(host_field) or "")
        if not host:
            continue
        count = int(row.get(count_field) or row.get("count") or 1)
        weight = urgency_risk_weight(str(row.get(urgency_field) or ""), weights=weights)
        scores[host] = scores.get(host, 0) + weight * count
    return [
        {"Host": host, "Risk score": score, "Rank": index + 1}
        for index, (host, score) in enumerate(sorted(scores.items(), key=lambda item: -item[1]))
    ]


def rules_coverage_map(
    rules: list[dict[str, Any]],
    *,
    framework_field: str = "framework_id",
    rule_id_field: str = "rule_id",
) -> dict[str, list[str]]:
    """A3: inverted index framework-id → rule-ids for detection-gap cards."""
    coverage: dict[str, list[str]] = defaultdict(list)
    for rule in rules:
        framework = str(rule.get(framework_field) or rule.get("framework") or "")
        rule_id = str(rule.get(rule_id_field) or rule.get("id") or "")
        if not framework or not rule_id:
            continue
        if rule_id not in coverage[framework]:
            coverage[framework].append(rule_id)
    return {key: sorted(values) for key, values in sorted(coverage.items())}


def alert_summary_aggregate(
    alerts: list[dict[str, Any]],
    *,
    severity_field: str = "urgency",
    rule_field: str = "rule_name",
    mitre_field: str = "mitre_technique",
    host_field: str = "host",
    agent_field: str = "agent",
    ip_field: str = "src",
    top_n: int = 5,
) -> dict[str, Any]:
    """A4: shift-handoff rollup — severity distribution + top rules/MITRE/IPs/agents."""
    severity_dist = Counter(str(row.get(severity_field) or "unknown") for row in alerts)
    return {
        "total_alerts": len(alerts),
        "severity_distribution": dict(severity_dist),
        "top_rules": _top_values(alerts, rule_field, top_n),
        "top_mitre_techniques": _top_values(alerts, mitre_field, top_n),
        "top_hosts": _top_values(alerts, host_field, top_n),
        "top_agents": _top_values(alerts, agent_field, top_n),
        "top_source_ips": _top_values(alerts, ip_field, top_n),
    }


def _top_values(rows: list[dict[str, Any]], field: str, top_n: int) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = str(row.get(field) or "").strip()
        if value:
            counter[value] += int(row.get("alert_count") or row.get("count") or 1)
    return [{"value": key, "count": count} for key, count in counter.most_common(top_n)]
