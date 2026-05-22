from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.connectors.telemetry import get_telemetry_connector


def import_harness_runs(path: Path) -> int:
    telemetry = get_telemetry_connector()
    imported = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if payload.get("event_type") not in {"harness_test_run", "ai_soc:test_run", "harness_test_run_db_fallback"}:
                continue
            _record_payload(telemetry, payload)
            imported += 1
    return imported


def _record_payload(telemetry: Any, payload: dict[str, Any]) -> None:
    trace_id = str(payload["trace_id"])
    case_id = str(payload["case_id"])
    telemetry.start_trace(trace_id, entrypoint="stage1_harness_jsonl_import", metadata={"case_id": case_id})
    telemetry.record_harness_result(
        trace_id,
        test_run_id=trace_id,
        case_id=case_id,
        user_query=payload.get("user_query"),
        expected_skill=payload.get("expected_skill"),
        actual_skill=payload.get("routed_skill"),
        generated_spl_ref=payload.get("spl"),
        spl_validation_result={
            "passed": bool(payload.get("spl_spec_pass", False)),
            "reasons": payload.get("spl_reasons", []),
        },
        mcp_execution_status="jsonl_import",
        expected_findings=payload.get("expected_findings", {}),
        actual_findings_summary=f"{payload.get('row_count', 0)} rows; reasons={payload.get('findings_reasons', [])}",
        layer_results={
            "skill": bool(payload.get("skill_pass", False)),
            "spl_spec": bool(payload.get("spl_spec_pass", False)),
            "findings": bool(payload.get("findings_pass", False)),
        },
        final_pass=bool(payload.get("overall_pass", False)),
    )
    telemetry.end_trace(trace_id, status="passed" if payload.get("overall_pass") else "failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Stage 1 harness JSONL audit records into telemetry DB.")
    parser.add_argument("--path", required=True, type=Path, help="Path to test_harness/audit_logs/test_runs.jsonl")
    args = parser.parse_args(argv)
    count = import_harness_runs(args.path)
    print(f"Imported {count} harness audit records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
