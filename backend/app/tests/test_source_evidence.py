"""Plan 8 E0A — EvidenceState derives from SourceEvidence without copying raw rows."""

from __future__ import annotations

from app.evidence.minimal_evidence_state import derive_minimal_evidence_state
from app.evidence.source_evidence import build_source_evidence
from app.tests.test_evidence_context import APPROVED_VALIDATION, EXECUTED


def test_source_evidence_projection_preserves_provenance_not_preview_rows() -> None:
    records = build_source_evidence(
        trace_id="trace-e0a-source",
        query="failed logins",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTED,
    )
    assert any(record.get("preview_rows") for record in records)
    state = derive_minimal_evidence_state(source_evidence=records)
    dumped = state.model_dump_view()
    assert dumped["provenance"]["derived_from"] == ["source_evidence"]
    assert "preview_rows" not in dumped
    assert not any("preview_rows" in item for item in dumped["items"])
    raw_values = {str(row) for record in records for row in (record.get("preview_rows") or [])}
    assert not any(value in str(dumped) for value in raw_values if "svc_app" in value)
    mcp_item = next(item for item in state.items if item.key == "mcp")
    assert mcp_item.trust_class == "untrusted_evidence"
    assert mcp_item.provenance
    assert mcp_item.status == "obtained"
    assert "mcp" in state.obtained
