"""Plan 8 REL0 — Cisco restart is human/operator only; code never restarts the model."""

from __future__ import annotations

import ast
from pathlib import Path

from app.llm.sidecar_governance import (
    CIRCUIT_OPEN,
    request_human_model_restart,
    reset_t4_circuit,
    t4_circuit_status,
)

_SEAM_FILES = (
    Path("app/llm/sidecar_governance.py"),
    Path("app/chat/semantic_t4_understanding.py"),
    Path("app/graph/resource_planner_graph.py"),
    Path("app/orchestration"),
)

_FORBIDDEN_SUBSTRINGS = (
    "systemctl restart",
    "systemctl reboot",
    "docker restart",
    "docker compose restart llama",
    "service llama-server restart",
    "kill -9",
    "pkill llama",
)


def test_request_human_restart_does_not_execute_a_restart() -> None:
    reset_t4_circuit()
    packet = request_human_model_restart()
    assert packet["restart_authorized"] is False
    assert packet["human_action_required"] is True
    assert packet["circuit_state"] == CIRCUIT_OPEN
    assert "does not restart" in packet["procedure"]
    assert t4_circuit_status()["state"] == CIRCUIT_OPEN


def test_sidecar_and_planner_have_no_restart_command() -> None:
    hits: list[str] = []
    roots = [Path("app/llm/sidecar_governance.py"), Path("app/chat/semantic_t4_understanding.py")]
    for path in roots:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for needle in _FORBIDDEN_SUBSTRINGS:
            if needle in lowered:
                hits.append(f"{path}: {needle}")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"system", "popen"}:
                    hits.append(f"{path}: {ast.dump(node.func)}")
            if isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names):
                if path.name == "sidecar_governance.py":
                    hits.append(f"{path}: import subprocess")
            if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                if path.name == "sidecar_governance.py":
                    hits.append(f"{path}: from subprocess")
    assert hits == []


def test_recovery_path_is_open_then_human_then_health_then_half_open() -> None:
    """Documented REL0 path: failure → OPEN/degrade → human action → external restart → health → HALF_OPEN."""
    from app.llm.sidecar_governance import record_manual_model_restart, run_sidecar_llm_with_timeout
    import os

    os.environ["AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD"] = "1"
    reset_t4_circuit()
    run_sidecar_llm_with_timeout(lambda: (_ for _ in ()).throw(ConnectionError("down")), timeout_seconds=1.0)
    assert t4_circuit_status()["state"] == CIRCUIT_OPEN
    packet = request_human_model_restart()
    assert packet["restart_authorized"] is False
    # Health verification is an inference probe result supplied by the operator, not /v1/models.
    after = record_manual_model_restart(
        inference_health_ok=True,
        evidence={"probe": "bounded_generation", "not": "/v1/models"},
    )
    assert after["state"] == "HALF_OPEN"
    assert after["last_health"]["source"] == "operator_inference_probe"
    closed = run_sidecar_llm_with_timeout(lambda: "ok", timeout_seconds=1.0)
    assert closed.raw_output == "ok"
    assert t4_circuit_status()["state"] == "CLOSED"
