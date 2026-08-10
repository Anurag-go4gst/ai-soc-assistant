"""Tripwires for the B1=RETIRE planning-surface cleanup (plan items B2-R1..R4).

This file pins the **pre-retirement** state. Every expectation B2-R2/R3 will
change lives in one named table, `PLANNING_SURFACE_EXPECTATION`, so the
retirement is a single reviewable edit to that table plus the removals that make
it true again.

Three distinct planning surfaces are inventoried, and the point of the file is
that they must never be conflated:

1. `resource_plan_shadow` — a runner whose plan is discarded by construction.
2. the inline `llm_plan_bridge` application — reachable only from inside the
   *fenced* legacy `graph_node_evidence_planning`, so present but unreachable on
   a canonical turn.
3. the imperative guided-hybrid proposer — a parallel planning authority behind
   an **inverted** flag gate.

Two things must survive retirement untouched, and have their own permanently-
present table: live dispatch-v2 pre-SPL discovery, and deterministic guided
dispatch/validation/collection. Assertions covering those are marked RETAINED
and must never go red in R2/R3 — if they do, retirement overreached.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest

from app.chat import pipeline
from app.chat.guided_hybrid_dispatch import uses_guided_hybrid_dispatch_from_state
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest

_PIPELINE_PATH = Path(pipeline.__file__)
_PIPELINE_SRC = _PIPELINE_PATH.read_text()


# ---------------------------------------------------------------------------
# The single named expected-state contract. B2-R2/R3 flip values here.
# ---------------------------------------------------------------------------

PLANNING_SURFACE_EXPECTATION: dict[str, dict[str, Any]] = {
    "resource_plan_shadow": {
        "pipeline_symbol": "run_resource_plan_shadow",
        "symbol_present": False,
        "call_site_present": False,
        # The runner executes on some canonical turns, but never spends a model
        # hop under repo-default settings.
        "model_called_on_canonical_turn": False,
        "trace_key": "resource_plan_shadow",
        "trace_present": True,
    },
    "llm_plan_bridge_inline": {
        "pipeline_symbol": "apply_llm_primary_resource_plan",
        "symbol_present": False,
        "call_site_present": False,
        # Its only call site is inside the fenced legacy planning node, so a
        # canonical turn can never reach it.
        "reachable_on_canonical_turn": False,
        "enclosing_function": "graph_node_evidence_planning",
    },
    "guided_hybrid_proposer": {
        "pipeline_symbol": "propose_investigation_plan_llm",
        "symbol_present": False,
        "call_site_present": False,
        # Retired by B2-R2: the flag no longer gates any planning-model call.
        "flag_gates_proposer": False,
        "proposer_gate_consumers": 0,
        "reserved_dropped_reason": "guided_finalize_composer_reserved",
        "dispatch_label": "guided_investigation_plan_llm",
    },
}

# B2-R3: fenced legacy discovery. The whole evidence-loop cluster is reachable
# only through `graph_node_evidence_planning`, which is fenced off canonical
# turns and is also the loop's only initializer — so these live call sites can
# never do work. R3 flips these to absent and removes them.
LEGACY_DISCOVERY_EXPECTATION: dict[str, Any] = {
    "imperative_drain_symbol": "_run_discovery_loop_imperative",
    "imperative_drain_present": False,
    "live_call_sites": (
        '_timed_node(state, "discovery_loop", _run_discovery_loop_imperative)',
        '_timed_node(state, "evidence_planning_loop", graph_node_evidence_planning)',
    ),
    "live_call_sites_present": False,
    # RETAINED regardless: the node, the loop module and the hop bound all keep
    # consumers (the legacy harness graph and direct unit tests), and MAX_MCP_HOPS
    # still bounds recipe budgets inside evidence_loop.py.
    "retained_symbols": ("graph_node_evidence_planning", "graph_node_mcp_call"),
}


# RETAINED — never flipped by any B2-R item. R3 must not remove these.
RETAINED_SURFACE_EXPECTATION: dict[str, dict[str, Any]] = {
    "live_pre_spl_discovery": {
        "pipeline_symbol": "graph_node_pre_spl_mcp_discovery",
        "symbol_present": True,
    },
    "deterministic_guided": {
        "modules": (
            "app.chat.guided_investigation_planner",
            "app.chat.guided_capability_validator",
            "app.planner.composer",
            "app.chat.guided_hybrid_collection",
        ),
        "symbol_present": True,
    },
}

# Budget/deadline consumers of `ai_soc_guided_llm_enabled`. These are legitimate
# and survive RETIRE — only the proposer gate above goes away.
GUIDED_FLAG_BUDGET_CONSUMERS = 3

_FLAG_CONSUMER_FILES = (
    Path(pipeline.__file__),
    Path(pipeline.__file__).parent.parent / "llm" / "guided_llm_budget.py",
)


@pytest.fixture(autouse=True)
def _quiet_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")


def _surface(name: str) -> dict[str, Any]:
    return PLANNING_SURFACE_EXPECTATION[name]


def _enclosing_function(source: str, needle: str) -> str | None:
    """Name of the top-level function whose body contains ``needle``."""
    tree = ast.parse(source)
    lines = source.split("\n")
    target_lines = [i + 1 for i, ln in enumerate(lines) if needle in ln and not ln.lstrip().startswith(("from ", "import ", "#"))]
    if not target_lines:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.end_lineno is not None:
            if any(node.lineno <= t <= node.end_lineno for t in target_lines):
                return node.name
    return None


# ---------------------------------------------------------------------------
# Static inventory — every surface named in the table, nothing hardcoded outside
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("surface_name", sorted(PLANNING_SURFACE_EXPECTATION))
def test_planning_surface_symbol_presence_matches_contract(surface_name: str) -> None:
    expected = _surface(surface_name)
    symbol = expected["pipeline_symbol"]
    assert hasattr(pipeline, symbol) is expected["symbol_present"], (
        f"{surface_name}: pipeline.{symbol} presence does not match "
        f"PLANNING_SURFACE_EXPECTATION[{surface_name!r}]['symbol_present']"
    )


@pytest.mark.parametrize("surface_name", sorted(PLANNING_SURFACE_EXPECTATION))
def test_planning_surface_call_site_presence_matches_contract(surface_name: str) -> None:
    expected = _surface(surface_name)
    symbol = expected["pipeline_symbol"]
    # A call site, not the import line.
    call_sites = [
        ln for ln in _PIPELINE_SRC.split("\n")
        if f"{symbol}(" in ln and not ln.lstrip().startswith(("from ", "import ", "def "))
    ]
    assert bool(call_sites) is expected["call_site_present"], (
        f"{surface_name}: call-site presence for {symbol} does not match the contract"
    )


def test_inline_bridge_call_site_is_inside_the_fenced_legacy_node() -> None:
    """The bridge is present but unreachable — that distinction is the point."""
    expected = _surface("llm_plan_bridge_inline")
    if not expected["call_site_present"]:
        assert f"{expected['pipeline_symbol']}(" not in _PIPELINE_SRC, (
            "contract says the inline bridge is retired, but a call site remains"
        )
        return
    enclosing = _enclosing_function(_PIPELINE_SRC, f"{expected['pipeline_symbol']}(")
    assert enclosing == expected["enclosing_function"], (
        "inline bridge moved out of the fenced legacy node; reachability changed"
    )


# ---------------------------------------------------------------------------
# Runtime call counts on a canonical turn, in both runtimes
# ---------------------------------------------------------------------------


def _counting_run(monkeypatch: pytest.MonkeyPatch, query: str, *, use_graph: bool = False) -> dict[str, int]:
    """Count planning-surface calls for one turn.

    Patches the *pipeline module globals*, because pipeline.py binds all three
    symbols by from-import — patching their defining modules would count nothing.
    """
    counts = {name: 0 for name in PLANNING_SURFACE_EXPECTATION}
    for name, expected in PLANNING_SURFACE_EXPECTATION.items():
        symbol = expected["pipeline_symbol"]
        if not hasattr(pipeline, symbol):
            continue
        original = getattr(pipeline, symbol)

        def _wrapper(*args: Any, _orig: Any = original, _key: str = name, **kwargs: Any) -> Any:
            counts[_key] += 1
            return _orig(*args, **kwargs)

        monkeypatch.setattr(pipeline, symbol, _wrapper)

    if use_graph:
        from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph

        run_chat_via_resource_planner_graph(ChatRequest(message=query))
    else:
        build_live_chat_response(ChatRequest(message=query))
    return counts


_CANONICAL_QUERY = "Show me failed login attempts in the last 24 hours"


@pytest.mark.parametrize("use_graph", [False, True], ids=["imperative", "rp_graph"])
def test_inline_bridge_is_never_called_on_a_canonical_turn(
    monkeypatch: pytest.MonkeyPatch, use_graph: bool
) -> None:
    counts = _counting_run(monkeypatch, _CANONICAL_QUERY, use_graph=use_graph)
    expected_reachable = _surface("llm_plan_bridge_inline")["reachable_on_canonical_turn"]
    assert (counts["llm_plan_bridge_inline"] > 0) is expected_reachable


@pytest.mark.parametrize("use_graph", [False, True], ids=["imperative", "rp_graph"])
def test_shadow_runner_spends_no_model_hop(monkeypatch: pytest.MonkeyPatch, use_graph: bool) -> None:
    """The shadow may run; it must not spend a model call, and its output is discarded."""
    expected = _surface("resource_plan_shadow")
    if use_graph:
        from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph

        response = run_chat_via_resource_planner_graph(ChatRequest(message=_CANONICAL_QUERY))
    else:
        response = build_live_chat_response(ChatRequest(message=_CANONICAL_QUERY))
    trace = response.control_plane_trace or {}
    shadow = trace.get(expected["trace_key"])
    assert (shadow is not None) is expected["trace_present"]
    if shadow is None:
        return
    assert shadow.get("llm_called") is expected["model_called_on_canonical_turn"], (
        "shadow spent a model hop on a canonical turn"
    )
    if shadow.get("live_plan_source_unchanged") is not None:
        assert shadow["live_plan_source_unchanged"] is True, "shadow result must stay discarded"


# ---------------------------------------------------------------------------
# Guided: the inverted gate, and the proposer/execution distinction
# ---------------------------------------------------------------------------


def test_guided_proposer_gate_is_inverted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag TRUE reserves the proposer; flag FALSE calls it.

    Asserted against the source of the branch rather than a live turn, because
    the branch is what R2 removes and it must be pinned unambiguously.
    """
    expected = _surface("guided_hybrid_proposer")
    if not expected["flag_gates_proposer"]:
        # Flipping the contract must assert absence, never skip — a skipped
        # tripwire is indistinguishable from a passing one.
        assert f"{expected['pipeline_symbol']}(query=" not in _PIPELINE_SRC, (
            "contract says the proposer gate is retired, but the call site remains"
        )
        assert expected["reserved_dropped_reason"] not in _PIPELINE_SRC
        return
    enclosing = _enclosing_function(_PIPELINE_SRC, f"{expected['pipeline_symbol']}(")
    assert enclosing == "_run_guided_hybrid_dispatch"
    src = _PIPELINE_SRC
    gate_index = src.index("if settings.ai_soc_guided_llm_enabled:")
    proposer_index = src.index(f"{expected['pipeline_symbol']}(query=")
    reserved_index = src.index(expected["reserved_dropped_reason"])
    # The reserved branch precedes the call branch: true reserves, false calls.
    assert gate_index < reserved_index < proposer_index, (
        "guided proposer gate is no longer inverted; R2's disposition assumes it is"
    )


