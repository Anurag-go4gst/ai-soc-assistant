"""§4.5 live-run orchestrator: preflight gate, posture, abort threshold, manifest."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "run_live_efficacy_profile.py"
_spec = importlib.util.spec_from_file_location("run_live_efficacy_profile", _SCRIPT)
assert _spec and _spec.loader
orch = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = orch  # dataclass needs the module registered
_spec.loader.exec_module(orch)


class _FakeClient:
    """Canned HTTP responses keyed by (method, path-prefix)."""

    def __init__(self, *, health=200, debug=200, readiness=200, llm: dict[str, Any] | None = None,
                 login_ok=True, debug_access=True) -> None:
        self._health, self._debug, self._readiness = health, debug, readiness
        self._llm = llm or {"llm_enabled": False, "llm_mode": "mock"}
        self._login_ok, self._debug_access = login_ok, debug_access

    def login(self) -> dict[str, Any]:
        if not self._login_ok:
            raise RuntimeError("login failed")
        return {"debug_access": self._debug_access}

    def request(self, method: str, path: str, *_a, **_k):
        if path.startswith("/health"):
            return self._health, {"status": "ok"}, None
        if path.startswith("/debug/traces"):
            return self._debug, {"traces": []}, None
        if path.startswith("/debug/readiness"):
            return self._readiness, {"llm": self._llm, "rag": {}, "telemetry": {}}, None
        return 404, {}, None


def test_posture_deterministic_requires_llm_off() -> None:
    ok, miss = orch.check_posture({"llm": {"llm_enabled": False}}, "deterministic")
    assert ok and miss == []
    bad, miss2 = orch.check_posture({"llm": {"llm_enabled": True}}, "deterministic")
    assert not bad and miss2


def test_posture_llm_requires_synthesis_on() -> None:
    ok, _ = orch.check_posture({"llm": {"llm_enabled": True, "final_synthesis_enabled": True}}, "llm")
    assert ok
    bad, miss = orch.check_posture({"llm": {"llm_enabled": True, "final_synthesis_enabled": False}}, "llm")
    assert not bad and any("final_synthesis_enabled" in m for m in miss)


def test_preflight_passes_for_matched_deterministic() -> None:
    client = _FakeClient(llm={"llm_enabled": False, "llm_mode": "disabled"})
    result = orch.run_preflight(client, "deterministic")
    assert result.ok is True


def test_preflight_aborts_on_posture_mismatch() -> None:
    # Server LLM is on but profile asked deterministic -> abort.
    client = _FakeClient(llm={"llm_enabled": True, "llm_mode": "local"})
    result = orch.run_preflight(client, "deterministic")
    assert result.ok is False
    assert any(c["check"].startswith("posture_matches") and not c["ok"] for c in result.checks)


def test_preflight_llm_profile_needs_reachable_model() -> None:
    # Enabled flag but mock mode -> not reachable -> abort.
    client = _FakeClient(llm={"llm_enabled": True, "final_synthesis_enabled": True, "llm_mode": "mock"})
    result = orch.run_preflight(client, "llm")
    assert result.ok is False
    assert any(c["check"] == "llm_reachable" and not c["ok"] for c in result.checks)


def test_preflight_aborts_on_debug_canary_failure() -> None:
    client = _FakeClient(debug=403, llm={"llm_enabled": False, "llm_mode": "disabled"})
    result = orch.run_preflight(client, "deterministic")
    assert result.ok is False
    assert any(c["check"] == "debug_bundle_canary" and not c["ok"] for c in result.checks)


def test_preflight_aborts_on_login_failure() -> None:
    client = _FakeClient(login_ok=False)
    result = orch.run_preflight(client, "deterministic")
    assert result.ok is False


def test_abort_threshold_counts_only_5xx() -> None:
    summary = {"total": 100, "http_success": 95,
               "failure_classification": {"by_error_code": {"500": 3, "0": 2, "404": 1}}}
    # 3/100 = 3% > 2% -> abort. The 2 transport-0 and 1 404 are excluded.
    assert orch.abort_threshold_exceeded(summary, 0.02) is True
    assert orch._http_5xx_count(summary) == 3


def test_abort_threshold_not_triggered_by_transport_timeouts() -> None:
    summary = {"total": 100, "http_success": 90,
               "failure_classification": {"by_error_code": {"0": 10}}}  # all transport-0
    assert orch.abort_threshold_exceeded(summary, 0.02) is False


def test_manifest_has_revision_scorer_and_reliability() -> None:
    summary = {"total": 100, "http_success": 98,
               "failure_classification": {"by_error_code": {"500": 1, "0": 1}},
               "resilience": {"retry_attempted": 1}}
    pf = orch.PreflightResult()
    pf.record("backend_health", True, {})
    manifest = orch.build_archive_manifest(
        profile="llm", summary=summary,
        readiness={"llm": {"llm_enabled": True, "llm_mode": "local"}}, preflight=pf,
    )
    assert manifest["scorer_version"] == orch.SCORER_VERSION
    assert manifest["code_revision"]
    assert manifest["reliability_first_attempt"]["http_5xx"] == 1
    assert manifest["reliability_first_attempt"]["success_rate"] == 0.98
    assert manifest["config_snapshot"]["llm_mode"] == "local"
    assert manifest["abort_5xx_triggered"] is False
