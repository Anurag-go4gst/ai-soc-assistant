"""Plan 5 B6 — pin the evaluator observability matrix.

`docs/evals/plan5/b6_evaluator_observability_matrix.md` claims which routing layer each
evaluator actually reaches. B5 showed why that matters: capability enforcement changed a
real in-catalogue answer (`cisco.ot.029`) while `eval_routing_truth_set.py --arm both`
reported zero changes, because neither of its arms calls `adjudicate_route`.

These tests assert *call reachability only* — never a routing outcome, never a baseline —
so a future refactor that silently moves a layer into or out of an evaluator's reach fails
here instead of being discovered by a product regression.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TRUTH_SET = REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json"


def _load_script(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_b6_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_row() -> dict[str, Any]:
    payload = json.loads(TRUTH_SET.read_text(encoding="utf-8"))
    return dict(payload["rows"][0])


class _Counter:
    """Wrap a callable and count invocations without changing its behaviour."""

    def __init__(self, fn: Any) -> None:
        self._fn = fn
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return self._fn(*args, **kwargs)


@pytest.fixture()
def counters(monkeypatch: pytest.MonkeyPatch) -> dict[str, _Counter]:
    """Instrument every layer boundary named in the matrix."""
    import app.chat.resolved_query_builder as rqb
    import app.routing.route_adjudication as adjudication_mod
    import app.routing.select_route_from_understanding as select_mod
    import app.routing.skill_router as skill_router_mod

    wired = {
        "select_route_from_understanding": _Counter(select_mod.select_route_from_understanding),
        "route_skill": _Counter(skill_router_mod.route_skill),
        "build_resolved_query_contract": _Counter(rqb.build_resolved_query_contract),
        "adjudicate_route": _Counter(adjudication_mod.adjudicate_route),
    }
    monkeypatch.setattr(select_mod, "select_route_from_understanding", wired["select_route_from_understanding"])
    monkeypatch.setattr(skill_router_mod, "route_skill", wired["route_skill"])
    monkeypatch.setattr(rqb, "build_resolved_query_contract", wired["build_resolved_query_contract"])
    monkeypatch.setattr(adjudication_mod, "adjudicate_route", wired["adjudicate_route"])
    return wired


def test_truth_set_deterministic_arm_observes_layer_1_only(counters: dict[str, _Counter]) -> None:
    """Deterministic arm reaches `select_route_from_understanding` and stops there."""
    evaluator = _load_script("eval_routing_truth_set")
    evaluator.evaluate_row(_sample_row())

    assert counters["select_route_from_understanding"].calls >= 1
    assert counters["adjudicate_route"].calls == 0, (
        "deterministic arm now reaches route adjudication — the B6 matrix and the frozen "
        "baseline semantics both need re-measuring before this is allowed"
    )
    assert counters["build_resolved_query_contract"].calls == 0
    assert counters["route_skill"].calls == 0


def test_truth_set_live_arm_observes_route_skill_not_adjudication(counters: dict[str, _Counter]) -> None:
    """Live arm reaches `route_skill` (layer 2) — still short of adjudication."""
    evaluator = _load_script("eval_routing_truth_set")
    row = _sample_row()
    evaluator.evaluate_live_row(row, "knowledge_recall")

    assert counters["route_skill"].calls >= 1
    assert counters["adjudicate_route"].calls == 0


def test_b5_arm_observes_contract_and_adjudication(counters: dict[str, _Counter]) -> None:
    """The Plan 5 B5 arm is the instrument that reaches layers 3 and 4."""
    from app.config import settings

    probe = _load_script("eval_b5_capability_enforcement")
    previous = settings.ai_soc_live_capability_enforcement_enabled
    try:
        probe._adjudicate_row(_sample_row(), enabled=False)
    finally:
        settings.ai_soc_live_capability_enforcement_enabled = previous

    assert counters["select_route_from_understanding"].calls >= 1
    assert counters["build_resolved_query_contract"].calls >= 1
    assert counters["adjudicate_route"].calls >= 1


def test_b5_measurement_never_leaves_enforcement_enabled() -> None:
    """The measurement arm mutates a live setting; it must not leak an ON default."""
    from app.config import Settings, settings

    assert Settings().ai_soc_live_capability_enforcement_enabled is False
    assert settings.ai_soc_live_capability_enforcement_enabled is False


def test_full_pipeline_guard_is_the_only_final_commit_observer() -> None:
    """The in-catalogue contract guard routes through the real `/chat` entry point.

    Static reachability, deliberately: executing 155 chat turns belongs in the guard
    itself, not in a matrix pin.
    """
    import app.evals.in_catalogue_contract as guard

    assert guard.capture_contract_row.__module__ == "app.evals.in_catalogue_contract"
    source = Path(guard.__file__).read_text(encoding="utf-8")
    assert "from app.api.routes_chat import chat" in source, (
        "the in-catalogue guard no longer enters through routes_chat — it was the only "
        "instrument that observed the cisco.ot.029 final-route commit at B5"
    )