def test_guided_flag_consumer_counts_match_contract() -> None:
    """One proposer gate, three budget/deadline consumers.

    R2 flips `proposer_gate_consumers` to 0; the budget count must not move.
    """
    expected = _surface("guided_hybrid_proposer")
    pattern = re.compile(r"settings\.ai_soc_guided_llm_enabled")
    total = sum(len(pattern.findall(path.read_text())) for path in _FLAG_CONSUMER_FILES)
    assert total == expected["proposer_gate_consumers"] + GUIDED_FLAG_BUDGET_CONSUMERS, (
        "ai_soc_guided_llm_enabled consumer count changed; re-inventory before retiring"
    )


def test_guided_dispatch_step_label_is_gated_on_attempt() -> None:
    """The label outlives its producer unless R2 dispositions it explicitly."""
    expected = _surface("guided_hybrid_proposer")
    label = expected["dispatch_label"]
    emitters = [ln for ln in _PIPELINE_SRC.split("\n") if f'"{label}"' in ln]
    if not expected["call_site_present"]:
        assert not emitters, "proposer retired but its dispatch-step label still emits"
        return
    assert emitters, f"{label} emitter missing while the proposer still exists"
    assert any("llm_result.attempted" in ln for ln in _PIPELINE_SRC.split("\n"))


