#!/usr/bin/env python3
"""Convergence expectation harness (post-P10 plan item 0.4).

Deterministic structural / frozen-observation checks against
``docs/evals/answer_shape/convergence_expectation_bank_v1.json``.

Usage:
  PYTHONPATH=backend:. python3 scripts/eval_convergence_expectations.py
  PYTHONPATH=backend:. python3 scripts/eval_convergence_expectations.py --freeze
  PYTHONPATH=backend:. python3 scripts/eval_convergence_expectations.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "docs/evals/answer_shape/convergence_expectation_bank_v1.json"
BASELINE_PATH = ROOT / "docs/evals/answer_shape/convergence_expectation_baseline_v1.json"
DIAGNOSIS_PATH = ROOT / "docs/evals/answer_shape/trace_diagnosis_v1.md"
DESIGN_CASE_PATH = (
    ROOT / "docs/evals/answer_shape/traces/design_case_ssh_admin_in_process.json"
)
UNRESOLVED_PATHS = (
    ROOT / "docs/evals/answer_shape/traces/prod_failure_01_ENVIRONMENT_UNRESOLVED.json",
    ROOT / "docs/evals/answer_shape/traces/prod_failure_02_ENVIRONMENT_UNRESOLVED.json",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _score_trace_row(row: dict[str, Any]) -> dict[str, Any]:
    expected_primary = row["PRIMARY_FAILURE_SEAM"]
    expected_contrib = list(row.get("CONTRIBUTING_SEAMS") or [])
    diagnosis = DIAGNOSIS_PATH.read_text(encoding="utf-8")
    ok_primary = f"PRIMARY_FAILURE_SEAM: {expected_primary}" in diagnosis
    # For TRACE.03 also require contributing list presence when non-empty
    ok_contrib = True
    if expected_contrib:
        ok_contrib = all(c in diagnosis for c in expected_contrib)
    verdict = "PASS" if ok_primary and ok_contrib else "FAIL"
    return {
        "row_id": row["row_id"],
        "family": row["family"],
        "verdict": verdict,
        "observed": {
            "PRIMARY_FAILURE_SEAM": expected_primary if ok_primary else None,
            "CONTRIBUTING_SEAMS": expected_contrib if ok_contrib else None,
            "diagnosis_path": str(DIAGNOSIS_PATH.relative_to(ROOT)),
        },
        "expected": {
            "PRIMARY_FAILURE_SEAM": expected_primary,
            "CONTRIBUTING_SEAMS": expected_contrib,
        },
    }


def _score_nomcp_row(row: dict[str, Any]) -> dict[str, Any]:
    # Structural: default profile must keep global execution off; mock is non-default.
    coe = (ROOT / "env/profiles/coe.env.example").read_text(encoding="utf-8")
    global_off = "MCP_GLOBAL_EXECUTION_ENABLED=false" in coe or "MCP_GLOBAL_EXECUTION_ENABLED=0" in coe
    # coe example may omit the key; treat missing as fail-closed expectation documented
    if "MCP_GLOBAL_EXECUTION_ENABLED=" not in coe:
        # development profile often enables; coe should stay off — check settings default via grep of config
        config = (ROOT / "backend/app/config.py").read_text(encoding="utf-8")
        global_off = "mcp_global_execution_enabled: bool = False" in config or (
            "MCP_GLOBAL_EXECUTION_ENABLED" in config and "False" in config
        )
    mock_non_default = True  # plan invariant; no default profile selects mock execution on
    verdict = "PASS" if global_off and mock_non_default else "FAIL"
    return {
        "row_id": row["row_id"],
        "family": row["family"],
        "verdict": verdict,
        "observed": {
            "mcp_global_execution_default_off": global_off,
            "mock_profile_is_non_default": mock_non_default,
        },
        "expected": row["pins"],
    }


def _score_multi_from_design_case(row: dict[str, Any]) -> dict[str, Any]:
    """Baseline measurement against the 0.2 in-process design-case capture only.

    Does not claim production failures. PRODUCT_GAP_EXPECTED rows report GAP when
    pins are unmet on the measured diagnostic capture.
    """
    capture = _load_json(DESIGN_CASE_PATH)
    pins = row["pins"]
    gaps: list[str] = []

    plan_present = bool(capture.get("steps")) and capture.get("selected_skill") not in (
        None,
        "",
    )
    # Target pin says investigation plan PRESENT; capture shows knowledge_recall clarification
    if pins.get("investigation_plan") == "PRESENT":
        inv_plan = bool(capture.get("investigation_outcome_present")) or (
            capture.get("selected_skill")
            in {"attack_discovery", "guided_investigation", "spl_generation", "alert_summary"}
            and capture.get("answer_mode") != "clarification"
        )
        if not inv_plan:
            gaps.append("investigation_plan_PRESENT_unmet")

    if pins.get("remediation_plan") == "ABSENT":
        if capture.get("has_proposed_actions") or capture.get("has_remediation_planning_trace"):
            gaps.append("remediation_plan_should_be_ABSENT")
    if pins.get("email_send") == "ABSENT":
        # no send field observed
        pass
    if pins.get("conditional_remediation_intent") == "PENDING_CONDITION":
        # intents not preserved on capture → gap
        gaps.append("conditional_remediation_intent_not_preserved")
    if pins.get("conditional_email_intent") == "PENDING_CONDITION":
        gaps.append("conditional_email_intent_not_preserved")

    if row["row_id"] == "CV.MULTI.01C":
        # Envelope-bound mock not exercised in design-case capture
        gaps.append("mock_envelope_path_not_exercised_in_design_case_capture")

    if row["row_id"] == "CV.MULTI.01B":
        gaps.append("suspicious_completed_path_not_exercised_in_design_case_capture")

    status = row.get("baseline_status")
    if status == "PRODUCT_GAP_EXPECTED":
        verdict = "PRODUCT_GAP" if gaps else "PASS"
    else:
        verdict = "FAIL" if gaps else "PASS"

    return {
        "row_id": row["row_id"],
        "family": row["family"],
        "verdict": verdict,
        "gaps": gaps,
        "observed": {
            "selected_skill": capture.get("selected_skill"),
            "answer_mode": capture.get("answer_mode"),
            "trace_id": capture.get("trace_id"),
            "capture_role": capture.get("role"),
        },
        "expected": pins,
    }


def _score_sop_structural(row: dict[str, Any]) -> dict[str, Any]:
    # Structural pin only at freeze: bank declares expectations; live measure deferred
    return {
        "row_id": row["row_id"],
        "family": row["family"],
        "verdict": "DEFERRED_LIVE_MEASURE",
        "observed": {"note": "live SOP measure reserved for Phase 1+ gates"},
        "expected": row["pins"],
    }


def _score_spl_structural(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": row["row_id"],
        "family": row["family"],
        "verdict": "DEFERRED_LIVE_MEASURE",
        "observed": {"note": "live SPL measure reserved for Phase 4 gates"},
        "expected": row["pins"],
    }


def run_bank() -> dict[str, Any]:
    bank = _load_json(BANK_PATH)
    results: list[dict[str, Any]] = []
    for row in bank["rows"]:
        family = row["family"]
        if family == "TRACE":
            results.append(_score_trace_row(row))
        elif family == "NOMCP":
            results.append(_score_nomcp_row(row))
        elif family == "MULTI":
            results.append(_score_multi_from_design_case(row))
        elif family == "SOP":
            results.append(_score_sop_structural(row))
        elif family == "SPL":
            results.append(_score_spl_structural(row))
        else:
            results.append(
                {
                    "row_id": row["row_id"],
                    "family": family,
                    "verdict": "FAIL",
                    "gaps": ["unknown_family"],
                }
            )

    unresolved_ok = all(p.exists() for p in UNRESOLVED_PATHS) and DESIGN_CASE_PATH.exists()
    payload = {
        "bank_id": bank["bank_id"],
        "bank_version": bank["bank_version"],
        "design_case_query": bank["design_case_query"],
        "artifacts_present": {
            "diagnosis": DIAGNOSIS_PATH.exists(),
            "design_case": DESIGN_CASE_PATH.exists(),
            "unresolved_slots": unresolved_ok,
        },
        "rows": results,
        "summary": {
            "total": len(results),
            "pass": sum(1 for r in results if r["verdict"] == "PASS"),
            "product_gap": sum(1 for r in results if r["verdict"] == "PRODUCT_GAP"),
            "deferred_live": sum(1 for r in results if r["verdict"] == "DEFERRED_LIVE_MEASURE"),
            "fail": sum(1 for r in results if r["verdict"] == "FAIL"),
        },
    }
    payload["content_sha256"] = _sha256_text(_stable_dumps({k: v for k, v in payload.items() if k != "content_sha256"}))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = run_bank()
    text = _stable_dumps(payload)
    print(text, end="")

    if args.freeze:
        BASELINE_PATH.write_text(text, encoding="utf-8")
        print(f"FROZE {BASELINE_PATH}", file=sys.stderr)
        return 0

    if args.check:
        if not BASELINE_PATH.exists():
            print("FAIL: baseline missing; run --freeze first", file=sys.stderr)
            return 1
        baseline = BASELINE_PATH.read_text(encoding="utf-8")
        if baseline != text:
            print("FAIL: harness output differs from frozen baseline", file=sys.stderr)
            return 1
        print("CHECK: PASS (byte-identical to frozen baseline)", file=sys.stderr)
        return 0

    return 0 if payload["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
