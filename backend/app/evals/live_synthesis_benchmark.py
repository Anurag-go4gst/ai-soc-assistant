"""Live synthesis baseline benchmark harness (workstream E).

Deterministic stub mode supports unit tests and CI-free verification.
Live HTTP probes require explicit operator opt-in, authorization env, and fixed
approved case definitions — no arbitrary query text.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from app.evals.percentile_stats import percentile_summary
from app.synthesis.turn_timing import (
    RunKind,
    SynthesisPath,
    TurnOutcome,
    sanitize_turn_timing_payload,
)

PROBE_MATRIX_VERSION = "1"
LIVE_HARNESS_SCHEMA_VERSION = "1"
LIVE_AUTHORIZATION_ENV = "AI_SOC_LIVE_BENCHMARK_AUTHORIZED"
MAX_LIVE_PROBES_PER_RUN = 6
DEFAULT_PROBE_TIMEOUT_S = 300
DEFAULT_INTER_PROBE_PAUSE_S = 2.0
DEFAULT_LIVE_OUTPUT_PATH = "/tmp/live_synthesis_benchmark_report.json"
LIVE_EVIDENCE_CLASS = "exploratory_live_wiring_validation"
LIVE_PERCENTILE_WARNING = (
    "Six exploratory probes are statistically insufficient for SLO definition; "
    "percentiles are descriptive only."
)

# Closed case set for controlled baseline (sanitized ids only — no raw queries in artifacts).
DEFAULT_PROBE_MATRIX: tuple[dict[str, str], ...] = (
    {"case_id": "E-P1", "profile": "knowledge_recall", "run_kind": "cold"},
    {"case_id": "E-P2", "profile": "knowledge_recall", "run_kind": "warm"},
    {"case_id": "E-P3", "profile": "alert_summary", "run_kind": "cold"},
    {"case_id": "E-P4", "profile": "alert_summary", "run_kind": "warm"},
    {"case_id": "E-P5", "profile": "guided_investigation", "run_kind": "cold"},
    {"case_id": "E-P6", "profile": "spl_generation", "run_kind": "cold"},
)

APPROVED_LIVE_CASE_IDS: frozenset[str] = frozenset(row["case_id"] for row in DEFAULT_PROBE_MATRIX)

ALLOWLISTED_ERROR_CODES: frozenset[str] = frozenset(
    {
        "authorization_missing",
        "health_not_ready",
        "migrations_not_ready",
        "live_connector_selectable",
        "authentication_failed",
        "http_non_success",
        "request_timeout",
        "malformed_turn_timing",
        "execution_enabled",
        "response_invalid",
        "unexpected_client_error",
    }
)

_LIVE_MOCK_SERVER_TRANSPORTS = frozenset({"mock"})
_LIVE_REMEDIATION_PROVIDER_TYPES = frozenset({"ticketing", "remediation", "soar"})

# Fixed, reviewable probe definitions — messages are never accepted from CLI.
APPROVED_LIVE_PROBE_MESSAGES: dict[str, dict[str, Any]] = {
    "E-P1": {
        "profile": "knowledge_recall",
        "matrix_run_kind": "cold",
        "pair_id": "knowledge_pair",
        "pair_position": "first",
        "generation_only": False,
        "message": (
            "What is the standard operating procedure for investigating brute-force login attempts? "
            "Provide playbook guidance only; do not generate or execute SPL."
        ),
    },
    "E-P2": {
        "profile": "knowledge_recall",
        "matrix_run_kind": "warm",
        "pair_id": "knowledge_pair",
        "pair_position": "repeat",
        "generation_only": False,
        "message": (
            "Summarize the key investigation steps from the brute-force login SOP. "
            "Knowledge recall only; no SPL generation or execution."
        ),
    },
    "E-P3": {
        "profile": "alert_summary",
        "matrix_run_kind": "cold",
        "pair_id": "alert_pair",
        "pair_position": "first",
        "generation_only": False,
        "message": (
            "Summarize alert ALT-BF-001: multiple failed logins for svc_backup from 203.0.113.44 "
            "followed by a successful login. Include severity and MITRE context. Read-only analysis."
        ),
    },
    "E-P4": {
        "profile": "alert_summary",
        "matrix_run_kind": "warm",
        "pair_id": "alert_pair",
        "pair_position": "repeat",
        "generation_only": False,
        "message": (
            "Provide an analyst summary for alert ALT-BF-001 brute-force pattern. "
            "Read-only; do not execute searches."
        ),
    },
    "E-P5": {
        "profile": "guided_investigation",
        "matrix_run_kind": "cold-intent",
        "pair_id": "none",
        "pair_position": "standalone",
        "generation_only": False,
        "message": (
            "We observed periodic HTTPS beacons to an unknown domain from a finance workstation. "
            "Provide guided investigation hypotheses and evidence collection guidance only. "
            "No SPL execution or MCP searches."
        ),
    },
    "E-P6": {
        "profile": "spl_generation",
        "matrix_run_kind": "cold-intent",
        "pair_id": "none",
        "pair_position": "standalone",
        "generation_only": True,
        "message": (
            "Draft a candidate SPL to hunt failed Windows logon events (event code 4625) in the last 24 hours. "
            "Generation and review only; do not execute the search."
        ),
    },
}

_SENSITIVE_REPORT_KEYS = frozenset(
    {
        "message",
        "query",
        "prompt",
        "answer",
        "response",
        "content",
        "password",
        "token",
        "secret",
        "credential",
        "authorization",
        "cookie",
        "session_id",
    }
)


class LiveHarnessRejected(RuntimeError):
    """Fail-closed rejection before or during a live harness run."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class LiveHarnessConfig:
    base_url: str
    case_ids: tuple[str, ...]
    confirm_live: bool
    probe_timeout_s: int = DEFAULT_PROBE_TIMEOUT_S
    inter_probe_pause_s: float = DEFAULT_INTER_PROBE_PAUSE_S
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass(frozen=True)
class BenchmarkProbeSpec:
    case_id: str
    profile: str
    run_kind: RunKind


