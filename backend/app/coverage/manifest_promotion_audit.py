"""Audit committed pattern_coverage_v1.json rows against S5 promotion gates."""

from __future__ import annotations

from typing import Any

from app.coverage.coverage_loader import list_coverage
from app.coverage.manifest_precondition_alignment import (
    evaluate_manifest_precondition_alignment,
)
from app.coverage.manifest_promotion_gates import evaluate_promotion_gates


def audit_committed_manifest(*, coe_signoff_recorded: bool = True) -> dict[str, Any]:
    """Read-only audit of every manifest entry (trust signal; does not block /chat)."""
    results = []
    alignments = []
    for entry in list_coverage():
        gate = evaluate_promotion_gates(
            entry,
            mode="committed",
            coe_signoff_recorded=coe_signoff_recorded,
        )
        gate_payload = gate.model_dump()
        alignment = evaluate_manifest_precondition_alignment(
            entry,
            gate,
            coe_signoff_recorded=coe_signoff_recorded,
        )
        gate_payload["precondition_alignment"] = alignment.model_dump()
        results.append(gate_payload)
        alignments.append(alignment.model_dump())

    all_integrity = all(item["manifest_integrity_ok"] for item in results)
    all_precondition_alignment_ok = all(
        item["alignment_status"] in ("aligned", "documented_gap") for item in alignments
    )
    return {
        "entry_count": len(results),
        "all_manifest_integrity_ok": all_integrity,
        "all_precondition_alignment_ok": all_precondition_alignment_ok,
        "entries": results,
    }
