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
    ALLOWLISTED_ERROR_CODES,
    APPROVED_LIVE_CASE_IDS,
    LIVE_AUTHORIZATION_ENV,
    LIVE_EVIDENCE_CLASS,
    LiveHarnessConfig,
    LiveHarnessRejected,
    assert_mock_connector_posture,
    build_live_harness_config,
    estimate_live_probe_cost,
    parse_probe_matrix,
    run_live_benchmark,
    run_stub_benchmark,
    sanitize_report_error_code,
    summarize_benchmark,
    validate_live_authorization,
    validate_live_case_ids,
    validate_no_arbitrary_query_inputs,
)
from app.synthesis.turn_timing import RunKind, SynthesisPath, TurnOutcome, sanitize_turn_timing_payload

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "run_live_synthesis_baseline_benchmark.py"


def _production_mock_settings(*, global_execution_enabled: bool = True) -> dict[str, Any]:
    return {
        "mcp": {
            "mode": "mock",
            "discovery_status": "mock",
            "status_detail": "mock",
            "global_execution_enabled": global_execution_enabled,
            "base_url_configured": False,
            "token_configured": False,
            "splunk_mcp_enabled": False,
            "splunk_live_readiness": {"ready_for_live_splunk_mcp": False},
            "servers": [
                {
                    "name": "mock",
                    "type": "splunk",
                    "transport": "mock",
                    "url_configured": False,
                    "execution_enabled": global_execution_enabled,
                }
            ],
        }
    }


def _production_mock_providers() -> dict[str, Any]:
    return {
        "providers": [
            {
                "provider_id": "splunk_mcp",
                "provider_type": "splunk_mcp",
                "enabled": False,
                "available": False,
                "auth_configured": False,
                "write_supported": False,
            },
            {
                "provider_id": "mock_asset_inventory",
                "provider_type": "asset_inventory",
                "enabled": True,
                "available": True,
                "auth_configured": False,
                "write_supported": False,
            },
        ]
    }


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
        providers_status: int = 200,
        providers_body: dict[str, Any] | None = None,
        chat_responses: dict[str, tuple[int, dict[str, Any], int]] | None = None,
        chat_calls: list[tuple[str, str]] | None = None,
    ) -> None:
        self.health_status = health_status
        self.health_body = health_body or {
            "status": "ok",
            "readiness": {"database_migrations": {"ready": True}},
        }
        self.settings_status = settings_status
        self.settings_body = settings_body or _production_mock_settings()
        self.providers_status = providers_status
        self.providers_body = providers_body or _production_mock_providers()
        self.chat_responses = chat_responses or {}
        self.chat_calls = chat_calls if chat_calls is not None else []

    def fetch_health(self) -> tuple[int, dict[str, Any]]:
        return self.health_status, self.health_body

    def fetch_settings_status(self) -> tuple[int, dict[str, Any]]:
        return self.settings_status, self.settings_body

    def fetch_providers_status(self) -> tuple[int, dict[str, Any]]:
        return self.providers_status, self.providers_body

    def post_chat(self, *, case_id: str, session_id: str, timeout_s: int) -> tuple[int, dict[str, Any], int]:
        self.chat_calls.append((case_id, session_id))
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
        run_id="benchrun",
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
    assert cost["heuristic_duration_minutes"] == "10-15"
    assert cost["maximum_timeout_bound_minutes"] >= 30
    assert "note" in cost


def test_summarize_benchmark_handles_empty_runs() -> None:
    from app.evals.live_synthesis_benchmark import BenchmarkReport

    summary = summarize_benchmark(BenchmarkReport())
    assert summary["end_to_end_ms"]["p50"] is None
    assert summary["timeout_rate"] is None


def test_missing_confirm_live_rejects() -> None:
    with pytest.raises(LiveHarnessRejected) as exc:
        validate_live_authorization(confirm_live=False)
    assert sanitize_report_error_code(exc.value.code) == "authorization_missing"


def test_missing_authorization_env_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LIVE_AUTHORIZATION_ENV, raising=False)
    with pytest.raises(LiveHarnessRejected) as exc:
        validate_live_authorization(confirm_live=True)
    assert sanitize_report_error_code(exc.value.code) == "authorization_missing"


def test_arbitrary_query_input_unsupported() -> None:
    with pytest.raises(LiveHarnessRejected):
        validate_no_arbitrary_query_inputs(message="show me everything")


def test_unapproved_case_id_rejects() -> None:
    with pytest.raises(LiveHarnessRejected):
        validate_live_case_ids(["E-P1", "E-UNKNOWN"])


def test_production_mock_only_flags_are_accepted() -> None:
    assert_mock_connector_posture(
        _production_mock_settings(global_execution_enabled=True),
        _production_mock_providers(),
    )


def test_live_connector_availability_is_rejected() -> None:
    settings = _production_mock_settings()
    settings["mcp"]["mode"] = "registry"
    settings["mcp"]["discovery_status"] = "configured_unavailable_without_real_adapter"
    with pytest.raises(LiveHarnessRejected) as exc:
        assert_mock_connector_posture(settings, _production_mock_providers())
    assert sanitize_report_error_code(exc.value.code) == "live_connector_selectable"


