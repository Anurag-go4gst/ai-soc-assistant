"""Out-of-catalog OT analyst-ask probe evaluation."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.api.routes_chat import chat
from app.evals.answer_efficacy_checks import (
    evaluate_probe_expectations,
    evaluate_universal_efficacy,
    extract_response_observed,
)
from app.evals.golden_answer_runner import _model_to_dict
from app.evals.sentinel_eval import sentinel_runtime
from app.schemas.requests import ChatRequest

REPO_ROOT = Path(__file__).resolve().parents[3]
BANK_PATH = REPO_ROOT / "docs" / "evals" / "out_of_catalog_ot_probe_bank.json"
BASELINE_PATH = REPO_ROOT / "docs" / "evals" / "out_of_catalog_ot_probe_baseline.json"


def load_bank(*, path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or BANK_PATH).read_text(encoding="utf-8"))


def evaluate_probe_row(probe: dict[str, Any], *, synthesis_enabled: bool = False) -> dict[str, Any]:
    query = str(probe["query"])
    row: dict[str, Any] = {
        "id": probe["id"],
        "category": probe.get("category"),
        "query": query,
        "status": "ok",
        "violations": [],
        "severity": "pass",
    }
    try:
        with sentinel_runtime():
            response = chat(ChatRequest(message=query, session_id=f"ot-oc-probe-{uuid.uuid4()}"))
        payload = _model_to_dict(response)
        row["observed"] = extract_response_observed(payload, query=query)
        violations = list(
            evaluate_probe_expectations(
                query=query,
                payload=payload,
                expect=probe.get("expect"),
                synthesis_enabled=synthesis_enabled,
            )
        )
        violations.extend(
            evaluate_universal_efficacy(
                query=query,
                payload=payload,
                category=probe.get("category"),
                synthesis_enabled=synthesis_enabled,
            )
        )
        row["violations"] = sorted(set(violations))
        if row["violations"]:
            row["severity"] = "fail"
    except Exception as exc:  # pragma: no cover - surfaced in report
        row["status"] = "error"
        row["severity"] = "fail"
        row["error"] = str(exc)
        row["violations"] = ["pipeline_error"]
    return row


def evaluate_all(*, path: Path | None = None, synthesis_enabled: bool = False) -> dict[str, Any]:
    bank = load_bank(path=path)
    probes = bank.get("probes") or []
    rows = [evaluate_probe_row(probe, synthesis_enabled=synthesis_enabled) for probe in probes]
    counts = {"pass": 0, "fail": 0, "error": 0}
    for row in rows:
        if row.get("status") == "error":
            counts["error"] += 1
        elif row.get("severity") == "fail":
            counts["fail"] += 1
        else:
            counts["pass"] += 1
    return {
        "bank": bank.get("name"),
        "version": bank.get("version"),
        "probe_count": len(rows),
        "counts": counts,
        "critical_count": counts["fail"] + counts["error"],
        "rows": rows,
    }


def freeze_baseline(report: dict[str, Any]) -> None:
    payload = {
        "version": "out_of_catalog_ot_probe_baseline_v1",
        "bank_version": report.get("version"),
        "probe_count": report["probe_count"],
        "rows": {
            row["id"]: {
                "selected_skill": (row.get("observed") or {}).get("selected_skill"),
                "match_path": (row.get("observed") or {}).get("match_path"),
                "signal_class": (row.get("observed") or {}).get("signal_class"),
                "action_count": (row.get("observed") or {}).get("action_count"),
                "duplicate_actions": (row.get("observed") or {}).get("duplicate_actions"),
            }
            for row in report["rows"]
            if row.get("status") == "ok"
        },
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_against_baseline(report: dict[str, Any]) -> list[str]:
    if not BASELINE_PATH.is_file():
        return ["baseline missing: run scripts/eval_out_of_catalog_ot_probe.py --freeze"]
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    expected_rows = baseline.get("rows") or {}
    diffs: list[str] = []
    for row in report["rows"]:
        probe_id = row["id"]
        if row.get("severity") == "fail":
            diffs.append(f"{probe_id}: violations={row.get('violations')}")
            continue
        expected = expected_rows.get(probe_id)
        if expected is None:
            diffs.append(f"{probe_id}: missing from baseline")
            continue
        observed = row.get("observed") or {}
        for key, value in expected.items():
            if observed.get(key) != value:
                diffs.append(f"{probe_id}: {key} expected={value!r} got={observed.get(key)!r}")
    return diffs
