"""Where the keyword router actually holds routing authority (Plan 4 R1.2).

Plan 4's corpus was required to include rows exercising the surfaces where
`route_skill_deterministic` decides. Assembly measured that **neither surface is
reachable from query text** given the committed registries, so the plan's stated
fallback applies: cover them by unit test instead of by corpus row.

There are exactly two such surfaces:

* `_keyword_fallback` — reached from `_route_catalog_only` when a mapped
  use-case id does not resolve (`catalog_use_case_not_found`), or when a catalog
  entry's `primary_skill` is neither a routable skill nor in
  `CATALOG_SKILL_COLLAPSE` (`unknown_catalog_primary_skill:*`).
* `_qu_failover_route` — reached only when `understand_query` raises.

Both are real code paths and both must keep working; these tests pin their
behavior directly, and pin the registry conditions that currently make them
unreachable, so that a future catalog edit which *does* make them reachable
fails here loudly rather than silently changing routing authority.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.query_understanding.parser import understand_query
from app.routing.deterministic_router import LOW_CONFIDENCE_ROUTE
from app.routing.select_route_from_understanding import CATALOG_SKILL_COLLAPSE, _keyword_fallback
from app.use_cases.registry import get_use_case
from contracts.skill_enum import SKILL_ENUM

REPO_ROOT = Path(__file__).resolve().parents[3]
USE_CASE_CATALOG = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"


def _catalog_entries() -> list[dict]:
    payload = json.loads(USE_CASE_CATALOG.read_text(encoding="utf-8"))
    entries = payload.get("use_cases") or payload.get("entries") or payload
    if isinstance(entries, dict):
        entries = list(entries.values())
    return [e for e in entries if isinstance(e, dict)]


# ------------------------------------------------------------------ reachability


def test_every_catalog_primary_skill_is_routable_or_collapsible() -> None:
    """Pins why `unknown_catalog_primary_skill` cannot fire today.

    If a future catalog entry introduces a `primary_skill` that is neither
    routable nor collapsible, that entry silently hands routing authority to the
    keyword router. This test makes that a visible decision instead.
    """
    unknown = [
        (e.get("use_case_id"), e.get("primary_skill"))
        for e in _catalog_entries()
        if e.get("primary_skill") not in SKILL_ENUM
        and e.get("primary_skill") not in CATALOG_SKILL_COLLAPSE
    ]
    assert unknown == [], f"catalog entries that would fall back to the keyword router: {unknown}"


def test_every_catalog_use_case_id_resolves() -> None:
    """Pins why `catalog_use_case_not_found` cannot fire today."""
    unresolvable = [
        e.get("use_case_id") for e in _catalog_entries() if get_use_case(str(e.get("use_case_id"))) is None
    ]
    assert unresolvable == [], f"catalog ids the registry cannot resolve: {unresolvable}"


@pytest.mark.parametrize(
    "hostile",
    ["", "   ", "\x00\x01", "a" * 20000, "🙂" * 500, "'; DROP TABLE x; --", "{{}}[]", "\n\n\n"],
)
def test_understand_query_does_not_raise_on_hostile_input(hostile: str) -> None:
    """Pins why `_qu_failover_route` is not reachable from a query string.

    The failover path exists for a parser that throws. Measured at Plan 4 R1.2,
    the parser does not throw on any of these, so the corpus cannot reach it.
    """
    understand_query(hostile)


# ------------------------------------------------------- the paths still work


def test_keyword_fallback_marks_low_confidence_default_as_weak_not_keyword_authority() -> None:
    """An unmatched query keeps `query_understanding_weak`, not keyword authority.

    This is the distinction Plan 4 turns on: the 0.20 `knowledge_recall` default
    is *not* attributed to the keyword router, because the keyword router did not
    choose it — no rule matched.
    """
    understanding = understand_query("Can you correlate badge-reader swipes with cafeteria purchases?")
    keyword_would_have = dict(LOW_CONFIDENCE_ROUTE)

    base, provenance = _keyword_fallback(
        understanding,
        "Can you correlate badge-reader swipes with cafeteria purchases?",
        keyword_would_have,
        reason="catalog_use_case_not_found",
    )

    assert base["skill"] == LOW_CONFIDENCE_ROUTE["skill"]
    assert provenance["authority_source"] == "query_understanding_weak"
    assert provenance["selected_by"] == "query_understanding_weak"
    assert "catalog_use_case_not_found" in base["reasons"]


def test_keyword_fallback_claims_authority_only_on_a_real_keyword_match() -> None:
    """When a keyword rule *does* match, the fallback records keyword authority."""
    query = "Which users have excessive failed logins?"
    understanding = understand_query(query)

    base, provenance = _keyword_fallback(
        understanding,
        query,
        {"skill": "attack_discovery", "tool_plan": [], "confidence": 0.86, "reasons": []},
        reason="unknown_catalog_primary_skill:some_future_skill",
    )

    assert base["skill"] == "attack_discovery"
    assert provenance["authority_source"] == "keyword_router_fallback"
    assert provenance["selected_by"] == "keyword_router_fallback"
