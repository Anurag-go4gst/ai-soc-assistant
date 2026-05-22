"""Audit-event emitter for the test harness.

Each completed case produces one ``ai_soc:test_run`` event with the
per-layer results and the trace id. Events are written as JSON Lines to
``test_harness/audit_logs/test_runs.jsonl`` so they can be replayed or
shipped to a real audit sink later.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


_DEFAULT_AUDIT_LOG = (
    Path(__file__).resolve().parent.parent / "audit_logs" / "test_runs.jsonl"
)


@dataclass
class CaseAuditRecord:
    case_id: str
    trace_id: str
    skill_pass: bool
    spl_spec_pass: bool
    findings_pass: bool
    overall_pass: bool
    routed_skill: str
    expected_skill: str
    spl: str
    spl_reasons: tuple[str, ...] = field(default_factory=tuple)
    findings_reasons: tuple[str, ...] = field(default_factory=tuple)
    row_count: int = 0
    timestamp: float = field(default_factory=lambda: time.time())


def emit(record: CaseAuditRecord, log_path: Path | None = None) -> None:
    path = log_path or _resolve_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope: dict[str, Any] = {
        "event_type": "ai_soc:test_run",
        "schema_version": 1,
        **asdict(record),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(envelope, separators=(",", ":")) + "\n")


def _resolve_log_path() -> Path:
    override = os.environ.get("AI_SOC_TEST_AUDIT_PATH")
    return Path(override) if override else _DEFAULT_AUDIT_LOG


__all__ = ["CaseAuditRecord", "emit"]
