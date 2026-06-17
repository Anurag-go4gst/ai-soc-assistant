"""CVE A4 — merge snapshot provenance into source_evidence / structured context."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.cve.requirements import cve_requirements_present
from app.cve.snapshot_store import CveSnapshotStore


def cve_requirements_from_plan(evidence_plan: dict[str, Any] | None) -> list[str]:
    required: list[str] = []
    if not isinstance(evidence_plan, dict):
        return required
    # Canonical evidence-plan keys emitted by app.chat.evidence_planner, plus the
    # older loop-state aliases (mcp_required_produces path) for completeness.
    for key in (
        "required_evidence_keys",
        "optional_evidence_keys",
        "missing_required_evidence",
        "missing_evidence",
        "evidence_needs",
        "required_produces",
    ):
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
    # Must satisfy SourceEvidenceEnvelope (schemas/responses.py): all required
    # fields present, else the whole /chat response fails validation.
    item = {
        "evidence_id": f"{trace_id}:vulnerability_source",
        "trace_id": trace_id,
        "source_type": "cve_snapshot",
        "source_name": "vulnerability_source",
        "tool_name": "cve_snapshot_store",
        "collection_status": collection_status,
        "query_or_request_summary": "CVE snapshot read-model status (plan §3 A4)",
        "result_count": 0,
        "fields_returned": [],
        "preview_rows": [],
        "raw_result_stored": False,
        "warnings": [] if status == "onboarded_snapshot" else ["cve_snapshot_not_actionable"],
        "sensitivity_flags": [],
        "output_type": "vulnerability_source_status",
        "provider_used": "cve_snapshot_store",
        "provenance": "operator_vendored_cve_package",
        "created_at": datetime.now(UTC).isoformat(),
        "vulnerability_source": vuln,
    }
    return [*source_evidence, item]


def vulnerability_context_line(vuln: dict[str, Any] | None) -> str | None:
    """Analyst-facing one-liner for the CVE snapshot status (plan §3 A4b).

    Onboarded snapshots are advisory context — never a confirmed unpatched-CVE claim
    without asset/CPE join keys. Returns None when there is no CVE context to state.
    """
    if not isinstance(vuln, dict) or not vuln.get("status"):
        return None
    status = str(vuln["status"])
    if status == "onboarded_snapshot":
        sid = vuln.get("snapshot_id") or "snapshot"
        age = vuln.get("snapshot_age_days")
        age_txt = f", {age}d old" if isinstance(age, int) else ""
        return (
            f"Vulnerability context: CVE snapshot onboarded ({sid}{age_txt}); advisory only "
            "— host/product correlation requires asset + CPE join keys before any unpatched-CVE claim."
        )
    if status == "stale":
        return (
            f"Vulnerability context: CVE snapshot is stale ({vuln.get('snapshot_id') or 'snapshot'}); "
            "treat as degraded and refresh before relying on CVE correlation."
        )
    return "Vulnerability context: CVE source not onboarded in this deployment; no CVE correlation performed."


def vulnerability_source_from_evidence(source_evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in source_evidence:
        if item.get("source_name") == "vulnerability_source" or item.get("source_type") == "cve_snapshot":
            payload = item.get("vulnerability_source")
            if isinstance(payload, dict):
                return payload
    return None
