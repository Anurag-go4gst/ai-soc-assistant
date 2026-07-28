"""Unit tests for live synthesis benchmark harness (workstream E phase 1 + phase 2 wiring)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.evals.live_synthesis_benchmark import (
    APPROVED_LIVE_CASE_IDS,
    LIVE_AUTHORIZATION_ENV,
    LIVE_EVIDENCE_CLASS,
    LiveHarnessConfig,
    LiveHarnessRejected,
    build_live_harness_config,
    estimate_live_probe_cost,
    parse_probe_matrix,
    run_live_benchmark,
    run_stub_benchmark,
    summarize_benchmark,
    validate_live_authorization,
    validate_live_case_ids,
    validate_no_arbitrary_query_inputs,
)
from app.synthesis.turn_timing import RunKind, SynthesisPath, TurnOutcome, sanitize_turn_timing_payload

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "run_live_synthesis_baseline_benchmark.py"


def _timing(
    *,
    run_kind: str = "unknown",
    synthesis_path: str = SynthesisPath.SKIPPED.value,
    outcome: str = TurnOutcome.SKIPPED.value,
    end_to_end: int = 1200,
) -> dict[str, Any]:
    return sanitize_turn_timing_payload(
        {
            "schema_version": "1",
            "run_kind": run_kind,
            "synthesis_path": synthesis_path,
            "outcome": outcome,
            "timeout_applied": False,
            "fallback_used": False,
            "segments_ms": {
                "canonical_planning": 100,
                "retrieval_spl": 200,
                "synthesis_endpoint": None,
                "application_overhead": 50,
                "end_to_end": end_to_end,
            },
            "endpoint_detail": {
                "provider_label": "local",
                "model": "test-model",
                "http_round_trip_ms": None,
            },
        }
    )


class FakeLiveHttpClient:
    def __init__(
        self,
        *,
        health_status: int = 200,
        health_body: dict[str, Any] | None = None,
        settings_status: int = 200,
        settings_body: dict[str, Any] | None = None,
        chat_responses: dict[str, tuple[int, dict[str, Any], int]] | None = None,
        chat_calls: list[str] | None = None,
    ) -> None:
        self.health_status = health_status
        self.health_body = health_body or {
            "status": "ok",
            "readiness": {"database_migrations": {"ready": True}},
        }
        self.settings_status = settings_status
        self.settings_body = settings_body or {
            "mcp": {
                "mode": "mock",
                "global_execution_enabled": False,
                "splunk_live_readiness": {"ready_for_live_splunk_mcp": False},
                "servers": [],
            }
        }
        self.chat_responses = chat_responses or {}
        self.chat_calls = chat_calls if chat_calls is not None else []

    def fetch_health(self) -> tuple[int, dict[str, Any]]:
        return self.health_status, self.health_body

    def fetch_settings_status(self) -> tuple[int, dict[str, Any]]:
        return self.settings_status, self.settings_body

    def post_chat(self, *, case_id: str, session_id: str, timeout_s: int) -> tuple[int, dict[str, Any], int]:
        self.chat_calls.append(case_id)
        if case_id in self.chat_responses:
            return self.chat_responses[case_id]
        return (
            200,
            {
                "workflow_plan": {"execution_enabled": False},
                "control_plane_trace": {"turn_timing": _timing()},
            },
            1500,
        )


def _live_config(case_ids: tuple[str, ...] = ("E-P1",)) -> LiveHarnessConfig:
    return LiveHarnessConfig(
        base_url="http://127.0.0.1:8010",
        case_ids=case_ids,
        confirm_live=True,
        probe_timeout_s=30,
        inter_probe_pause_s=0.0,
        session_id="bench-session",
    )


def test_stub_benchmark_produces_sanitized_summary() -> None:
    report = run_stub_benchmark()
    payload = report.to_sanitized_dict()
    assert payload["mode"] == "stub"
    assert payload["evidence_class"] == "stub_deterministic_not_measured"
    assert payload["run_count"] == len(parse_probe_matrix())
    assert payload["summary"]["sample_count"] == payload["run_count"]
    assert "end_to_end_ms" in payload["summary"]
    assert "synthesis_path_counts" in payload["summary"]
    for row in payload["runs"]:
        assert "turn_timing" in row
        assert "schema_version" in row["turn_timing"]
        assert "segments_ms" in row["turn_timing"]


def test_estimate_live_probe_cost_is_heuristic() -> None:
    cost = estimate_live_probe_cost()
    assert cost["probe_count"] == 6
    assert cost["estimated_runtime_minutes"] > 0
    assert "note" in cost


def test_summarize_benchmark_handles_empty_runs() -> None:
    from app.evals.live_synthesis_benchmark import BenchmarkReport

    summary = summarize_benchmark(BenchmarkReport())
    assert summary["end_to_end_ms"]["p50"] is None
    assert summary["timeout_rate"] is None


def test_missing_confirm_live_rejects() -> None:
    with pytest.raises(LiveHarnessRejected) as exc:
        validate_live_authorization(confirm_live=False)
    assert exc.value.code == "confirm_live_required"


def test_missing_authorization_env_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LIVE_AUTHORIZATION_ENV, raising=False)
    with pytest.raises(LiveHarnessRejected) as exc:
        validate_live_authorization(confirm_live=True)
    assert exc.value.code == "authorization_env_required"


def test_arbitrary_query_input_unsupported() -> None:
    with pytest.raises(LiveHarnessRejected) as exc:
        validate_no_arbitrary_query_inputs(message="show me everything")
    assert exc.value.code == "arbitrary_query_unsupported"


def test_unapproved_case_id_rejects() -> None:
    with pytest.raises(LiveHarnessRejected) as exc:
        validate_live_case_ids(["E-P1", "E-UNKNOWN"])
    assert exc.value.code == "unapproved_case_id"


def test_unhealthy_health_rejects() -> None:
    client = FakeLiveHttpClient(
        health_status=503,
        health_body={"status": "degraded"},
    )
    report = run_live_benchmark(_live_config(), client=client)
    assert report.aborted is True
    assert report.abort_reason == "health_not_ready"
    assert report.runs == []


def test_migration_not_ready_rejects() -> None:
    client = FakeLiveHttpClient(
        health_body={
            "status": "ok",
            "readiness": {"database_migrations": {"ready": False, "missing_versions": ["001"]}},
        }
    )
    report = run_live_benchmark(_live_config(), client=client)
    assert report.aborted is True
    assert report.abort_reason == "migrations_not_ready"


def test_missing_auth_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_AUTH_ENABLED", "true")
    monkeypatch.delenv("APP_AUTH_PASSWORD", raising=False)
    monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, "1")
    with pytest.raises(LiveHarnessRejected) as exc:
        build_live_harness_config(
            base_url="http://127.0.0.1:8010",
            case_ids=["E-P1"],
            confirm_live=True,
        )
    assert exc.value.code == "auth_credentials_required"


def test_execution_enabled_true_aborts() -> None:
    client = FakeLiveHttpClient(
        chat_responses={
            "E-P1": (
                200,
                {
                    "workflow_plan": {"execution_enabled": True},
                    "control_plane_trace": {"turn_timing": _timing()},
                },
                900,
            )
        }
    )
    report = run_live_benchmark(_live_config(("E-P1", "E-P2")), client=client)
    assert report.aborted is True
    assert report.abort_reason == "execution_enabled_true"
    assert len(report.runs) == 1
    assert client.chat_calls == ["E-P1"]


def test_live_connector_selection_aborts() -> None:
    client = FakeLiveHttpClient(
        settings_body={
            "mcp": {
                "mode": "registry",
                "global_execution_enabled": True,
                "splunk_live_readiness": {"ready_for_live_splunk_mcp": False},
                "servers": [],
            }
        }
    )
    report = run_live_benchmark(_live_config(), client=client)
    assert report.aborted is True
    assert report.abort_reason == "live_connector_selectable"


def test_timeout_records_once_with_no_retry() -> None:
    client = FakeLiveHttpClient(
        chat_responses={
            "E-P1": (
                200,
                {
                    "workflow_plan": {"execution_enabled": False},
                    "control_plane_trace": {
                        "turn_timing": _timing(
                            outcome=TurnOutcome.TIMEOUT.value,
                            synthesis_path=SynthesisPath.LAB.value,
                        )
                    },
                },
                300000,
            )
        }
    )
    report = run_live_benchmark(_live_config(("E-P1", "E-P2")), client=client, sleep_fn=lambda _: None)
    assert len(report.runs) == 2
    assert client.chat_calls == ["E-P1", "E-P2"]
    assert report.runs[0].turn_timing["outcome"] == TurnOutcome.TIMEOUT.value


def test_non_200_aborts_with_no_retry() -> None:
    client = FakeLiveHttpClient(
        chat_responses={
            "E-P1": (500, {"detail": "server error"}, 120),
        }
    )
    report = run_live_benchmark(_live_config(("E-P1", "E-P2")), client=client)
    assert report.aborted is True
    assert report.abort_reason == "http_500"
    assert len(report.runs) == 1
    assert client.chat_calls == ["E-P1"]


def test_skipped_synthesis_remains_valid_single_result() -> None:
    client = FakeLiveHttpClient(
        chat_responses={
            "E-P6": (
                200,
                {
                    "workflow_plan": {"execution_enabled": False},
                    "control_plane_trace": {
                        "turn_timing": _timing(
                            synthesis_path=SynthesisPath.SKIPPED.value,
                            outcome=TurnOutcome.SKIPPED.value,
                        )
                    },
                },
                800,
            )
        }
    )
    report = run_live_benchmark(_live_config(("E-P6",)), client=client)
    assert report.aborted is False
    assert report.runs[0].error is None
    assert report.runs[0].response_valid is True
    assert report.runs[0].turn_timing["synthesis_path"] == SynthesisPath.SKIPPED.value


def test_secrets_prompts_answers_absent_from_json() -> None:
    client = FakeLiveHttpClient(
        chat_responses={
            "E-P1": (
                200,
                {
                    "workflow_plan": {"execution_enabled": False},
                    "message": "secret prompt must not leak",
                    "answer": "secret answer must not leak",
                    "control_plane_trace": {
                        "turn_timing": _timing(),
                        "prompt": "do not store",
                    },
                },
                500,
            )
        }
    )
    report = run_live_benchmark(_live_config(("E-P1",)), client=client)
    payload = report.to_sanitized_dict()
    serialized = json.dumps(payload)
    assert "secret prompt" not in serialized
    assert "secret answer" not in serialized
    assert "do not store" not in serialized
    assert "password" not in serialized.lower()


def test_client_run_kind_does_not_overwrite_server_run_kind() -> None:
    client = FakeLiveHttpClient(
        chat_responses={
            "E-P2": (
                200,
                {
                    "workflow_plan": {"execution_enabled": False},
                    "control_plane_trace": {"turn_timing": _timing(run_kind=RunKind.UNKNOWN.value)},
                },
                700,
            )
        }
    )
    report = run_live_benchmark(_live_config(("E-P1", "E-P2")), client=client, sleep_fn=lambda _: None)
    warm_row = report.runs[1]
    assert warm_row.client_run_kind == RunKind.WARM.value
    assert warm_row.server_run_kind == RunKind.UNKNOWN.value
    assert warm_row.turn_timing["run_kind"] == RunKind.UNKNOWN.value


def test_maximum_run_count_enforced() -> None:
    with pytest.raises(LiveHarnessRejected) as exc:
        validate_live_case_ids(list(APPROVED_LIVE_CASE_IDS) + ["E-P1"])
    assert exc.value.code == "max_probe_count_exceeded"


def test_partial_report_written_on_abort(tmp_path: Path) -> None:
    client = FakeLiveHttpClient(
        chat_responses={
            "E-P1": (500, {}, 100),
        }
    )
    report = run_live_benchmark(_live_config(("E-P1", "E-P2")), client=client)
    out = tmp_path / "partial.json"
    out.write_text(json.dumps(report.to_sanitized_dict(), indent=2), encoding="utf-8")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["aborted"] is True
    assert payload["run_count"] == 1


def test_live_report_labels_exploratory_not_slo_baseline() -> None:
    client = FakeLiveHttpClient()
    report = run_live_benchmark(_live_config(("E-P1",)), client=client)
    payload = report.to_sanitized_dict()
    assert payload["evidence_class"] == LIVE_EVIDENCE_CLASS
    assert payload["summary"]["slo_baseline"] is False
    assert "percentile_warning" in payload["summary"]


def test_cli_live_missing_confirm_live_rejects() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT / 'backend'}:{REPO_ROOT}"
    env[LIVE_AUTHORIZATION_ENV] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--live",
            "--base-url",
            "http://127.0.0.1:8010",
            "--cases",
            "E-P1",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "confirm_live_required" in proc.stderr


def test_stub_mode_remains_unchanged() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT / 'backend'}:{REPO_ROOT}"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--stub"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "stub benchmark complete" in proc.stdout
