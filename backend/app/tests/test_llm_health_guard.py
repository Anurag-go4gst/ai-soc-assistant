"""P2-A item 7: health guard baseline vs resilience gate.

Baseline runs (no ``--restart``) must only measure and report; resilience runs
(``--restart``) may restart a degraded single-slot model. The tok/s + wall-time +
reachability decision must classify health consistently. Live network is never touched:
``measure_tok_per_s`` and ``restart_service`` are patched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "llm_health_guard.py"
_spec = importlib.util.spec_from_file_location("llm_health_guard", _SCRIPT)
assert _spec and _spec.loader
hg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hg)


def _run(monkeypatch, argv, before, after=None):
    monkeypatch.setattr(sys, "argv", ["llm_health_guard.py", *argv])
    measures = [before] + ([after] if after is not None else [])
    calls = iter(measures)
    monkeypatch.setattr(hg, "measure_tok_per_s", lambda **_: next(calls))
    restarts: list[bool] = []

    def _fake_restart():
        restarts.append(True)
        return {"restarted": True, "cmd": "fake"}

    monkeypatch.setattr(hg, "restart_service", _fake_restart)
    rc = hg.main()
    return rc, restarts


def test_healthy_baseline_returns_zero_no_restart(monkeypatch) -> None:
    before = {"reachable": True, "tok_per_s": 9.0, "wall_s": 10.0}
    rc, restarts = _run(monkeypatch, [], before)
    assert rc == 0
    assert restarts == []


def test_degraded_baseline_never_restarts(monkeypatch) -> None:
    # Slow tok/s + over wall budget, but baseline (no --restart) must not restart.
    before = {"reachable": True, "tok_per_s": 0.5, "wall_s": 999.0}
    rc, restarts = _run(monkeypatch, ["--threshold", "3", "--max-wall-seconds", "120"], before)
    assert rc == 1
    assert restarts == []


def test_degraded_resilience_restarts_and_recovers(monkeypatch) -> None:
    before = {"reachable": True, "tok_per_s": 0.5, "wall_s": 999.0}
    after = {"reachable": True, "tok_per_s": 5.0, "wall_s": 30.0}
    rc, restarts = _run(
        monkeypatch,
        ["--restart", "--threshold", "3", "--max-wall-seconds", "120"],
        before,
        after,
    )
    assert rc == 0
    assert restarts == [True]


def test_wall_time_over_budget_is_degraded(monkeypatch) -> None:
    # Good tok/s but breaches the wall-time gate → unhealthy.
    before = {"reachable": True, "tok_per_s": 9.0, "wall_s": 500.0}
    rc, restarts = _run(monkeypatch, ["--max-wall-seconds", "120"], before)
    assert rc == 1
    assert restarts == []


def test_unreachable_is_degraded(monkeypatch) -> None:
    before = {"reachable": False, "tok_per_s": 0.0, "error": "health_check_failed"}
    rc, restarts = _run(monkeypatch, [], before)
    assert rc == 1
    assert restarts == []
