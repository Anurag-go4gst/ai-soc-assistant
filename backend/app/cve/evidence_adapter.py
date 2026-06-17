"""CVE A4 — merge snapshot provenance into source_evidence / structured context."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.cve.requirements import cve_requirements_present
from app.cve.snapshot_store import CveSnapshotStore


def cve_requirements_from_plan(evidence_plan: dict[str, Any] | None) -> list[str]:
    required: list[str] = []
    if not isinstance(evidence_plan, dict):
        return required
    for key in ("missing_evidence", "evidence_needs", "required_produces"):
        value = evidence_plan.get(key)
        if isinstance(value, list):
            required.extend(str(item) for item in value)
    return required


def resolve_vulnerability_source_status(
    *,
    required_produces: list[str] | None = None,
    evidence_plan: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve CVE snapshot read-model status when the plan needs vulnerability context."""
    required = list(required_produces or [])
    required.extend(cve_requirements_from_plan(evidence_plan))
    if not cve_requirements_present(required):
        return None
    store = CveSnapshotStore(
        package_dir=settings.ai_soc_cve_snapshot_dir or None,
        stale_after_days=settings.ai_soc_cve_snapshot_stale_after_days,
    )
    status = store.vulnerability_source_status()
    return {
        "status": status.status,
        "snapshot_id": status.snapshot_id,
        "snapshot_generated_at": status.snapshot_generated_at,
        "snapshot_age_days": status.snapshot_age_days,
        "limitation": status.limitation,
        "provenance": status.provenance,
    }


def append_cve_snapshot_source_evidence(
    source_evidence: list[dict[str, Any]],
    *,
    trace_id: str,
    required_produces: list[str] | None = None,
    evidence_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Append honest CVE snapshot provenance — never fabricates CVE rows."""
    vuln = resolve_vulnerability_source_status(
        required_produces=required_produces,
        evidence_plan=evidence_plan,
    )
    if vuln is None:
        return source_evidence
    status = str(vuln.get("status") or "not_onboarded")
    collection_status = "collected" if status == "onboarded_snapshot" else "blocked"
    item = {
        "evidence_id": f"{trace_id}:vulnerability_source",
        "source_type": "cve_snapshot",
        "source_name": "vulnerability_source",
        "tool_name": "cve_snapshot_store",
        "collection_status": collection_status,
        "query_or_request_summary": "CVE snapshot read-model status (plan §3 A4)",
        "result_count": 0,
        "preview_rows": [],
        "warnings": [] if status == "onboarded_snapshot" else ["cve_snapshot_not_actionable"],
        "output_type": "vulnerability_source_status",
        "provider_used": "cve_snapshot_store",
        "provenance": "operator_vendored_cve_package",
        "vulnerability_source": vuln,
    }
    return [*source_evidence, item]


def vulnerability_source_from_evidence(source_evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in source_evidence:
        if item.get("source_name") == "vulnerability_source" or item.get("source_type") == "cve_snapshot":
            payload = item.get("vulnerability_source")
            if isinstance(payload, dict):
                return payload
    return None