def test_unhealthy_health_rejects() -> None:
    client = FakeLiveHttpClient(health_status=503, health_body={"status": "degraded"})
    report = run_live_benchmark(_live_config(), client=client)
    assert report.aborted is True
    assert report.abort_reason == "health_not_ready"


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


def test_missing_secure_credentials_reject_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_AUTH_ENABLED", "true")
    monkeypatch.delenv("APP_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("APP_AUTH_USER", raising=False)
    monkeypatch.setenv(LIVE_AUTHORIZATION_ENV, "1")
    with pytest.raises(LiveHarnessRejected) as exc:
        build_live_harness_config(
            base_url="http://127.0.0.1:8010",
            case_ids=["E-P1"],
            confirm_live=True,
        )
    assert sanitize_report_error_code(exc.value.code) == "authentication_failed"


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
    assert report.abort_reason == "execution_enabled"
    assert len(report.runs) == 1


def test_live_connector_selection_aborts_at_preflight() -> None:
    settings = _production_mock_settings()
    settings["mcp"]["base_url_configured"] = True
    client = FakeLiveHttpClient(settings_body=settings)
    report = run_live_benchmark(_live_config(), client=client)
    assert report.aborted is True
    assert report.abort_reason == "live_connector_selectable"


def test_timeout_aborts_remaining_probes_with_no_retry() -> None:
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
    assert len(report.runs) == 1
    assert report.aborted is True
    assert report.abort_reason == "request_timeout"
    assert client.chat_calls == [("E-P1", "live-synth-bench-benchrun-knowledge")]


def test_non_200_aborts_with_no_retry() -> None:
    client = FakeLiveHttpClient(
        chat_responses={
            "E-P1": (500, {"detail": "server error at https://secret.example.invalid"}, 120),
        }
    )
    report = run_live_benchmark(_live_config(("E-P1", "E-P2")), client=client)
    assert report.aborted is True
    assert report.abort_reason == "http_non_success"
    assert len(report.runs) == 1
    payload = report.to_sanitized_dict()
    assert "secret.example" not in json.dumps(payload)


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


def test_e_p3_not_relabelled_warm_when_third_in_sequence() -> None:
    client = FakeLiveHttpClient()
    report = run_live_benchmark(
        _live_config(("E-P1", "E-P2", "E-P3")),
        client=client,
        sleep_fn=lambda _: None,
    )
    e_p3 = report.runs[2]
    assert e_p3.matrix_run_kind == "cold"
    assert e_p3.sequence_position == "subsequent"
    assert e_p3.pair_id == "alert_pair"
    assert e_p3.pair_position == "first"


def test_fixed_matrix_and_pair_labels() -> None:
    client = FakeLiveHttpClient()
    report = run_live_benchmark(
        _live_config(("E-P1", "E-P2", "E-P3", "E-P4", "E-P5", "E-P6")),
        client=client,
        sleep_fn=lambda _: None,
    )
    labels = {
        row.case_id: (
            row.matrix_run_kind,
            row.pair_id,
            row.pair_position,
            row.sequence_position,
        )
        for row in report.runs
    }
    assert labels["E-P1"] == ("cold", "knowledge_pair", "first", "first")
    assert labels["E-P2"] == ("warm", "knowledge_pair", "repeat", "subsequent")
    assert labels["E-P3"] == ("cold", "alert_pair", "first", "subsequent")
    assert labels["E-P4"] == ("warm", "alert_pair", "repeat", "subsequent")
    assert labels["E-P5"] == ("cold-intent", "none", "standalone", "subsequent")
    assert labels["E-P6"] == ("cold-intent", "none", "standalone", "subsequent")


def test_server_run_kind_remains_separate() -> None:
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
    assert warm_row.matrix_run_kind == "warm"
    assert warm_row.server_run_kind == RunKind.UNKNOWN.value
    assert warm_row.turn_timing["run_kind"] == RunKind.UNKNOWN.value


def test_raw_exception_url_response_content_cannot_enter_error() -> None:
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
    if payload["runs"][0]["error"] is not None:
        assert payload["runs"][0]["error"] in ALLOWLISTED_ERROR_CODES


def test_repeat_pairs_share_session_posture() -> None:
    client = FakeLiveHttpClient()
    run_live_benchmark(_live_config(("E-P1", "E-P2", "E-P3", "E-P4")), client=client, sleep_fn=lambda _: None)
    sessions = {case_id: session for case_id, session in client.chat_calls}
    assert sessions["E-P1"] == sessions["E-P2"]
    assert sessions["E-P3"] == sessions["E-P4"]
    assert sessions["E-P1"] != sessions["E-P3"]


def test_maximum_run_count_enforced() -> None:
    with pytest.raises(LiveHarnessRejected):
        validate_live_case_ids(list(APPROVED_LIVE_CASE_IDS) + ["E-P1"])


def test_partial_report_written_on_abort(tmp_path: Path) -> None:
    client = FakeLiveHttpClient(chat_responses={"E-P1": (500, {}, 100)})
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
    assert "authorization_missing" in proc.stderr


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
