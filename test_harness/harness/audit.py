"""JSONL audit-event emitter for the independent test harness.

The Stage 1 harness is intentionally independent from the backend application. Each
completed case appends one JSON line to the local audit log. Backend DB import
is handled later by a separate adapter that reads this file.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


_DEFAULT_AUDIT_LOG = Path(__file__).resolve().parent.parent / "audit_logs" / "test_runs.jsonl"
_FALLBACK_AUDIT_LOG = Path("/tmp") / "ai_soc_test_runs.jsonl"


@dataclass
class CaseAuditRecord:
    case_id: str
    trace_id: str
    user_query: str
    skill_pass: bool
    spl_spec_pass: bool
    findings_pass: bool
    overall_pass: bool
    routed_skill: str
    expected_skill: str
    spl: str
    expected_findings: dict[str, Any] = field(default_factory=dict)
    spl_reasons: tuple[str, ...] = field(default_factory=tuple)
    findings_reasons: tuple[str, ...] = field(default_factory=tuple)
    row_count: int = 0
    timestamp: float = field(default_factory=lambda: time.time())


def emit(record: CaseAuditRecord, log_path: Path | None = None) -> None:
    path = log_path or _resolve_log_path()
    envelope: dict[str, Any] = {
        "event_type": "harness_test_run",
        "schema_version": 1,
        **asdict(record),
    }
    try:
        _append_jsonl(path, envelope)
    except OSError:
        if log_path is None:
            _append_jsonl(_FALLBACK_AUDIT_LOG, envelope)


def _resolve_log_path() -> Path:
    override = os.environ.get("AI_SOC_TEST_AUDIT_PATH")
    return Path(override) if override else _DEFAULT_AUDIT_LOG


def _append_jsonl(path: Path, envelope: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(envelope, separators=(",", ":")) + "\n")


__all__ = ["CaseAuditRecord", "emit"]