@dataclass
class BenchmarkRunResult:
    case_id: str
    profile: str
    run_kind: str
    turn_timing: dict[str, Any]
    elapsed_ms: int
    error: str | None = None
    matrix_run_kind: str | None = None
    sequence_position: str | None = None
    server_run_kind: str | None = None
    pair_id: str | None = None
    pair_position: str | None = None
    http_status: int | None = None
    execution_enabled: bool | None = None
    response_valid: bool | None = None
    aborted: bool = False


@dataclass
class BenchmarkReport:
    harness: str = "live_synthesis_baseline"
    schema_version: str = LIVE_HARNESS_SCHEMA_VERSION
    mode: str = "stub"
    evidence_class: str = "stub_deterministic_not_measured"
    probe_matrix_version: str = PROBE_MATRIX_VERSION
    started_at_unix: float = field(default_factory=time.time)
    completed_at_unix: float | None = None
    runs: list[BenchmarkRunResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    aborted: bool = False
    abort_reason: str | None = None

    def to_sanitized_dict(self) -> dict[str, Any]:
        completed = self.completed_at_unix or time.time()
        payload = {
            "harness": self.harness,
            "schema_version": self.schema_version,
            "mode": self.mode,
            "evidence_class": self.evidence_class,
            "probe_matrix_version": self.probe_matrix_version,
            "duration_seconds": round(completed - self.started_at_unix, 2),
            "run_count": len(self.runs),
            "error_count": sum(1 for row in self.runs if row.error),
            "aborted": self.aborted,
            "abort_reason": sanitize_report_error_code(self.abort_reason),
            "runs": [
                {
                    "case_id": row.case_id,
                    "profile": row.profile,
                    "run_kind": row.run_kind,
                    "matrix_run_kind": row.matrix_run_kind,
                    "sequence_position": row.sequence_position,
                    "server_run_kind": row.server_run_kind,
                    "pair_id": row.pair_id,
                    "pair_position": row.pair_position,
                    "http_status": row.http_status,
                    "execution_enabled": row.execution_enabled,
                    "response_valid": row.response_valid,
                    "aborted": row.aborted,
                    "elapsed_ms": row.elapsed_ms,
                    "error": sanitize_report_error_code(row.error),
                    "turn_timing": row.turn_timing,
                }
                for row in self.runs
            ],
            "summary": self.summary,
        }
        return sanitize_turn_timing_payload(_drop_sensitive_report_keys(payload))


class LiveBenchmarkHttpClient(Protocol):
    def fetch_health(self) -> tuple[int, dict[str, Any]]: ...

    def fetch_settings_status(self) -> tuple[int, dict[str, Any]]: ...

    def fetch_providers_status(self) -> tuple[int, dict[str, Any]]: ...

    def post_chat(self, *, case_id: str, session_id: str, timeout_s: int) -> tuple[int, dict[str, Any], int]: ...


def sanitize_report_error_code(raw: str | None) -> str | None:
    """Map internal failures to the bounded allowlisted error codes stored in JSON."""
    if raw is None:
        return None
    normalized = str(raw).strip()
    if not normalized:
        return None
    if normalized in ALLOWLISTED_ERROR_CODES:
        return normalized
    if normalized.startswith("http_"):
        return "http_non_success"
    mapped = _INTERNAL_ERROR_CODE_MAP.get(normalized)
    if mapped in ALLOWLISTED_ERROR_CODES:
        return mapped
    return "unexpected_client_error"


_INTERNAL_ERROR_CODE_MAP: dict[str, str] = {
    "confirm_live_required": "authorization_missing",
    "authorization_env_required": "authorization_missing",
    "auth_credentials_required": "authentication_failed",
    "auth_failed": "authentication_failed",
    "health_not_ready": "health_not_ready",
    "migrations_not_ready": "migrations_not_ready",
    "live_connector_selectable": "live_connector_selectable",
    "settings_unavailable": "health_not_ready",
    "malformed_turn_timing": "malformed_turn_timing",
    "execution_enabled_true": "execution_enabled",
    "missing_control_plane_trace": "response_invalid",
    "missing_turn_timing": "response_invalid",
    "invalid_json_response": "response_invalid",
    "http_transport_error": "unexpected_client_error",
    "TimeoutError": "request_timeout",
    "socket.timeout": "request_timeout",
}


def _drop_sensitive_report_keys(payload: dict[str, Any]) -> dict[str, Any]:
    def _walk(value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                if str(key).lower() in _SENSITIVE_REPORT_KEYS:
                    continue
                cleaned[key] = _walk(item)
            return cleaned
        if isinstance(value, list):
            return [_walk(item) for item in value]
        return value

    return _walk(payload)


def _normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def _api_base(base_url: str) -> str:
    normalized = _normalize_base_url(base_url)
    if normalized.endswith("/api"):
        return normalized
    return f"{normalized}/api"


def _json_request(
    opener: Any,
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout_s: float,
) -> tuple[int, dict[str, Any]]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
            status = getattr(response, "status", 200)
    except HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"_parse_error": True}
        return status, parsed if isinstance(parsed, dict) else {}
    except URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "timed out" in reason.lower():
            raise LiveHarnessRejected("request_timeout", "request timed out") from exc
        raise LiveHarnessRejected("http_transport_error", "http transport failed") from exc
    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise LiveHarnessRejected("invalid_json_response", "response was not valid JSON") from exc
    return status, parsed if isinstance(parsed, dict) else {}


def _auth_enabled() -> bool:
    raw = os.getenv("APP_AUTH_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no"}


def validate_live_authorization(*, confirm_live: bool) -> None:
    if not confirm_live:
        raise LiveHarnessRejected("confirm_live_required", "--confirm-live is required for live probes")
    if os.getenv(LIVE_AUTHORIZATION_ENV, "").strip() != "1":
        raise LiveHarnessRejected(
            "authorization_env_required",
            f"{LIVE_AUTHORIZATION_ENV}=1 is required for live probes",
        )


def validate_live_base_url(base_url: str | None) -> str:
    if not base_url or not base_url.strip():
        raise LiveHarnessRejected("base_url_required", "--base-url is required for live probes")
    return _normalize_base_url(base_url)


def validate_live_auth_credentials() -> None:
    if not _auth_enabled():
        return
    username = os.getenv("APP_AUTH_USER", "").strip()
    password = os.getenv("APP_AUTH_PASSWORD", "").strip()
    if not username or not password:
        raise LiveHarnessRejected(
            "auth_credentials_required",
            "APP_AUTH_USER and APP_AUTH_PASSWORD must be set when APP_AUTH_ENABLED=true",
        )


def validate_no_arbitrary_query_inputs(*, message: str | None = None, query: str | None = None) -> None:
    if message or query:
        raise LiveHarnessRejected(
            "arbitrary_query_unsupported",
            "Arbitrary query/message CLI input is not supported; use approved --cases only",
        )


def validate_live_case_ids(case_ids: list[str]) -> tuple[str, ...]:
    if not case_ids:
        raise LiveHarnessRejected("case_ids_required", "At least one approved --cases value is required")
    if len(case_ids) > MAX_LIVE_PROBES_PER_RUN:
        raise LiveHarnessRejected(
            "max_probe_count_exceeded",
            f"Maximum {MAX_LIVE_PROBES_PER_RUN} probes per invocation",
        )
    normalized = tuple(case_ids)
    unknown = [case_id for case_id in normalized if case_id not in APPROVED_LIVE_CASE_IDS]
    if unknown:
        raise LiveHarnessRejected("unapproved_case_id", f"Unapproved case id(s): {', '.join(unknown)}")
    return normalized


def validate_turn_timing_payload(raw_timing: dict[str, Any]) -> dict[str, Any]:
    if raw_timing.get("schema_version") != "1":
        raise LiveHarnessRejected("malformed_turn_timing", "turn_timing.schema_version must be '1'")
    segments = raw_timing.get("segments_ms")
    if not isinstance(segments, dict):
        raise LiveHarnessRejected("malformed_turn_timing", "turn_timing.segments_ms must be an object")
    for key in ("synthesis_path", "outcome"):
        if key not in raw_timing:
            raise LiveHarnessRejected("malformed_turn_timing", f"turn_timing.{key} is required")
    return sanitize_turn_timing_payload(raw_timing)


def assert_health_ready(health_body: dict[str, Any]) -> None:
    if health_body.get("status") != "ok":
        raise LiveHarnessRejected("health_not_ready", "/health status is not ok")
    readiness = health_body.get("readiness")
    if not isinstance(readiness, dict):
        raise LiveHarnessRejected("health_not_ready", "/health readiness block missing")
    migrations = readiness.get("database_migrations")
    if not isinstance(migrations, dict) or migrations.get("ready") is not True:
        raise LiveHarnessRejected("migrations_not_ready", "database migrations are not ready")


def assert_mock_connector_posture(settings_body: dict[str, Any], providers_body: dict[str, Any] | None = None) -> None:
    mcp = settings_body.get("mcp")
    if not isinstance(mcp, dict):
        raise LiveHarnessRejected("settings_unavailable", "settings mcp block missing")

    mode = str(mcp.get("mode") or "")
    if mode != "mock":
        raise LiveHarnessRejected("live_connector_selectable", "MCP registry mode must be mock")

    discovery_status = str(mcp.get("discovery_status") or "")
    status_detail = str(mcp.get("status_detail") or "")
    if discovery_status != "mock" or status_detail != "mock":
        raise LiveHarnessRejected("live_connector_selectable", "effective MCP connector is not mock-only")

    if mcp.get("base_url_configured") is True or mcp.get("token_configured") is True:
        raise LiveHarnessRejected("live_connector_selectable", "live Splunk endpoint credentials are configured")

    if mcp.get("splunk_mcp_enabled") is True and mcp.get("base_url_configured") is True:
        raise LiveHarnessRejected("live_connector_selectable", "live Splunk MCP is enabled with a configured URL")

    readiness = mcp.get("splunk_live_readiness")
    if isinstance(readiness, dict) and readiness.get("ready_for_live_splunk_mcp") is True:
        raise LiveHarnessRejected("live_connector_selectable", "live Splunk MCP readiness reports execution-ready")

    servers = mcp.get("servers")
    if not isinstance(servers, list) or not servers:
        raise LiveHarnessRejected("live_connector_selectable", "mock MCP server registry is empty")

    for server in servers:
        if not isinstance(server, dict):
            continue
        transport = str(server.get("transport") or "")
        if transport not in _LIVE_MOCK_SERVER_TRANSPORTS:
            raise LiveHarnessRejected("live_connector_selectable", "non-mock MCP server transport is registered")
        if server.get("url_configured") is True:
            raise LiveHarnessRejected("live_connector_selectable", "registry server exposes a configured live URL")
        server_type = str(server.get("type") or "")
        if server_type in {"splunk", "splunk_mcp"} and transport != "mock":
            raise LiveHarnessRejected("live_connector_selectable", "live Splunk server type is selectable")

    if providers_body is not None:
        _assert_no_live_or_remediation_providers(providers_body)


def _assert_no_live_or_remediation_providers(providers_body: dict[str, Any]) -> None:
    providers = providers_body.get("providers")
    if not isinstance(providers, list):
        return
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        provider_type = str(provider.get("provider_type") or "").strip().lower()
        provider_id = str(provider.get("provider_id") or "").strip().lower()
        enabled = provider.get("enabled") is True
        available = provider.get("available") is True
        auth_configured = provider.get("auth_configured") is True
        write_supported = provider.get("write_supported") is True
        if provider_type in _LIVE_REMEDIATION_PROVIDER_TYPES and enabled:
            raise LiveHarnessRejected("live_connector_selectable", "remediation connector is registered")
        if provider_type == "splunk_mcp" and enabled and available and auth_configured:
            raise LiveHarnessRejected("live_connector_selectable", "live Splunk provider is selectable")
        if write_supported and enabled and available and provider_id not in {"mock_asset_inventory"}:
            raise LiveHarnessRejected("live_connector_selectable", "write-capable remediation provider is registered")


def _workflow_execution_enabled(body: dict[str, Any]) -> bool:
    workflow = body.get("workflow_plan")
    if not isinstance(workflow, dict):
        return False
    return workflow.get("execution_enabled") is True


def _sequence_position_for_index(index: int) -> str:
    return "first" if index == 0 else "subsequent"


def _session_id_for_case(case_id: str, *, run_id: str) -> str:
    definition = APPROVED_LIVE_PROBE_MESSAGES[case_id]
    pair_id = str(definition.get("pair_id") or "none")
    if pair_id == "knowledge_pair":
        return f"live-synth-bench-{run_id}-knowledge"
    if pair_id == "alert_pair":
        return f"live-synth-bench-{run_id}-alert"
    return f"live-synth-bench-{run_id}-{case_id}"


def build_live_harness_config(
    *,
    base_url: str | None,
    case_ids: list[str],
    confirm_live: bool,
    probe_timeout_s: int = DEFAULT_PROBE_TIMEOUT_S,
    inter_probe_pause_s: float = DEFAULT_INTER_PROBE_PAUSE_S,
    message: str | None = None,
    query: str | None = None,
) -> LiveHarnessConfig:
    validate_no_arbitrary_query_inputs(message=message, query=query)
    validate_live_authorization(confirm_live=confirm_live)
    validate_live_auth_credentials()
    normalized_cases = validate_live_case_ids(case_ids)
    normalized_url = validate_live_base_url(base_url)
    if probe_timeout_s <= 0:
        raise LiveHarnessRejected("invalid_probe_timeout", "probe timeout must be positive")
    return LiveHarnessConfig(
        base_url=normalized_url,
        case_ids=normalized_cases,
        confirm_live=confirm_live,
        probe_timeout_s=probe_timeout_s,
        inter_probe_pause_s=inter_probe_pause_s,
    )


def parse_probe_matrix(rows: list[dict[str, str]] | None = None) -> list[BenchmarkProbeSpec]:
    source = rows if rows is not None else list(DEFAULT_PROBE_MATRIX)
    specs: list[BenchmarkProbeSpec] = []
    for row in source:
        run_kind_raw = str(row.get("run_kind") or RunKind.UNKNOWN.value)
        try:
            run_kind = RunKind(run_kind_raw)
        except ValueError:
            run_kind = RunKind.UNKNOWN
        specs.append(
            BenchmarkProbeSpec(
                case_id=str(row["case_id"]),
                profile=str(row["profile"]),
                run_kind=run_kind,
            )
        )
    return specs


def _percentiles(values: list[int]) -> dict[str, int | None]:
    return percentile_summary(values)


def summarize_benchmark(report: BenchmarkReport) -> dict[str, Any]:
    ok_runs = [row for row in report.runs if row.error is None]
    e2e = [int(row.turn_timing.get("segments_ms", {}).get("end_to_end") or row.elapsed_ms) for row in ok_runs]
    endpoint = [
        int(row.turn_timing.get("segments_ms", {}).get("synthesis_endpoint") or 0)
        for row in ok_runs
        if row.turn_timing.get("segments_ms", {}).get("synthesis_endpoint") is not None
    ]

    def _matrix_kind_value(row: BenchmarkRunResult) -> str:
        return str(row.matrix_run_kind or row.run_kind or RunKind.UNKNOWN.value)

    cold_e2e = [
        int(row.turn_timing.get("segments_ms", {}).get("end_to_end") or row.elapsed_ms)
        for row in ok_runs
        if _matrix_kind_value(row) in {RunKind.COLD.value, "cold-intent"}
    ]
    warm_e2e = [
        int(row.turn_timing.get("segments_ms", {}).get("end_to_end") or row.elapsed_ms)
        for row in ok_runs
        if _matrix_kind_value(row) == RunKind.WARM.value
    ]
    timeout_count = sum(1 for row in ok_runs if row.turn_timing.get("outcome") == TurnOutcome.TIMEOUT.value)
    # Request-level governed timeout (final outcome), not per-hop endpoint_attempt_timeout.
    fallback_count = sum(1 for row in ok_runs if row.turn_timing.get("fallback_used") is True)
    path_counts: dict[str, int] = {}
    for row in ok_runs:
        path = str(row.turn_timing.get("synthesis_path") or SynthesisPath.SKIPPED.value)
        path_counts[path] = path_counts.get(path, 0) + 1
    summary = {
        "sample_count": len(ok_runs),
        "end_to_end_ms": _percentiles(e2e),
        "synthesis_endpoint_ms": _percentiles(endpoint),
        "cold_end_to_end_ms": _percentiles(cold_e2e),
        "warm_end_to_end_ms": _percentiles(warm_e2e),
        "timeout_rate": round(timeout_count / len(ok_runs), 4) if ok_runs else None,
        "fallback_rate": round(fallback_count / len(ok_runs), 4) if ok_runs else None,
        "synthesis_path_counts": path_counts,
    }
    if report.mode == "live":
        summary["percentile_warning"] = LIVE_PERCENTILE_WARNING
        summary["slo_baseline"] = False
    return summary


def _stub_turn_timing(spec: BenchmarkProbeSpec) -> dict[str, Any]:
    base = 42000 if spec.run_kind is RunKind.COLD else 18000
    planning = 8000 if spec.profile != "knowledge_recall" else 5000
    retrieval = 12000 if spec.profile in {"spl_generation", "alert_summary"} else 6000
    endpoint = base - planning - retrieval - 2000
    path = SynthesisPath.COMPOSER if spec.profile == "guided_investigation" else SynthesisPath.LAB
    if spec.profile == "spl_generation":
        path = SynthesisPath.SKIPPED
        endpoint = 0
    return sanitize_turn_timing_payload(
        {
            "schema_version": "1",
            "run_kind": spec.run_kind.value,
            "synthesis_path": path.value,
            "outcome": TurnOutcome.COMPLETED.value if endpoint else TurnOutcome.SKIPPED.value,
            "timeout_applied": False,
            "fallback_used": False,
            "segments_ms": {
                "canonical_planning": planning,
                "retrieval_spl": retrieval,
                "synthesis_endpoint": endpoint or None,
                "application_overhead": 2000,
                "end_to_end": base,
            },
            "endpoint_detail": {
                "provider_label": "stub",
                "model": "stub-deterministic",
                "http_round_trip_ms": endpoint or None,
            },
        }
    )


def run_stub_benchmark(
    specs: list[BenchmarkProbeSpec] | None = None,
    *,
    sleep_ms: int = 0,
) -> BenchmarkReport:
    report = BenchmarkReport(mode="stub")
    for spec in specs or parse_probe_matrix():
        started = time.monotonic()
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)
        timing = _stub_turn_timing(spec)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        report.runs.append(
            BenchmarkRunResult(
                case_id=spec.case_id,
                profile=spec.profile,
                run_kind=spec.run_kind.value,
                turn_timing=timing,
                elapsed_ms=elapsed_ms,
            )
        )
    report.completed_at_unix = time.time()
    report.summary = summarize_benchmark(report)
    return report


