"""Plan 8 REL0 — T4 circuit CLOSED → OPEN → human restart → HALF_OPEN → CLOSED."""

from __future__ import annotations

import os

from app.llm.sidecar_governance import (
    CIRCUIT_CLOSED,
    CIRCUIT_HALF_OPEN,
    CIRCUIT_OPEN,
    FAILURE_CIRCUIT_OPEN,
    NOTE_HUMAN_ACTION_REQUIRED,
    record_manual_model_restart,
    reset_t4_circuit,
    run_sidecar_llm_with_timeout,
    t4_circuit_status,
)


def _failing() -> str:
    raise ConnectionRefusedError("model down")


def test_repeated_failures_open_circuit_and_require_human_action(monkeypatch) -> None:
    monkeypatch.setenv("AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD", "3")
    reset_t4_circuit()
    for _ in range(3):
        result = run_sidecar_llm_with_timeout(_failing, timeout_seconds=1.0)
        assert result.failure_kind == "provider_unavailable"
    status = t4_circuit_status()
    assert status["state"] == CIRCUIT_OPEN
    assert status["human_action_required"] is True

    calls = {"n": 0}

    def _must_not_run() -> str:
        calls["n"] += 1
        return "should-not"

    shed = run_sidecar_llm_with_timeout(_must_not_run, timeout_seconds=1.0)
    assert calls["n"] == 0
    assert shed.failure_kind == FAILURE_CIRCUIT_OPEN
    assert shed.human_action_required is True
    assert NOTE_HUMAN_ACTION_REQUIRED in shed.notes
    assert t4_circuit_status()["state"] == CIRCUIT_OPEN


def test_open_circuit_does_not_auto_close() -> None:
    os.environ["AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD"] = "1"
    reset_t4_circuit()
    run_sidecar_llm_with_timeout(_failing, timeout_seconds=1.0)
    assert t4_circuit_status()["state"] == CIRCUIT_OPEN
    run_sidecar_llm_with_timeout(lambda: "ok", timeout_seconds=1.0)
    assert t4_circuit_status()["state"] == CIRCUIT_OPEN


def test_manual_restart_without_inference_health_stays_open() -> None:
    os.environ["AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD"] = "1"
    reset_t4_circuit()
    run_sidecar_llm_with_timeout(_failing, timeout_seconds=1.0)
    status = record_manual_model_restart(inference_health_ok=False, evidence={"probe": "/v1/models"})
    assert status["state"] == CIRCUIT_OPEN
    assert status["human_action_required"] is True


def test_health_ok_then_half_open_success_closes() -> None:
    os.environ["AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD"] = "1"
    reset_t4_circuit()
    run_sidecar_llm_with_timeout(_failing, timeout_seconds=1.0)
    status = record_manual_model_restart(
        inference_health_ok=True,
        evidence={"probe": "bounded_generation", "elapsed_ms": 800},
    )
    assert status["state"] == CIRCUIT_HALF_OPEN
    ok = run_sidecar_llm_with_timeout(lambda: "recovered", timeout_seconds=1.0)
    assert ok.raw_output == "recovered"
    assert t4_circuit_status()["state"] == CIRCUIT_CLOSED


def test_half_open_failure_reopens() -> None:
    os.environ["AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD"] = "1"
    reset_t4_circuit()
    run_sidecar_llm_with_timeout(_failing, timeout_seconds=1.0)
    record_manual_model_restart(inference_health_ok=True, evidence={"probe": "bounded_generation"})
    again = run_sidecar_llm_with_timeout(_failing, timeout_seconds=1.0)
    assert again.failure_kind == "provider_unavailable"
    assert t4_circuit_status()["state"] == CIRCUIT_OPEN
    assert t4_circuit_status()["human_action_required"] is True
