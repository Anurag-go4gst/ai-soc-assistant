#!/usr/bin/env python3
"""P8 L3 — live local/office LLM semantic measurement runner.

L3-1 (this script, default --dry-run): freeze bank hash, load pre-declared
thresholds, probe endpoints, refuse to invent scores.

L3-2 (--live): call real production seams against CURRENT_ACTIVE_PROMPT only.
There is no CANDIDATE_PROMPT. Deterministic fallback is recorded as fallback,
never as semantic success. Blocked reasoning roles are never invoked.

    PYTHONPATH=backend:. python3 scripts/eval_p8_l3_live.py --dry-run
    PYTHONPATH=backend:. AI_SOC_TESTS_ALLOW_LIVE_LLM=1 python3 scripts/eval_p8_l3_live.py --live
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "docs/evals/p8_l3/bank_v1.json"
THRESHOLDS_PATH = ROOT / "docs/evals/p8_l3/thresholds_v1.json"
REPORT_DIR = ROOT / "docs/evals/p8_l3"
PRODUCT_SHA = "b6e4befe9a79dd722a09a09fdd345bae82880884"
BLOCKED_ROLES = (
    "mitre_reasoner",
    "missing_evidence_reasoner",
    "risk_rationale_reasoner",
    "plan_delta_reasoner",
    "pattern_reasoner",
    "evidence_reasoner",
    "hypothesis_reasoner",
)
REQUIRED_CATEGORIES = frozenset(
    {
        "t4_semantic",
        "spl_rolling",
        "spl_trend",
        "spl_sequence",
        "spl_ranking",
        "spl_raw_events",
        "l2_production",
        "followup_correction",
        "evidence_truth_negative",
        "investigation_planner",
        "failure_abstain",
        "prompt_role",
    }
)
PROBE_CANDIDATES = (
    ("local_llama_8081", "http://127.0.0.1:8081/v1", "foundation-sec-1.1-8b-instruct-q8_0.gguf"),
    ("coe_instruct_8004", "http://10.52.1.13:8004/v1", "foundation-sec-instruct"),
)


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def bank_hash(bank: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(bank)).hexdigest()


def load_bank() -> dict[str, Any]:
    return json.loads(BANK_PATH.read_text(encoding="utf-8"))


def load_thresholds() -> dict[str, Any]:
    return json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))


def validate_bank(bank: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if bank.get("candidate_prompt") is not None:
        errors.append("candidate_prompt must be null until a real candidate exists")
    if bank.get("live_ab_eval_performed") is not False:
        errors.append("live_ab_eval_performed must stay false until a two-arm live run")
    if bank.get("product_sha") != PRODUCT_SHA:
        errors.append(f"bank product_sha must be {PRODUCT_SHA}")
    rows = bank.get("rows") or []
    if not rows:
        errors.append("bank has no rows")
    cats = {str(row.get("category") or "") for row in rows}
    missing = sorted(REQUIRED_CATEGORIES - cats)
    if missing:
        errors.append(f"missing categories: {missing}")
    ids = [str(row.get("row_id") or "") for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate row_id")
    for role in bank.get("blocked_roles_must_not_be_invoked") or []:
        if role not in BLOCKED_ROLES:
            errors.append(f"unknown blocked role in bank: {role}")
    live_roles = {str(row.get("role_id")) for row in rows if row.get("role_id")}
    invoked_blocked = sorted(live_roles & set(BLOCKED_ROLES))
    if invoked_blocked:
        errors.append(f"bank must not live-invoke blocked roles: {invoked_blocked}")
    return errors


def validate_thresholds(thresholds: dict[str, Any]) -> list[str]:
    from app.llm.policy.evaluation import REQUIRED_FROZEN_METRICS, freeze_thresholds

    errors: list[str] = []
    floors = thresholds.get("measurement_floors") or {}
    missing = sorted(set(REQUIRED_FROZEN_METRICS) - set(floors))
    if missing:
        errors.append(f"thresholds missing required metrics: {missing}")
    if not thresholds.get("frozen_before_live"):
        errors.append("thresholds must be marked frozen_before_live")
    if thresholds.get("product_sha") != PRODUCT_SHA:
        errors.append(f"thresholds product_sha must be {PRODUCT_SHA}")
    try:
        for role_id in thresholds.get("roles") or []:
            freeze_thresholds(str(role_id), {k: float(v) for k, v in floors.items()})
    except Exception as exc:  # noqa: BLE001 — surface contract errors to the dry-run
        errors.append(f"freeze_thresholds rejected floors: {exc}")
    return errors


def _tcp_open(url: str, timeout: float = 3.0) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_endpoint(label: str, base_url: str, model: str, timeout: float = 8.0) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": label,
        "base_url": base_url,
        "model": model,
        "tcp_open": _tcp_open(base_url, timeout=3.0),
        "http_status": None,
        "healthy": False,
        "error": None,
    }
    if not result["tcp_open"]:
        result["error"] = "tcp_closed"
        return result
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 4,
            "temperature": 0,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["http_status"] = int(resp.status)
            result["healthy"] = 200 <= int(resp.status) < 300
            result["latency_ms"] = int((time.monotonic() - started) * 1000)
    except urllib.error.HTTPError as exc:
        result["http_status"] = int(exc.code)
        result["error"] = f"http_{exc.code}"
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
    except Exception as exc:  # noqa: BLE001
        result["error"] = type(exc).__name__
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
    return result


def probe_all() -> list[dict[str, Any]]:
    return [probe_endpoint(*item) for item in PROBE_CANDIDATES]


def provenance_rows() -> dict[str, Any]:
    from app.llm.policy.candidates import candidate_for, candidate_stable_prefix_hash
    from app.llm.policy.evaluation import contract_for_role
    from app.llm.policy.role_inventory import blocked_role_ids

    roles = ("semantic_t4", "spl_advisory_generator", "investigation_planner", "shape_advisor")
    arms = {}
    registered: dict[str, Any] = {}
    for role_id in roles:
        contract = contract_for_role(role_id)
        arms[role_id] = {
            "template_id": contract.active.template_id,
            "version": contract.active.version,
            "stable_prefix_hash": contract.active.stable_prefix_hash,
            "candidate": None,
            "eval_status": contract.eval_status,
        }
        cand = candidate_for(role_id)
        if cand is not None:
            registered[role_id] = {
                "template_id": cand.template_id,
                "version": cand.version,
                "status": cand.status,
                "stable_prefix_hash": candidate_stable_prefix_hash(role_id),
            }
    return {
        "active_prompt_arms": arms,
        "registered_candidates": registered,
        "blocked_role_ids": list(blocked_role_ids()),
        "reasoning_allowlist_expected": ["investigation_planner"],
    }


def write_report(name: str, payload: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def dry_run(*, persist: bool = False) -> tuple[int, dict[str, Any]]:
    for path in (ROOT / "backend", ROOT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    bank = load_bank()
    thresholds = load_thresholds()
    errors = validate_bank(bank) + validate_thresholds(thresholds)
    digest = bank_hash(bank)
    probes = probe_all()
    healthy = [p for p in probes if p.get("healthy")]
    report: dict[str, Any] = {
        "phase": "L3-1",
        "mode": "dry_run",
        "product_sha": PRODUCT_SHA,
        "bank_id": bank.get("bank_id"),
        "bank_hash": digest,
        "row_count": len(bank.get("rows") or []),
        "categories": sorted({row["category"] for row in bank["rows"]}),
        "candidate_prompt": None,
        "live_ab_eval_performed": False,
        "blocked_roles_enabled": False,
        "endpoint_probes": probes,
        "healthy_endpoint": healthy[0] if healthy else None,
        "prompt_provenance": provenance_rows(),
        "errors": errors,
        "eval_status": "BLOCKED_INFRASTRUCTURE" if not healthy else "DRY_RUN_READY",
        "live_llm_used": False,
        "live_mcp_used": False,
    }
    report_path = str(write_report("l3_1_dry_run.json", report)) if persist else None
    print(
        json.dumps(
            {
                "ok": not errors,
                "bank_hash": digest,
                "report": report_path,
                "eval_status": report["eval_status"],
                "errors": errors,
            },
            indent=2,
        )
    )
    return (1 if errors else 0), report


def apply_compose_like_env() -> dict[str, str]:
    """Load COE profile then non-secret .env overlays the same way Compose does.

    Does not rewrite repo files. Forces MCP execution off. Leaves the host
    ``AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS`` overlay in place.
    """
    applied: dict[str, str] = {}

    def _parse(path: Path) -> list[tuple[str, str]]:
        if not path.is_file():
            return []
        rows: list[tuple[str, str]] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            value = value.strip().strip('"').strip("'")
            rows.append((key, value))
        return rows

    for key, value in _parse(ROOT / "env/profiles/coe.env.example"):
        os.environ[key] = value
        applied[key] = value
    for key, value in _parse(ROOT / ".env"):
        os.environ[key] = value
        applied[key] = value
    os.environ["MCP_GLOBAL_EXECUTION_ENABLED"] = "false"
    os.environ["MCP_SERVER_MOCK_EXECUTION_ENABLED"] = "false"
    # Eval process is not the Docker network: do not hang on hostname `postgres`
    # or write live telemetry. This does not change product files or Compose.
    os.environ["AI_SOC_TELEMETRY_SINK"] = "none"
    os.environ["TELEMETRY_MODE"] = "none"
    db_url = os.environ.get("DATABASE_URL", "")
    host_port = os.environ.get("AI_SOC_POSTGRES_HOST_PORT", "5434")
    if "@postgres:5432" in db_url:
        os.environ["DATABASE_URL"] = db_url.replace("@postgres:5432", f"@127.0.0.1:{host_port}")
    os.environ["AI_SOC_TESTS_ALLOW_LIVE_LLM"] = "1"
    applied["MCP_GLOBAL_EXECUTION_ENABLED"] = "false"
    applied["MCP_SERVER_MOCK_EXECUTION_ENABLED"] = "false"
    applied["TELEMETRY_MODE"] = "none"
    return applied


def capture_model_identity() -> dict[str, Any]:
    from app.config import settings
    from app.llm.clients.endpoint_resolver import resolve_local_primary_endpoint

    endpoint = resolve_local_primary_endpoint(sidecar=True)
    identity: dict[str, Any] = {
        "provider": settings.ai_soc_llm_default_provider or settings.ai_soc_llm_mode,
        "model": (endpoint.model if endpoint else settings.ai_soc_llm_local_model),
        "endpoint": (endpoint.base_url if endpoint else settings.ai_soc_llm_local_base_url),
        "timeout_seconds": int(settings.ai_soc_llm_timeout_seconds or 0),
        "t4_timeout_seconds": float(settings.ai_soc_t4_semantic_understanding_timeout_seconds or 0),
        "temperature": float(settings.ai_soc_llm_temperature or 0),
        "retry_policy": "one_infra_retry_transport_only",
        "llm_mode": settings.ai_soc_llm_mode,
        "llm_enabled": bool(settings.ai_soc_llm_enabled),
        "mcp_global_execution_enabled": bool(
            getattr(settings, "mcp_global_execution_enabled", False)
        ),
        "model_version_or_build": None,
    }
    if endpoint and _tcp_open(endpoint.base_url):
        try:
            req = urllib.request.Request(f"{endpoint.base_url.rstrip('/')}/models")
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode())
            models = payload.get("data") or []
            if models:
                identity["provider"] = models[0].get("owned_by") or identity["provider"]
                identity["model_version_or_build"] = {
                    "id": models[0].get("id"),
                    "owned_by": models[0].get("owned_by"),
                    "root": models[0].get("root"),
                    "max_model_len": models[0].get("max_model_len"),
                }
        except Exception as exc:  # noqa: BLE001
            identity["model_identity_error"] = type(exc).__name__
    return identity


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def aggregate_live_results(
    *,
    rows: list[dict[str, Any]],
    bank_digest: str,
    identity: dict[str, Any],
    thresholds: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    scored = [row for row in rows if row.get("final_result") not in {"OBSERVED_NOT_SCORED", "NOT_RUN"}]
    quality_pass = [row for row in scored if row.get("final_result") == "PASS" and row.get("llm_used")]
    product_pass = [row for row in scored if row.get("final_result") in {"PASS", "PRODUCT_SUCCESS_MODEL_FAILURE"}]
    failed = [row for row in scored if row.get("final_result") == "FAIL"]
    llm_called = [row for row in rows if row.get("llm_called")]
    llm_used = [row for row in rows if row.get("llm_used")]
    rejected = [row for row in llm_called if not row.get("llm_accepted")]
    fallback = [row for row in rows if row.get("fallback_used")]
    timeouts = [row for row in rows if row.get("failure_class") == "MODEL_TIMEOUT"]
    structured = [row for row in rows if row.get("structured_output_valid") is True]
    structured_n = [row for row in rows if row.get("structured_output_valid") is not None]
    model_semantic = []
    for row in scored:
        if row.get("llm_used"):
            model_semantic.append(float(row.get("semantic_correctness") or 0.0))
        elif row.get("llm_called"):
            model_semantic.append(0.0)
    latencies = [int(row["latency_ms"]) for row in rows if row.get("latency_ms")]
    authority = [row["case_id"] for row in rows if row.get("authority_violations")]
    hallucinations = [row["case_id"] for row in rows if row.get("evidence_hallucinations")]
    spl_rows = [row for row in rows if row.get("seam") == "spl_plan"]
    invented = [
        row
        for row in spl_rows
        if any(item in (row.get("spl_losses") or []) for item in ("unexpected_threshold", "arbitrary_head_100"))
    ]
    n_called = max(len(llm_called), 1)

    def rate(num: int, den: int) -> float:
        return round(num / den, 4) if den else 0.0

    floors = {k: float(v) for k, v in (thresholds.get("measurement_floors") or {}).items()}
    actuals = {
        "semantic_correctness": round(sum(model_semantic) / len(model_semantic), 4) if model_semantic else 0.0,
        "schema_validity": rate(len(structured), len(structured_n) or 1),
        "initial_pass_rate": rate(len(quality_pass), len(scored) or 1),
        "repair_rate": 0.0,
        "fallback_rate": rate(len(fallback), len(rows) or 1),
        "invented_constraint_rate": rate(len(invented), max(len(spl_rows), 1)),
        "semantic_loss_rate": rate(
            len([row for row in spl_rows if row.get("spl_losses")]),
            max(len(spl_rows), 1),
        ),
        "latency_p50_ms": float(_percentile(latencies, 50) or 0),
        "latency_p95_ms": float(_percentile(latencies, 95) or 0),
        "input_tokens": 0.0,
        "output_tokens": 0.0,
        "cache_eligibility": 0.0,
        "provider_cache_hit_rate": 0.0,
    }
    polarity = thresholds.get("polarity") or {}
    threshold_results = []
    threshold_review: list[str] = []
    for metric, floor in floors.items():
        actual = actuals.get(metric, 0.0)
        kind = polarity.get(metric, "record_only")
        if kind == "higher_better":
            passed_floor = actual >= floor
            if not passed_floor:
                threshold_review.append(metric)
        else:
            passed_floor = True
        threshold_results.append(
            {
                "metric": metric,
                "threshold": floor,
                "actual": actual,
                "pass": passed_floor,
                "polarity": kind,
            }
        )
    higher_failed = [item for item in threshold_results if item["polarity"] == "higher_better" and not item["pass"]]
    if authority or hallucinations or higher_failed:
        decision = "BASELINE_FAIL_REQUIRES_CANDIDATE"
    else:
        decision = "BASELINE_PASS"

    by_cat: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cat.setdefault(str(row.get("category")), []).append(
            {
                "case_id": row["case_id"],
                "final_result": row.get("final_result"),
                "failure_class": row.get("failure_class"),
                "llm_used": row.get("llm_used"),
                "fallback_used": row.get("fallback_used"),
            }
        )

    return {
        "phase": "L3-2",
        "mode": "live",
        "product_sha": PRODUCT_SHA,
        "bank_hash": bank_digest,
        "bank_row_count": len(rows),
        "live_ab_eval_performed": False,
        "candidate_prompt_created": False,
        "blocked_roles_enabled": False,
        "live_mcp_used": False,
        "thresholds_frozen": True,
        "identity": identity,
        "prompt_provenance": provenance,
        "rows_executed": len(rows),
        "rows_passed": len(quality_pass),
        "rows_product_pass": len(product_pass),
        "rows_failed": len(failed),
        "rows_product_success_model_failure": len(
            [row for row in rows if row.get("final_result") == "PRODUCT_SUCCESS_MODEL_FAILURE"]
        ),
        "llm_success_rate": rate(len(llm_used), n_called),
        "llm_reject_rate": rate(len(rejected), n_called),
        "llm_fallback_rate": rate(len(fallback), len(rows) or 1),
        "llm_timeout_rate": rate(len(timeouts), len(rows) or 1),
        "structured_output_valid_rate": actuals["schema_validity"],
        "semantic_success_rate": actuals["semantic_correctness"],
        "authority_violations": authority,
        "evidence_hallucinations": hallucinations,
        "latency_p50": _percentile(latencies, 50),
        "latency_p95": _percentile(latencies, 95),
        "latency_max": max(latencies) if latencies else None,
        "threshold_results": threshold_results,
        "threshold_review_candidate": threshold_review,
        "failed_case_ids": [row["case_id"] for row in failed],
        "failure_classification_by_case": {
            row["case_id"]: row.get("failure_class") for row in rows if row.get("failure_class")
        },
        "fallback_rescued_cases": [
            row["case_id"] for row in rows if row.get("final_result") == "PRODUCT_SUCCESS_MODEL_FAILURE"
        ],
        "category_results": by_cat,
        "baseline_decision": decision,
        "eval_status": "LIVE_BASELINE_COMPLETE",
        "role_metrics": _role_metrics(rows),
    }


def _role_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    t4 = [row for row in rows if row.get("seam") == "t4"]
    spl = [row for row in rows if row.get("seam") == "spl_plan" and row.get("case_id") != "L3.AB.01"]
    planner = [row for row in rows if row.get("seam") == "planner"]

    def rate(num: int, den: int) -> float:
        return round(num / den, 4) if den else 0.0

    return {
        "t4_attempted": sum(1 for row in t4 if row.get("t4_attempted")),
        "t4_accepted": sum(1 for row in t4 if row.get("t4_accepted")),
        "t4_accept_rate": rate(sum(1 for row in t4 if row.get("t4_accepted")), max(len(t4), 1)),
        "spl_pass": sum(1 for row in spl if row.get("final_result") == "PASS"),
        "spl_n": len(spl),
        "spl_success_rate": rate(sum(1 for row in spl if row.get("final_result") == "PASS"), max(len(spl), 1)),
        "planner_schema_success": sum(1 for row in planner if row.get("llm_accepted")),
        "planner_n": len(planner),
        "planner_schema_success_rate": rate(
            sum(1 for row in planner if row.get("llm_accepted")),
            max(len(planner), 1),
        ),
    }


def live_run(
    *,
    persist: bool = False,
    arm: str = "active",
    report_prefix: str | None = None,
    intended_model: str = "foundation-sec-instruct",
    local_base_url: str | None = None,
    local_model: str | None = None,
) -> int:
    os.environ["AI_SOC_TESTS_ALLOW_LIVE_LLM"] = "1"
    applied_keys = sorted(apply_compose_like_env())
    if local_base_url:
        os.environ["AI_SOC_LLM_LOCAL_BASE_URL"] = local_base_url
        # Fair comparison: do not prepend/failover the 8B specialists.
        os.environ["AI_SOC_LLM_FOUNDATION_SEC_REASONING_BASE_URL"] = ""
        os.environ["AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_BASE_URL"] = ""
        os.environ["AI_SOC_LLM_QWEN_PRIMARY_ENABLED"] = "false"
    if local_model:
        os.environ["AI_SOC_LLM_LOCAL_MODEL"] = local_model
        os.environ["AI_SOC_LLM_DEFAULT_MODEL"] = local_model
        os.environ["AI_SOC_LLM_ACTIVE_MODEL"] = local_model
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    rc, dry = dry_run(persist=False)
    if rc != 0:
        return rc
    prefix = report_prefix or ("ab_active" if arm == "active" else f"ab_{arm}")
    is_l32 = prefix == "l3_2"
    if not dry.get("healthy_endpoint"):
        blocked = {
            "phase": "L3-2" if is_l32 else "P8-B",
            "mode": "live",
            "prompt_arm": arm,
            "product_sha": PRODUCT_SHA,
            "eval_status": "BLOCKED_INFRASTRUCTURE",
            "live_ab_eval_performed": not is_l32,
            "reason": (
                "No reachable local/office LLM. :8081 is closed and "
                "10.52.1.13:8004 did not accept a TCP/HTTP probe. "
                "Scores are not invented."
            ),
            "endpoint_probes": dry.get("endpoint_probes"),
            "bank_hash": dry.get("bank_hash"),
            "live_llm_used": False,
            "live_mcp_used": False,
            "blocked_roles_enabled": False,
        }
        path = write_report(f"{prefix}_live_blocked.json", blocked) if persist and not is_l32 else None
        print(
            json.dumps(
                {"ok": False, "eval_status": "BLOCKED_INFRASTRUCTURE", "report": str(path) if path else None},
                indent=2,
            )
        )
        return 2

    identity = capture_model_identity()
    intended = intended_model
    actual_model = str(identity.get("model") or "")
    build = identity.get("model_version_or_build") or {}
    actual_id = str(build.get("id") or actual_model)
    if intended and intended not in actual_model and intended not in actual_id:
        mismatch = {
            "phase": "L3-2" if is_l32 else "P8-B",
            "eval_status": "MODEL_IDENTITY_MISMATCH",
            "intended": intended,
            "actual": identity,
        }
        if persist and not is_l32:
            write_report(f"{prefix}_model_mismatch.json", mismatch)
        print(json.dumps({"ok": False, **mismatch}, indent=2, default=str))
        return 2

    from app.llm.policy.eval_arm import use_prompt_eval_arm
    from p8_l3_live_seams import execute_row, summarize_request_binding

    bank = load_bank()
    thresholds = load_thresholds()
    digest = dry["bank_hash"]
    expected_hash = "5f78ccbe1940149a67dcd1052140c44c854ec42a409d7644b47e5357010dbf51"
    if digest != expected_hash:
        print(json.dumps({"ok": False, "eval_status": "BANK_HASH_DRIFT", "bank_hash": digest}, indent=2))
        return 2

    if persist and is_l32 and (REPORT_DIR / "l3_2_scorecard.json").exists():
        print(
            json.dumps(
                {
                    "ok": False,
                    "eval_status": "L3_2_ARTIFACT_PROTECTED",
                    "reason": "Refusing to overwrite frozen L3-2 artifacts. Use --ab-arm.",
                },
                indent=2,
            )
        )
        return 2
    frozen_ab = {"ab_active", "ab_candidate"}
    if persist and prefix in frozen_ab and (REPORT_DIR / f"{prefix}_scorecard.json").exists():
        print(
            json.dumps(
                {
                    "ok": False,
                    "eval_status": "AB_ARTIFACT_PROTECTED",
                    "reason": (
                        f"Refusing to overwrite committed {prefix} artifacts. "
                        "Pass --report-prefix with a new name (for example ab_binding)."
                    ),
                },
                indent=2,
            )
        )
        return 2

    session_id = None
    raw_rows: list[dict[str, Any]] = []
    with use_prompt_eval_arm("candidate" if arm == "candidate" else "active"):
        for row in bank["rows"]:
            print(f"{prefix} running {row['row_id']} seam={row.get('seam')} arm={arm}", flush=True)
            result = _jsonable(execute_row(row, model=str(identity.get("model")), session_id=session_id))
            if result.get("session_id"):
                session_id = result["session_id"]
            raw_rows.append(result)
            if persist:
                write_report(
                    f"{prefix}_raw_results.json",
                    {"product_sha": PRODUCT_SHA, "bank_hash": digest, "prompt_arm": arm, "rows": raw_rows},
                )

    scorecard = aggregate_live_results(
        rows=raw_rows,
        bank_digest=digest,
        identity=identity,
        thresholds=thresholds,
        provenance=dry.get("prompt_provenance") or provenance_rows(),
    )
    scorecard["phase"] = "L3-2" if is_l32 else "P8-B"
    scorecard["prompt_arm"] = arm
    scorecard["live_ab_eval_performed"] = not is_l32
    scorecard["candidate_prompt_created"] = True
    scorecard["p4_contract_candidate_activated"] = False
    scorecard["compose_env_keys_applied"] = applied_keys
    scorecard["healthy_endpoint"] = dry.get("healthy_endpoint")
    binding = summarize_request_binding(raw_rows)
    scorecard["request_binding"] = {
        "binding_proven": binding.get("binding_proven"),
        "harness_defect": binding.get("harness_defect"),
        "candidate_roles_observed": binding.get("candidate_roles_observed"),
        "candidate_roles_missing_llm_call": binding.get("candidate_roles_missing_llm_call"),
    }
    failures = {
        "prompt_arm": arm,
        "authority_violations": scorecard["authority_violations"],
        "evidence_hallucinations": scorecard["evidence_hallucinations"],
        "failure_classification_by_case": scorecard["failure_classification_by_case"],
        "failed_case_ids": scorecard["failed_case_ids"],
        "fallback_rescued_cases": scorecard["fallback_rescued_cases"],
        "eval_harness_defects": [
            row["case_id"] for row in raw_rows if row.get("failure_class") == "EVAL_HARNESS_DEFECT"
        ],
        "product_contract_defects": [
            row["case_id"] for row in raw_rows if row.get("failure_class") == "PRODUCT_CONTRACT_FAILURE"
        ],
        "threshold_review_candidate": scorecard.get("threshold_review_candidate") or [],
        "role_metrics": scorecard.get("role_metrics") or {},
    }
    if persist:
        write_report(f"{prefix}_scorecard.json", scorecard)
        write_report(f"{prefix}_failure_analysis.json", failures)
        write_report(f"{prefix}_binding.json", binding)
    print(
        json.dumps(
            {
                "ok": True,
                "eval_status": scorecard["eval_status"],
                "prompt_arm": arm,
                "baseline_decision": scorecard["baseline_decision"],
                "rows_failed": scorecard["rows_failed"],
                "semantic_success_rate": scorecard["semantic_success_rate"],
                "llm_success_rate": scorecard["llm_success_rate"],
                "role_metrics": scorecard.get("role_metrics"),
                "binding_proven": binding.get("binding_proven"),
                "binding_harness_defect": binding.get("harness_defect"),
            },
            indent=2,
        )
    )
    return 0


def compare_ab(active: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    a_role = active.get("role_metrics") or {}
    c_role = candidate.get("role_metrics") or {}

    def metric(name: str) -> dict[str, Any]:
        a_val = next((item["actual"] for item in active.get("threshold_results") or [] if item["metric"] == name), None)
        c_val = next((item["actual"] for item in candidate.get("threshold_results") or [] if item["metric"] == name), None)
        return {"active": a_val, "candidate": c_val}

    winners: dict[str, str] = {}
    rejected: dict[str, str] = {}
    if (c_role.get("t4_accepted") or 0) > (a_role.get("t4_accepted") or 0) and not candidate.get("authority_violations"):
        winners["semantic_t4"] = "candidate"
    else:
        rejected["semantic_t4"] = "no_safe_improvement" if (c_role.get("t4_accepted") or 0) <= (a_role.get("t4_accepted") or 0) else "safety_regression"
    if (c_role.get("spl_pass") or 0) > (a_role.get("spl_pass") or 0) and not candidate.get("authority_violations"):
        winners["spl_advisory_generator"] = "candidate"
    else:
        rejected["spl_advisory_generator"] = "no_safe_improvement"
    if (c_role.get("planner_schema_success") or 0) > (a_role.get("planner_schema_success") or 0):
        winners["investigation_planner"] = "candidate"
    else:
        rejected["investigation_planner"] = "no_safe_improvement"

    safety_ok = not candidate.get("authority_violations") and not candidate.get("evidence_hallucinations")
    return {
        "phase": "P8-B",
        "bank_hash": active.get("bank_hash"),
        "active_semantic_score": metric("semantic_correctness")["active"],
        "candidate_semantic_score": metric("semantic_correctness")["candidate"],
        "active_initial_pass_rate": metric("initial_pass_rate")["active"],
        "candidate_initial_pass_rate": metric("initial_pass_rate")["candidate"],
        "active_schema_validity": metric("schema_validity")["active"],
        "candidate_schema_validity": metric("schema_validity")["candidate"],
        "active_t4_accept_rate": a_role.get("t4_accept_rate"),
        "candidate_t4_accept_rate": c_role.get("t4_accept_rate"),
        "active_spl_success": a_role.get("spl_success_rate"),
        "candidate_spl_success": c_role.get("spl_success_rate"),
        "active_planner_schema_success": a_role.get("planner_schema_success_rate"),
        "candidate_planner_schema_success": c_role.get("planner_schema_success_rate"),
        "active_fallback_rate": metric("fallback_rate")["active"],
        "candidate_fallback_rate": metric("fallback_rate")["candidate"],
        "authority_violations_active": active.get("authority_violations"),
        "authority_violations_candidate": candidate.get("authority_violations"),
        "evidence_hallucinations_active": active.get("evidence_hallucinations"),
        "evidence_hallucinations_candidate": candidate.get("evidence_hallucinations"),
        "latency_active": {"p50": active.get("latency_p50"), "p95": active.get("latency_p95")},
        "latency_candidate": {"p50": candidate.get("latency_p50"), "p95": candidate.get("latency_p95")},
        "frozen_threshold_results_active": active.get("threshold_results"),
        "frozen_threshold_results_candidate": candidate.get("threshold_results"),
        "candidate_winners_by_role": winners,
        "candidates_rejected_by_role": rejected,
        "safety_ok": safety_ok,
        "promotion_status": "PROMPT_PROMOTION_APPROVAL_REQUIRED" if winners and safety_ok else "NO_PROMOTION",
        "p4_contract_still_active_only": True,
        "live_mcp_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Probe live endpoint; refuse to invent scores if unhealthy",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Persist JSON under docs/evals/p8_l3/",
    )
    parser.add_argument(
        "--ab-arm",
        choices=("active", "candidate", "both"),
        help="P8-B A/B arm. Writes ab_* artifacts and never overwrites L3-2.",
    )
    parser.add_argument(
        "--report-prefix",
        help="Artifact prefix under docs/evals/p8_l3/. Never overwrites l3_2 / committed ab_*.",
    )
    parser.add_argument(
        "--intended-model",
        default="foundation-sec-instruct",
        help="Require this model id/name in /v1/models before scoring.",
    )
    parser.add_argument(
        "--local-base-url",
        help="Eval-only overlay for AI_SOC_LLM_LOCAL_BASE_URL. Does not rewrite .env.",
    )
    parser.add_argument(
        "--local-model",
        help="Eval-only overlay for AI_SOC_LLM_LOCAL_MODEL. Does not rewrite .env.",
    )
    args = parser.parse_args()
    if args.live:
        kwargs = {
            "persist": args.write_report,
            "intended_model": args.intended_model,
            "local_base_url": args.local_base_url,
            "local_model": args.local_model,
        }
        if args.ab_arm in {None, "active"} and args.ab_arm != "both":
            arm = args.ab_arm or "active"
            prefix = args.report_prefix or ("ab_active" if args.ab_arm else "l3_2")
            return live_run(arm=arm, report_prefix=prefix, **kwargs)
        if args.ab_arm == "candidate":
            prefix = args.report_prefix or "ab_candidate"
            return live_run(arm="candidate", report_prefix=prefix, **kwargs)
        # both
        active_prefix = args.report_prefix or "ab_active"
        active_rc = live_run(arm="active", report_prefix=active_prefix, **kwargs)
        if active_rc != 0:
            return active_rc
        candidate_prefix = "ab_candidate" if args.report_prefix is None else f"{args.report_prefix}_candidate"
        candidate_rc = live_run(arm="candidate", report_prefix=candidate_prefix, **kwargs)
        if candidate_rc != 0:
            return candidate_rc
        if args.write_report:
            active = json.loads((REPORT_DIR / "ab_active_scorecard.json").read_text(encoding="utf-8"))
            candidate = json.loads((REPORT_DIR / "ab_candidate_scorecard.json").read_text(encoding="utf-8"))
            comparison = compare_ab(active, candidate)
            write_report("ab_comparison.json", comparison)
            print(json.dumps({"ok": True, "eval_status": "P8_B_AB_COMPLETE", **{
                k: comparison[k] for k in (
                    "promotion_status",
                    "candidate_winners_by_role",
                    "candidates_rejected_by_role",
                    "active_semantic_score",
                    "candidate_semantic_score",
                )
            }}, indent=2))
        return 0
    rc, _report = dry_run(persist=args.write_report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