class UrllibLiveBenchmarkHttpClient:
    """Sequential HTTP client for approved live probes (no concurrency, no retries)."""

    def __init__(self, *, base_url: str) -> None:
        self._api_base = _api_base(base_url)
        self._jar = CookieJar()
        self._opener = build_opener(HTTPCookieProcessor(self._jar))
        self._login()

    def _login(self) -> None:
        if not _auth_enabled():
            return
        username = os.getenv("APP_AUTH_USER", "analyst").strip() or "analyst"
        password = os.getenv("APP_AUTH_PASSWORD", "").strip()
        status, body = _json_request(
            self._opener,
            method="POST",
            url=f"{self._api_base}/auth/login",
            payload={"username": username, "password": password},
            timeout_s=30.0,
        )
        if status != 200 or not body.get("authenticated"):
            raise LiveHarnessRejected("auth_failed", "auth login failed")

    def fetch_health(self) -> tuple[int, dict[str, Any]]:
        return _json_request(
            self._opener,
            method="GET",
            url=f"{self._api_base}/health",
            timeout_s=30.0,
        )

    def fetch_settings_status(self) -> tuple[int, dict[str, Any]]:
        return _json_request(
            self._opener,
            method="GET",
            url=f"{self._api_base}/settings/status",
            timeout_s=30.0,
        )

    def fetch_providers_status(self) -> tuple[int, dict[str, Any]]:
        return _json_request(
            self._opener,
            method="GET",
            url=f"{self._api_base}/settings/providers/status",
            timeout_s=30.0,
        )

    def post_chat(self, *, case_id: str, session_id: str, timeout_s: int) -> tuple[int, dict[str, Any], int]:
        definition = APPROVED_LIVE_PROBE_MESSAGES[case_id]
        started = time.perf_counter()
        status, body = _json_request(
            self._opener,
            method="POST",
            url=f"{self._api_base}/chat",
            payload={"message": definition["message"], "session_id": session_id},
            timeout_s=float(timeout_s),
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return status, body, elapsed_ms


def run_live_preflight(client: LiveBenchmarkHttpClient) -> None:
    health_status, health_body = client.fetch_health()
    if health_status != 200:
        raise LiveHarnessRejected("health_not_ready", "/health returned non-success status")
    assert_health_ready(health_body)
    settings_status, settings_body = client.fetch_settings_status()
    if settings_status != 200:
        raise LiveHarnessRejected("settings_unavailable", "/settings/status returned non-success status")
    providers_status, providers_body = client.fetch_providers_status()
    if providers_status != 200:
        raise LiveHarnessRejected("settings_unavailable", "/settings/providers/status returned non-success status")
    assert_mock_connector_posture(settings_body, providers_body)


def _record_probe_result(
    *,
    case_id: str,
    definition: dict[str, Any],
    sequence_position: str,
    http_status: int,
    elapsed_ms: int,
    error: str | None,
    response_valid: bool,
    turn_timing: dict[str, Any],
    execution_enabled: bool,
    aborted: bool,
) -> BenchmarkRunResult:
    server_run_kind = str(turn_timing.get("run_kind") or RunKind.UNKNOWN.value)
    return BenchmarkRunResult(
        case_id=case_id,
        profile=str(definition["profile"]),
        run_kind=str(definition["matrix_run_kind"]),
        matrix_run_kind=str(definition["matrix_run_kind"]),
        sequence_position=sequence_position,
        server_run_kind=server_run_kind,
        pair_id=str(definition["pair_id"]),
        pair_position=str(definition["pair_position"]),
        http_status=http_status,
        execution_enabled=execution_enabled,
        response_valid=response_valid,
        turn_timing=turn_timing,
        elapsed_ms=elapsed_ms,
        error=sanitize_report_error_code(error),
        aborted=aborted,
    )


def run_live_benchmark(
    config: LiveHarnessConfig,
    *,
    client: LiveBenchmarkHttpClient | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> BenchmarkReport:
    """Execute approved live probes sequentially via injected or urllib HTTP client."""
    http_client = client or UrllibLiveBenchmarkHttpClient(base_url=config.base_url)
    report = BenchmarkReport(
        mode="live",
        evidence_class=LIVE_EVIDENCE_CLASS,
    )
    try:
        run_live_preflight(http_client)
    except LiveHarnessRejected as exc:
        report.aborted = True
        report.abort_reason = sanitize_report_error_code(exc.code)
        report.completed_at_unix = time.time()
        report.summary = summarize_benchmark(report)
        return report

    for index, case_id in enumerate(config.case_ids):
        definition = APPROVED_LIVE_PROBE_MESSAGES[case_id]
        sequence_position = _sequence_position_for_index(index)
        session_id = _session_id_for_case(case_id, run_id=config.run_id)
        error: str | None = None
        turn_timing: dict[str, Any] = {}
        http_status = 0
        elapsed_ms = 0
        response_valid = False
        execution_enabled = False
        body: dict[str, Any] = {}
        aborted = False

        try:
            http_status, body, elapsed_ms = http_client.post_chat(
                case_id=case_id,
                session_id=session_id,
                timeout_s=config.probe_timeout_s,
            )
            if http_status != 200:
                error = "http_non_success"
                aborted = True
            else:
                execution_enabled = _workflow_execution_enabled(body)
                if execution_enabled:
                    error = "execution_enabled"
                    aborted = True
                trace = body.get("control_plane_trace")
                if not isinstance(trace, dict):
                    error = error or "response_invalid"
                    aborted = True
                else:
                    raw_timing = trace.get("turn_timing")
                    if not isinstance(raw_timing, dict):
                        error = error or "response_invalid"
                        aborted = True
                    else:
                        turn_timing = validate_turn_timing_payload(raw_timing)
                        response_valid = True
                        if turn_timing.get("outcome") == TurnOutcome.TIMEOUT.value:
                            error = "request_timeout"
                            aborted = True
        except LiveHarnessRejected as exc:
            error = sanitize_report_error_code(exc.code)
            aborted = True
        except Exception as exc:  # noqa: BLE001 — benchmark captures operator failures once
            error = sanitize_report_error_code(type(exc).__name__)
            aborted = True

        report.runs.append(
            _record_probe_result(
                case_id=case_id,
                definition=definition,
                sequence_position=sequence_position,
                http_status=http_status,
                elapsed_ms=elapsed_ms,
                error=error,
                response_valid=response_valid,
                turn_timing=turn_timing,
                execution_enabled=execution_enabled,
                aborted=aborted,
            )
        )

        if aborted:
            report.aborted = True
            report.abort_reason = error
            break

        if index < len(config.case_ids) - 1 and config.inter_probe_pause_s > 0:
            sleep_fn(config.inter_probe_pause_s)

    report.completed_at_unix = time.time()
    report.summary = summarize_benchmark(report)
    return report


def estimate_live_probe_cost(specs: list[BenchmarkProbeSpec] | None = None) -> dict[str, Any]:
    """Rough operator cost model — not an SLO."""
    matrix = specs or parse_probe_matrix()
    cold = sum(1 for row in matrix if row.run_kind is RunKind.COLD)
    warm = sum(1 for row in matrix if row.run_kind is RunKind.WARM)
    # Observed VPS smoke band (gap reconciliation): 90–240 s/turn with live synthesis.
    est_cold_s = cold * 150
    est_warm_s = warm * 45
    inter_pause_s = max(0, len(matrix) - 1) * DEFAULT_INTER_PROBE_PAUSE_S
    return {
        "probe_count": len(matrix),
        "cold_probes": cold,
        "warm_probes": warm,
        "inter_probe_pause_seconds": inter_pause_s,
        "estimated_runtime_seconds": est_cold_s + est_warm_s + int(inter_pause_s),
        "estimated_runtime_minutes": round((est_cold_s + est_warm_s + inter_pause_s) / 60, 1),
        "heuristic_duration_minutes": "10-15",
        "maximum_timeout_bound_minutes": round((MAX_LIVE_PROBES_PER_RUN * DEFAULT_PROBE_TIMEOUT_S + inter_pause_s) / 60, 1),
        "note": (
            "Heuristic exploratory duration is approximately 10–15 minutes; "
            "timeout-bound ceiling is approximately 30 minutes plus preflight. "
            "Not an SLO baseline; no retries; first timeout/non-200/safety violation aborts remaining probes."
        ),
    }
