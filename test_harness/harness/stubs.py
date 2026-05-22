"""Stub implementations of the routing, SPL-generation, and Splunk-search
interfaces. These let the harness be exercised end-to-end before the real
components land. Replace them by passing concrete clients into ``Runner``.

The stubs are intentionally simple: keyword routing, per-case canned SPL,
and an in-memory search engine that filters envelopes the generator would
have produced. This means the harness can run against either a live
Splunk (via ``SplunkSearchClient``) or fully offline (via
``InMemorySplunkSearch``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from ..generator.generate import iter_dataset_events, load_fixtures
from .interfaces import RoutingClient, RoutingDecision, SplGenerator, SplunkSearch


# --- Routing --------------------------------------------------------------


_ROUTING_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("lockout", "locked"), "alert_summary"),
    (
        (
            "failed login",
            "failed logins",
            "brute force",
            "unusual",
            "new source",
            "abnormal",
            "successful login after",
            "compromise",
        ),
        "attack_discovery",
    ),
    (
        (
            "top users",
            "most authentication events",
            "volume",
            "how many",
        ),
        "knowledge_recall",
    ),
    (("generate spl", "write spl", "produce spl"), "spl_generation"),
)


@dataclass
class KeywordRoutingStub(RoutingClient):
    """Deterministic keyword routing — good enough for the 6 auth cases."""

    def route(self, query: str) -> RoutingDecision:
        lowered = query.lower()
        for keywords, skill in _ROUTING_RULES:
            if any(keyword in lowered for keyword in keywords):
                return RoutingDecision(skill=skill, trace_id=_new_trace_id())
        # Default fallback. The harness will mark a skill mismatch.
        return RoutingDecision(skill="knowledge_recall", trace_id=_new_trace_id())


def _new_trace_id() -> str:
    return f"test-{uuid.uuid4()}"


# --- SPL generation -------------------------------------------------------


# Canned SPL per case id. Each string satisfies its case's must_contain
# spec by construction. The harness validates clauses, not exact strings.
_CASE_SPL: dict[str, str] = {
    "case_01_failed_login_spike_by_user": (
        "search index=pgcil_soc sourcetype=pgcil:auth action=failure "
        "earliest=-60m latest=now "
        "| stats count as fail_count by user "
        "| where fail_count > 50 | sort -fail_count"
    ),
    "case_02_failed_logins_by_source_ip": (
        "search index=pgcil_soc sourcetype=pgcil:auth action=failure "
        "earliest=-60m latest=now "
        "| stats count as fail_count by src "
        "| sort -fail_count"
    ),
    "case_03_success_after_failures": (
        "search index=pgcil_soc sourcetype=pgcil:auth "
        "earliest=-60m latest=now "
        "| streamstats count(eval(action=\"failure\")) as fail_count "
        "by user, src "
        "| where action=\"success\" AND fail_count >= 5"
    ),
    "case_04_top_users_by_volume": (
        "search index=pgcil_soc sourcetype=pgcil:auth "
        "earliest=-60m latest=now "
        "| stats count by user "
        "| sort -count"
    ),
    "case_05_account_lockouts_over_time": (
        "search index=pgcil_soc sourcetype=pgcil:auth "
        "signature=account_locked earliest=-60m latest=now "
        "| timechart span=10m count"
    ),
    "case_06_logins_from_new_source_ips": (
        "search index=pgcil_soc sourcetype=pgcil:auth action=success "
        "earliest=-60m latest=now "
        "| stats count by src "
        "| where NOT cidrmatch(\"10.0.0.0/8\", src)"
    ),
}


@dataclass
class CannedSplGenerator(SplGenerator):
    """Returns a pre-written SPL keyed by case id. The case id is provided
    through a side channel (``set_current_case``) because the public
    interface only takes ``(query, skill)``. The real generator will not
    need this — it will compose SPL from the query itself.
    """

    def __post_init__(self) -> None:
        self._current_case: str | None = None

    def set_current_case(self, case_id: str) -> None:
        self._current_case = case_id

    def generate(self, query: str, skill: str) -> str:
        case_id = self._current_case
        if case_id is None or case_id not in _CASE_SPL:
            raise RuntimeError(
                "CannedSplGenerator: current case id not set or unknown. "
                "Call set_current_case() before generate()."
            )
        return _CASE_SPL[case_id]


# --- Splunk search --------------------------------------------------------


class InMemorySplunkSearch(SplunkSearch):
    """In-memory search that evaluates SPL semantics against an explicit
    set of CIM auth events. The implementation is intentionally minimal —
    it recognizes the specific shapes the six canned SPLs take.

    Construct one per case using ``from_fixtures(active_datasets=...)`` so
    only that case's planted data is visible to the SPL, mirroring the
    per-case clear+ingest behavior expected against a live Splunk.
    """

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events

    @classmethod
    def from_fixtures(
        cls, fixtures_path: str, active_datasets: tuple[str, ...]
    ) -> "InMemorySplunkSearch":
        fixtures = load_fixtures(fixtures_path)  # type: ignore[arg-type]
        events = [
            env["event"]
            for _name, env in iter_dataset_events(fixtures, active_datasets, None)
        ]
        return cls(events)

    def run(
        self,
        spl: str,
        earliest_time: str | None = None,
        latest_time: str | None = None,
    ) -> list[dict[str, Any]]:
        lowered = spl.lower()
        events = self._events

        # action filters
        if "action=failure" in lowered:
            events = [e for e in events if e.get("action") == "failure"]
        elif "action=success" in lowered:
            events = [e for e in events if e.get("action") == "success"]

        # case 01 / 02: count by user / src
        if "by user" in lowered and "streamstats" not in lowered and "transaction" not in lowered:
            grouped = _group_count(events, "user", count_field="fail_count" if "action=failure" in lowered else "count")
            grouped.sort(key=lambda row: -int(list(row.values())[-1]))
            if "where fail_count > 50" in lowered:
                grouped = [row for row in grouped if int(row["fail_count"]) > 50]
            return grouped

        if "by src" in lowered and "stats" in lowered and "streamstats" not in lowered:
            count_field = "fail_count" if "action=failure" in lowered else "count"
            grouped = _group_count(events, "src", count_field=count_field)
            grouped.sort(key=lambda row: -int(list(row.values())[-1]))
            # case 06 — filter to non-internal IPs
            if "cidrmatch" in lowered:
                grouped = [row for row in grouped if not _in_cidr(row["src"], "10.0.0.0/8")]
            return grouped

        # case 03 — successful login following failures, grouped by user+src
        if "streamstats" in lowered and "fail_count >= 5" in lowered:
            return _success_after_failures(self._events, threshold=5)

        # case 05 — timechart of account_locked
        if "timechart" in lowered and "account_locked" in lowered:
            locked = [e for e in self._events if e.get("signature") == "account_locked"]
            return [{"total_count": len(locked)}]

        # Default: return empty.
        return []


def _group_count(
    events: Iterable[dict[str, Any]],
    key: str,
    count_field: str,
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for event in events:
        value = event.get(key)
        if value is None:
            continue
        counts[value] = counts.get(value, 0) + 1
    return [{key: k, count_field: v} for k, v in counts.items()]


def _success_after_failures(
    events: list[dict[str, Any]], threshold: int
) -> list[dict[str, Any]]:
    # Sort by user, src — generator already places successes after failures
    # within the same window via offset minutes, but we don't rely on
    # _time parsing here. Use ordering produced by the generator
    # (failures emitted first per block).
    by_key: dict[tuple[str, str], dict[str, int]] = {}
    for event in events:
        user = str(event.get("user", ""))
        src = str(event.get("src", ""))
        bucket = by_key.setdefault((user, src), {"fail_count": 0, "success_count": 0})
        if event.get("action") == "failure":
            bucket["fail_count"] += 1
        elif event.get("action") == "success" and bucket["fail_count"] >= threshold:
            bucket["success_count"] += 1
    return [
        {"user": user, "src": src, "fail_count": v["fail_count"], "success_count": v["success_count"]}
        for (user, src), v in by_key.items()
        if v["success_count"] > 0
    ]


def _in_cidr(ip: str, cidr: str) -> bool:
    import ipaddress

    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr)
    except ValueError:
        return False


__all__ = [
    "KeywordRoutingStub",
    "CannedSplGenerator",
    "InMemorySplunkSearch",
]
