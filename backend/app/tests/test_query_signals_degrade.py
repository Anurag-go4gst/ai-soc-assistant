"""Plan 3 H0 — finalize must degrade when query signals are absent.

`_query_signals_from_state()` returns `None` whenever `query_to_intent` is
missing or not a dict. Seven of the eight *assignments* in the codebase guard
with `or {}`; the MITRE one in `graph_node_context_finalize` did not.

Reachability is narrower than it first looks, and these tests encode the real
condition. The unguarded read is the right operand of
`_mitre_alert_context_present(...) or bool(signals.get("alert_context_present"))`,
so `or` short-circuits it whenever the query itself carries alert context. The
crash needs **both** a query with no alert markers **and** a missing/non-dict
`query_to_intent` — a knowledge-style turn whose canonical planning did not
complete.

State comes from the production seam (`run_canonical_flow`, which runs
`graph_node_init_routing`) with `query_to_intent` removed, rather than a
hand-rolled dict: finalize reads nine keys directly, and a synthetic fixture
would prove only that the fixture was wrong.

Call sites that pass the helper's result straight into a callee as a keyword
argument stay unguarded on purpose: those callees declare
`query_signals: dict | None = None` and normalize with `or {}` internally.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.pipeline import (
    _mitre_alert_context_present,
    _query_signals_from_state,
    graph_node_context_finalize,
    graph_node_shadow_tail,
)
from app.tests.support.canonical_flow import run_canonical_flow

# No alert markers, so `_mitre_alert_context_present` is False and the guarded
# expression's right operand is actually evaluated.
_NO_ALERT_QUERY = "What is our password policy for contractor accounts?"
_ALERT_QUERY = "Summarise the brute force alert for handover"


def _finalize_ready_state(query: str = _NO_ALERT_QUERY) -> dict[str, Any]:
    """Real pre-finalize state, built by the production sequence.

    `run_canonical_flow` covers routing + canonical planning; `graph_node_shadow_tail`
    is the node that actually populates `selected_skill_chain` and `route_plan_shadow`,
    and it runs immediately before dispatch/finalize on the live path
    (`pipeline.py`). `_ensure_context_finalize_state` fills execution, human_review
    and workflow_plan inside finalize itself.
    """
    result = run_canonical_flow(query, trace_id="trace-h0")
    return dict(graph_node_shadow_tail(dict(result.state)))


# --- the helper's own contract ------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"query_to_intent": None},
        {"query_to_intent": "not-a-dict"},
        {"query_to_intent": {}},
        {"query_to_intent": {"query_signals": None}},
        {"query_to_intent": {"query_signals": "not-a-dict"}},
    ],
)
def test_helper_returns_none_for_absent_or_malformed_query_to_intent(
    state: dict[str, Any],
) -> None:
    assert _query_signals_from_state(state) is None


def test_helper_returns_the_signals_when_present() -> None:
    state = {"query_to_intent": {"query_signals": {"mitre_map": True}}}
    assert _query_signals_from_state(state) == {"mitre_map": True}


# --- the reachability condition, pinned so it cannot silently change ---------


def test_probe_query_carries_no_alert_context() -> None:
    """If this ever becomes True the degrade tests below stop proving anything."""
    assert _mitre_alert_context_present(_NO_ALERT_QUERY) is False


def test_alert_bearing_query_short_circuits_before_the_signals_read() -> None:
    assert _mitre_alert_context_present(_ALERT_QUERY) is True


# --- the defect: finalize must degrade, not raise ----------------------------


# A *string* `query_to_intent` is deliberately absent from this matrix: it fails
# `PlaceholderResponse` schema validation later in finalize (`pipeline.py`), which
# is correct defensive behavior and a different concern from the H0 crash. The
# states below are the ones canonical planning can actually leave behind.
@pytest.mark.parametrize(
    "query_to_intent",
    ["__absent__", None, {}, {"query_signals": None}, {"query_signals": "not-a-dict"}],
)
def test_finalize_degrades_when_query_signals_are_unavailable(query_to_intent: Any) -> None:
    """Failing-first: every one of these raised AttributeError before the guard."""
    state = _finalize_ready_state()
    if query_to_intent == "__absent__":
        state.pop("query_to_intent", None)
    else:
        state["query_to_intent"] = query_to_intent

    result = graph_node_context_finalize(state)

    assert isinstance(result, dict)
    assert result.get("response") is not None


def test_finalize_still_reads_real_signals_when_present() -> None:
    """The guard prevents a crash; it must never mask a real signal value."""
    state = _finalize_ready_state()
    state["query_to_intent"] = {
        "query_signals": {"alert_context_present": True, "mitre_map": True}
    }
    result = graph_node_context_finalize(state)
    assert isinstance(result, dict)
    assert result.get("response") is not None


def test_unmodified_production_state_still_finalizes() -> None:
    """Control: the guard changes nothing on the normal path."""
    result = graph_node_context_finalize(_finalize_ready_state())
    assert isinstance(result, dict)
    assert result.get("response") is not None


# --- sweep: every *assignment* from the helper stays guarded ------------------


def test_every_assignment_from_the_helper_is_guarded() -> None:
    """Keyword-argument pass-through is excluded: those callees accept ``None``."""
    import re
    from pathlib import Path

    chat = Path(__file__).resolve().parents[1] / "chat"
    assignment = re.compile(
        r"^\s*(?!.*query_signals\s*=\s*_query_signals_from_state)"
        r".*\b\w+\s*=\s*_query_signals_from_state\("
    )
    unguarded: list[str] = []
    for path in (chat / "pipeline.py", chat / "run_contract_builder.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if assignment.match(line) and "or {}" not in line:
                unguarded.append(f"{path.name}:{number}")
    assert unguarded == [], unguarded
