"""P0 — containment observation vs enforcement request signal matrix."""

from __future__ import annotations

import pytest

from app.chat.query_signals import extract_query_signals

NEGATIVE_QUERIES = (
    "Investigate firewall deny spike",
    "show denied firewall traffic",
    "give SPL for blocked traffic",
)

POSITIVE_QUERIES = (
    "block this IP on the firewall",
    "have the firewall drop traffic from 198.51.100.42",
    "contain this source",
    "create a remediation plan to block this IP",
)


@pytest.mark.parametrize("query", NEGATIVE_QUERIES)
def test_containment_observation_queries_are_not_block_or_contain(query: str) -> None:
    signals = extract_query_signals(query)
    assert signals.get("block_or_contain") is False, query


@pytest.mark.parametrize("query", POSITIVE_QUERIES)
def test_containment_enforcement_queries_set_block_or_contain(query: str) -> None:
    signals = extract_query_signals(query)
    assert signals.get("block_or_contain") is True, query
