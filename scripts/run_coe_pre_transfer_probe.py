#!/usr/bin/env python3
"""Run the COE India power-grid pre-transfer probe bank.

Usage:
  PYTHONPATH=backend:. python3 scripts/run_coe_pre_transfer_probe.py
  PYTHONPATH=backend:. python3 scripts/run_coe_pre_transfer_probe.py --check
  PYTHONPATH=backend:. python3 scripts/run_coe_pre_transfer_probe.py --json /tmp/coe_probe.json
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.chat.pipeline import build_live_chat_response  # noqa: E402
from app.evals.answer_efficacy_checks import evaluate_universal_efficacy  # noqa: E402
from app.schemas.requests import ChatRequest  # noqa: E402

BANK_PATH = REPO_ROOT / "docs" / "evals" / "coe_india_powergrid_probe_25_bank.json"

COE_STOP_VIOLATIONS = frozenset(
    {
        "run_contract_missing",
        "live_backed_without_execution",
        "results_table_not_allowed",
        "priority_prefix_without_severity",
        "route_authority_holder_contradiction",
        "duplicate_spl_warning",
        "duplicate_soc_review_checklist",
    }
)


class RowTimeout(RuntimeError):
    pass


def _raise_timeout(_signum: int, _frame: object) -> None:
    raise RowTimeout("row_timeout")


def _is_stop_violation(value: str) -> bool:
    return value in COE_STOP_VIOLATIONS or value.startswith("run_contract_field_missing:")


def _visible_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    message = payload.get("message")
    if isinstance(message, str):
        parts.append(message)
    analyst = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else {}
    for field in (
        "direct_answer_summary",
        "review_notice",
        "severity_label",
        "evidence_summary",
        "foundation_sec_analysis",
    ):
        value = analyst.get(field)
        if isinstance(value, str):
            parts.append(value)
    for field in ("recommended_actions", "analyst_checklist", "investigation_steps", "limitations"):
        values = analyst.get(field)
        if isinstance(values, list):
            parts.extend(str(item) for item in values if str(item).strip())
    draft = analyst.get("spl_draft_preview") if isinstance(analyst.get("spl_draft_preview"), dict) else {}
    for key in ("warning", "draft_spl", "not_catalog_approved_notice"):
        value = draft.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def _required_run_contract_violations(payload: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    contract = payload.get("run_contract") if isinstance(payload.get("run_contract"), dict) else None
    if contract is None:
        return ["run_contract_missing"]
    routing = contract.get("routing") if isinstance(contract.get("routing"), dict) else {}
    for field in (
        "execution_status",
        "collected_evidence_count",
        "source_evidence_available",
        "allow_live_result_language",
        "allow_results_table",
        "effective_hil_required",
    ):
        if field not in contract:
            violations.append(f"run_contract_field_missing:{field}")
    for field in ("canonical_skill", "legacy_skill", "legacy_authoritative", "authority_holder"):
        if field not in routing:
            violations.append(f"run_contract_field_missing:routing.{field}")
    return violations


def _renderer_violations(payload: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    visible = _visible_text(payload).lower()
    analyst = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else {}
    summary = str(analyst.get("direct_answer_summary") or "").lower()
    # Card and top-level message are alternate render surfaces; count duplicate
    # markers per surface (max), not summed, to avoid false positives on a single
    # body mirrored into both.
    card_lower = "\n".join(
        _visible_text({"analyst_response": analyst}).splitlines()
    ).lower()
    message_lower = str(payload.get("message") or "").lower()
    if "```" in summary or "search index=" in summary or "index=<" in summary:
        violations.append("direct_answer_summary_contains_draft_spl")
    if max(card_lower.count("soc review checklist"), message_lower.count("soc review checklist")) > 1:
        violations.append("duplicate_soc_review_checklist")
    if max(card_lower.count("lab-only draft spl preview"), message_lower.count("lab-only draft spl preview")) > 1:
        violations.append("duplicate_spl_warning")
    if visible.count("draft spl") > 2 and visible.count("```") > 2:
        violations.append("duplicate_draft_spl_block")
    if "live-backed" in visible:
        violations.append("live_backed_visible")
    if analyst.get("splunk_results_table"):
        violations.append("splunk_results_table_present")
    return violations


def evaluate_row(row: dict[str, Any], *, timeout_sec: int, strict_skill: bool) -> dict[str, Any]:
    started = time.monotonic()
    old_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(timeout_sec)
    try:
        response = build_live_chat_response(ChatRequest(message=str(row["question"])))
    except RowTimeout:
        return {
            "id": row["id"],
            "tier": row.get("tier"),
            "category": row.get("category"),
            "expected_skill": str(row.get("expected_skill") or ""),
            "selected_skill": None,
            "trace_id": None,
            "violations": [f"row_timeout:{timeout_sec}s"],
            "observations": [],
            "status": "fail",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    payload = response.model_dump(mode="json")
    selected_skill = str(payload.get("selected_skill") or "")
    expected_skill = str(row.get("expected_skill") or "")
    violations: list[str] = []
    observations: list[str] = []

    if expected_skill and selected_skill != expected_skill:
        mismatch = f"selected_skill_mismatch:expected={expected_skill}:got={selected_skill}"
        if strict_skill:
            violations.append(mismatch)
        else:
            observations.append(mismatch)

    violations.extend(_required_run_contract_violations(payload))
    efficacy = evaluate_universal_efficacy(
        query=str(row["question"]),
        payload=payload,
        category=str(row.get("category") or ""),
    )
    violations.extend(f"coe_stop:{item}" for item in efficacy if _is_stop_violation(item))

    if row.get("category") == "review_only_spl_renderer":
        violations.extend(_renderer_violations(payload))

    return {
        "id": row["id"],
        "tier": row.get("tier"),
        "category": row.get("category"),
        "expected_skill": expected_skill,
        "selected_skill": selected_skill,
        "trace_id": payload.get("trace_id"),
        "violations": sorted(set(violations)),
        "observations": sorted(set(observations)),
        "status": "pass" if not violations else "fail",
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


def run_bank(*, bank_path: Path = BANK_PATH, timeout_sec: int = 20, strict_skill: bool = False) -> dict[str, Any]:
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    rows = [
        evaluate_row(row, timeout_sec=timeout_sec, strict_skill=strict_skill)
        for row in bank.get("questions") or []
    ]
    fail_count = sum(1 for row in rows if row["status"] == "fail")
    return {
        "bank": bank.get("name"),
        "version": bank.get("version"),
        "question_count": len(rows),
        "fail_count": fail_count,
        "pass_count": len(rows) - fail_count,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit non-zero on any failed row")
    parser.add_argument("--json", type=Path, default=None, help="write full report JSON")
    parser.add_argument("--row-timeout-sec", type=int, default=20, help="maximum seconds per question")
    parser.add_argument("--strict-skill", action="store_true", help="fail when selected_skill differs from bank expectation")
    args = parser.parse_args()

    report = run_bank(timeout_sec=args.row_timeout_sec, strict_skill=args.strict_skill)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    for row in report["rows"]:
        status = row["status"].upper()
        line = f"  [{status}] {row['id']}: {row['selected_skill']}"
        if row["violations"]:
            line += f" - {'; '.join(row['violations'])}"
        elif row["observations"]:
            line += f" ({'; '.join(row['observations'])})"
        print(line)
    result = "PASS" if report["fail_count"] == 0 else "FAIL"
    print(f"RESULT: {result} ({report['pass_count']}/{report['question_count']} pass)")
    return 1 if args.check and report["fail_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