# ---------------------------------------------------------------------------
# RETAINED — must never go red in R2/R3
# ---------------------------------------------------------------------------


def test_live_pre_spl_discovery_symbol_is_retained() -> None:
    expected = RETAINED_SURFACE_EXPECTATION["live_pre_spl_discovery"]
    assert hasattr(pipeline, expected["pipeline_symbol"]) is expected["symbol_present"]


def test_deterministic_guided_modules_are_retained() -> None:
    import importlib

    expected = RETAINED_SURFACE_EXPECTATION["deterministic_guided"]
    for module_name in expected["modules"]:
        assert importlib.import_module(module_name) is not None


def test_deterministic_guided_surfaces_do_not_import_the_proposer() -> None:
    """Negative control against conflating the proposer with guided execution."""
    import importlib

    expected = RETAINED_SURFACE_EXPECTATION["deterministic_guided"]
    for module_name in expected["modules"]:
        module = importlib.import_module(module_name)
        source = Path(module.__file__ or "").read_text()
        assert "guided_investigation_plan_llm" not in source, (
            f"{module_name} imports the proposer; deterministic guided execution "
            "must stay separable from the LLM proposer"
        )


def test_guided_hybrid_gate_still_requires_the_deterministic_preconditions() -> None:
    """RETAINED: the deterministic gate contract is independent of the proposer."""
    state = {
        "planning_decision": {"path_type": "guided_investigation"},
        "canonical_planning_input": {"routing": {"answer_goal": "guided_investigation"}},
        "evidence_plan": {
            "answer_mode": "guided_investigation",
            "resource_plan": {"steps": []},
            "investigation_planning_enabled": True,
        },
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", True)
        assert uses_guided_hybrid_dispatch_from_state(state) is True
        # Removing only the deterministic precondition must close the gate.
        closed = {**state, "evidence_plan": {**state["evidence_plan"], "investigation_planning_enabled": None}}
        assert uses_guided_hybrid_dispatch_from_state(closed) is False


# ---------------------------------------------------------------------------
# Legacy fence
# ---------------------------------------------------------------------------


def test_legacy_evidence_planning_is_fenced_off_canonical_turns() -> None:
    from app.chat.canonical_mode import is_canonical_authoritative

    assert is_canonical_authoritative()
    result = pipeline.graph_node_evidence_planning({"request": ChatRequest(message=_CANONICAL_QUERY)})
    failure = result.get("canonical_planning_failure") or {}
    assert failure.get("reason") == "canonical_forbids_legacy_evidence_planning", (
        "legacy planning node is no longer fenced; the inline bridge would become reachable"
    )


# ---------------------------------------------------------------------------
# B2-R3 — fenced legacy discovery has no live call site
# ---------------------------------------------------------------------------


def test_legacy_discovery_live_call_sites_match_contract() -> None:
    expected = LEGACY_DISCOVERY_EXPECTATION
    present = [site for site in expected["live_call_sites"] if site in _PIPELINE_SRC]
    assert bool(present) is expected["live_call_sites_present"], (
        f"legacy discovery call-site presence changed: still present={present}"
    )


def test_imperative_discovery_drain_presence_matches_contract() -> None:
    expected = LEGACY_DISCOVERY_EXPECTATION
    symbol = expected["imperative_drain_symbol"]
    assert (f"def {symbol}(" in _PIPELINE_SRC) is expected["imperative_drain_present"]


def test_legacy_discovery_symbols_kept_for_retained_consumers() -> None:
    """RETAINED: the node and mcp_call keep the legacy harness graph and unit tests."""
    for symbol in LEGACY_DISCOVERY_EXPECTATION["retained_symbols"]:
        assert hasattr(pipeline, symbol), f"{symbol} still has retained consumers"


def test_hop_bound_survives_and_still_guards_recipe_budgets() -> None:
    """RETAINED: MAX_MCP_HOPS is inert on live paths but still bounds recipes."""
    from app.chat import evidence_loop

    assert evidence_loop.MAX_MCP_HOPS >= 1
    source = Path(evidence_loop.__file__).read_text()
    assert "min(MAX_MCP_HOPS - hops_done" in source, (
        "MAX_MCP_HOPS no longer bounds the recipe call budget"
    )
