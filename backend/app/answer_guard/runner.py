"""P6: orchestrate dormant semantic guards when answer-guard flag is enabled."""

from __future__ import annotations

from typing import Any

from app.answer_guard.models import AnswerGuardStatus
from app.config import settings
from app.synthesis.models import GovernedSynthesisPackage


def run_answer_guard_lab(
    *,
    draft: dict[str, Any] | None,
    package: GovernedSynthesisPackage | None,
    structured_context: dict[str, Any],
    source_evidence: list[dict[str, Any]],
    severity_label: str | None,
    action_policy: dict[str, Any],
) -> AnswerGuardStatus:
    if not settings.ai_soc_llm_answer_guard_enabled:
        return AnswerGuardStatus(
            enabled=False,
            guard_status="disabled",
            reason="AI_SOC_LLM_ANSWER_GUARD_ENABLED is false; no generated answer is being guarded.",
        )

    if draft is None:
        return AnswerGuardStatus(
            enabled=True,
            guard_status="skipped",
            reason="No synthesis draft was produced; Answer Guard did not run.",
        )

    from app.answer_guard.rules import (
        GuardResult,
        guard_action_tier,
        guard_aggregate_overclaim,
        guard_evidence_presence,
        guard_internal_leakage,
        guard_mitre_status,
        guard_priority_enum,
        guard_severity_authority,
        guard_spl_execution,
        guard_splunk_table_fidelity,
    )

    evidence_bundle = build_guard_evidence_bundle(
        draft=draft,
        package=package,
        structured_context=structured_context,
        source_evidence=source_evidence,
    )
    deterministic_mitre = {
        row.technique_id: row.status for row in (package.permitted_mitre_techniques if package else [])
    }
    findings: list[GuardResult] = []
    findings.extend(guard_aggregate_overclaim(draft, evidence_bundle))
    findings.extend(guard_evidence_presence(draft, evidence_bundle))
    findings.extend(guard_mitre_status(draft, deterministic_mitre))
    findings.extend(guard_severity_authority(draft, severity_label))
    findings.extend(guard_priority_enum(draft))
    findings.extend(guard_action_tier(draft, action_policy))
    findings.extend(guard_spl_execution(draft, validate_candidate=bool(draft.get("candidate_spl"))))
    findings.extend(guard_internal_leakage(draft))
    findings.extend(
        guard_splunk_table_fidelity(
            draft.get("splunk_results_table") or [],
            evidence_bundle.get("splunk_preview_rows") or [],
            strict=False,
        )
    )

    passed = sorted({item.guard_id for item in findings if item.status == "pass"})
    failed = sorted({item.guard_id for item in findings if item.status in {"fail", "warn"}})
    blocking = [item for item in findings if item.status == "fail" and item.severity == "blocking_candidate"]

    if blocking:
        return AnswerGuardStatus(
            enabled=True,
            guard_status="blocked",
            passed_checks=passed,
            failed_checks=failed,
            blocked_reason=blocking[0].message,
            analyst_review_required=True,
            reason="Answer Guard blocked the synthesis draft.",
        )

    return AnswerGuardStatus(
        enabled=True,
        guard_status="passed",
        passed_checks=passed,
        failed_checks=failed,
        blocked_reason=None,
        analyst_review_required=bool(failed),
        reason="Answer Guard passed all blocking checks on the synthesis draft.",
    )


def build_guard_evidence_bundle(
    *,
    draft: dict[str, Any],
    package: GovernedSynthesisPackage | None,
    structured_context: dict[str, Any],
    source_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics = dict(structured_context.get("metrics") or {})
    bundle: dict[str, Any] = dict(metrics)
    for aggregate in package.precomputed_aggregates if package else []:
        if aggregate.safe_for_model_use and aggregate.value is not None:
            bundle[aggregate.aggregate_key] = aggregate.value
    splunk_preview_rows = _preview_rows(source_evidence)
    bundle["splunk_preview_rows"] = splunk_preview_rows
    # Per-source distinct counts stay in preview rows only (not summed globally).
    failed_login_rows = [row for row in splunk_preview_rows if "failed_logins" in row]
    if failed_login_rows:
        bundle["total_failed_logins"] = sum(int(row.get("failed_logins") or 0) for row in failed_login_rows)
    return bundle


def _preview_rows(source_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preview_rows: list[dict[str, Any]] = []
    for envelope in source_evidence:
        if envelope.get("source_type") == "splunk_mcp":
            rows = envelope.get("preview_rows") or []
            preview_rows.extend(row for row in rows if isinstance(row, dict))
    return preview_rows
