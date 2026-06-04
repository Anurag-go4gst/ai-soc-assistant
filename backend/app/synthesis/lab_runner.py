"""Flag-gated governed synthesis lab.

Default path builds a deterministic draft (no live LLM). When live synthesis is
enabled, the analyst-summary prose is narrated by the real model while every
fact stays deterministic; any failure falls back to the deterministic summary.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Any

from app.actions.capability_policy import ActionCapability
from app.chat.progress_context import emit_heartbeat, emit_llm_degraded
from app.llm.clients import LocalChatError
from app.llm.clients.local_chat_errors import local_chat_error_code, user_message_for_local_chat_error
from app.synthesis.live_narration import NarrationFailure, NarrationResult
from app.chat.progress_events import live_synthesis_timeout_seconds
from app.config import settings
from app.llm.clients import LocalChatClient, build_synthesis_client_from_settings
from app.synthesis.live_narration import narrate_analyst_summary
from app.evidence.context_sufficiency import (
    ANALYST_REVIEW_REQUIRED,
    BLOCKED_BY_POLICY,
    FULL_ANSWER,
    INSUFFICIENT_EVIDENCE,
    KNOWLEDGE_ONLY_ANSWER,
    PARTIAL_ANSWER,
    SPL_REVIEW_ONLY,
)
from app.synthesis.models import GovernedSynthesisPackage, SynthesisStatus, build_governed_synthesis_package
from app.threat.mitre_kb import MitreMappingDecision

_LAB_READY_MODES = {FULL_ANSWER, PARTIAL_ANSWER, KNOWLEDGE_ONLY_ANSWER}
_BLOCKED_MODES = {BLOCKED_BY_POLICY, INSUFFICIENT_EVIDENCE, SPL_REVIEW_ONLY, ANALYST_REVIEW_REQUIRED}


@dataclass(frozen=True)
class SynthesisLabResult:
    status: SynthesisStatus
    package: GovernedSynthesisPackage | None
    draft: dict[str, Any] | None
    analyst_summary: str | None


def run_governed_synthesis_lab(
    *,
    structured_context: dict[str, Any],
    source_evidence: list[dict[str, Any]],
    context_sufficiency: dict[str, Any],
    mitre_mappings: list[MitreMappingDecision] | list[dict[str, Any]] | None,
    action_capability: ActionCapability,
    severity_label: str | None,
    spl_validation: dict[str, Any] | None,
    human_review: dict[str, Any] | None,
    synthesis_client: LocalChatClient | None = None,
) -> SynthesisLabResult:
    if not settings.ai_soc_llm_final_synthesis_enabled:
        return SynthesisLabResult(
            status=SynthesisStatus(
                enabled=False,
                status="disabled",
                reason="AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED is false; production chat returns governed evidence/status only.",
            ),
            package=None,
            draft=None,
            analyst_summary=None,
        )

    mode = str(context_sufficiency.get("status") or INSUFFICIENT_EVIDENCE)
    readiness = bool(context_sufficiency.get("synthesis_readiness"))
    if settings.ai_soc_llm_require_context_sufficiency and not readiness:
        return _blocked_result(
            mode=mode,
            reason=f"context_sufficiency:{mode}",
            structured_context=structured_context,
            source_evidence=source_evidence,
            mitre_mappings=mitre_mappings,
            action_capability=action_capability,
            synthesis_allowed=False,
        )

    if mode in _BLOCKED_MODES:
        return _blocked_result(
            mode=mode,
            reason=f"context_sufficiency:{mode}",
            structured_context=structured_context,
            source_evidence=source_evidence,
            mitre_mappings=mitre_mappings,
            action_capability=action_capability,
            synthesis_allowed=False,
        )

    if human_review and human_review.get("required"):
        return _blocked_result(
            mode=mode,
            reason="human_review_required",
            structured_context=structured_context,
            source_evidence=source_evidence,
            mitre_mappings=mitre_mappings,
            action_capability=action_capability,
            synthesis_allowed=False,
        )

    package = build_governed_synthesis_package(
        structured_context=structured_context,
        source_evidence=source_evidence,
        mitre_mappings=mitre_mappings,
        action_capability=action_capability,
    )
    package = package.model_copy(update={"synthesis_allowed": mode in _LAB_READY_MODES})

    draft = _build_deterministic_lab_draft(
        package=package,
        structured_context=structured_context,
        source_evidence=source_evidence,
        severity_label=severity_label,
        mitre_mappings=mitre_mappings or [],
        spl_validation=spl_validation,
    )
    summary = str(draft.get("analyst_summary") or "").strip() or None

    provider = "deterministic_lab"
    model: str | None = None
    latency_ms: int | None = None
    reason = "Governed synthesis lab produced a deterministic draft from StructuredContext and SourceEvidence only."

    # Live narration: the model rewrites ONLY the analyst-summary prose from the
    # governed package; all structured facts stay deterministic. Any failure
    # keeps the deterministic summary, so a live model never breaks the answer.
    if settings.ai_soc_llm_live_synthesis_enabled and mode in _LAB_READY_MODES:
        client = synthesis_client or build_synthesis_client_from_settings()
        if client is not None:
            narration, timed_out = _narrate_with_progress_and_timeout(
                package=package,
                deterministic_draft=draft,
                severity_label=severity_label,
                client=client,
                structured_context=structured_context,
            )
            if timed_out:
                return SynthesisLabResult(
                    status=SynthesisStatus(
                        enabled=True,
                        status="partial_timeout",
                        provider="deterministic_lab",
                        reason="Live narration exceeded the governed timeout; kept the deterministic summary.",
                    ),
                    package=package,
                    draft=draft,
                    analyst_summary=summary,
                )
            if isinstance(narration, NarrationFailure):
                emit_llm_degraded(code=narration.code, message=narration.user_message)
                reason = f"{narration.user_message} (code={narration.code})"
                return SynthesisLabResult(
                    status=SynthesisStatus(
                        enabled=True,
                        status="degraded",
                        provider="deterministic_lab",
                        reason=reason,
                    ),
                    package=package,
                    draft=draft,
                    analyst_summary=summary,
                )
            if narration is not None:
                draft = {**draft, "analyst_summary": narration.summary, "draft_source": "live_model"}
                summary = narration.summary
                provider = "local_model"
                model = narration.model
                latency_ms = narration.latency_ms
                reason = "Analyst summary narrated by the live model; all facts remain deterministic."
            else:
                emit_llm_degraded(
                    code="llm_client_unavailable",
                    message="Live LLM client is not configured; using the deterministic summary.",
                )
                reason = "Live narration failed or was unavailable; kept the deterministic summary."

    return SynthesisLabResult(
        status=SynthesisStatus(
            enabled=True,
            status="completed",
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            reason=reason,
        ),
        package=package,
        draft=draft,
        analyst_summary=summary,
    )


def apply_synthesis_allowed_to_sufficiency(
    context_sufficiency: dict[str, Any],
    *,
    package: GovernedSynthesisPackage | None,
) -> dict[str, Any]:
    if not settings.ai_soc_llm_final_synthesis_enabled:
        return context_sufficiency
    allowed = bool(package and package.synthesis_allowed)
    if context_sufficiency.get("synthesis_allowed") == allowed:
        return context_sufficiency
    return {**context_sufficiency, "synthesis_allowed": allowed}


def _blocked_result(
    *,
    mode: str,
    reason: str,
    structured_context: dict[str, Any],
    source_evidence: list[dict[str, Any]],
    mitre_mappings: list[MitreMappingDecision] | list[dict[str, Any]] | None,
    action_capability: ActionCapability,
    synthesis_allowed: bool,
) -> SynthesisLabResult:
    package = build_governed_synthesis_package(
        structured_context=structured_context,
        source_evidence=source_evidence,
        mitre_mappings=mitre_mappings,
        action_capability=action_capability,
    )
    package = package.model_copy(update={"synthesis_allowed": synthesis_allowed})
    return SynthesisLabResult(
        status=SynthesisStatus(
            enabled=True,
            status="blocked",
            provider="deterministic_lab",
            reason=f"Synthesis lab blocked: {reason}.",
        ),
        package=package,
        draft=None,
        analyst_summary=None,
    )


def _build_deterministic_lab_draft(
    *,
    package: GovernedSynthesisPackage,
    structured_context: dict[str, Any],
    source_evidence: list[dict[str, Any]],
    severity_label: str | None,
    mitre_mappings: list[MitreMappingDecision] | list[dict[str, Any]],
    spl_validation: dict[str, Any] | None,
) -> dict[str, Any]:
    facts = structured_context.get("structured_facts") or []
    lead = ""
    if facts and isinstance(facts[0], dict):
        lead = str(facts[0].get("statement") or "").strip()

    mitre_lines: list[str] = []
    for item in package.permitted_mitre_techniques[:3]:
        mitre_lines.append(f"{item.technique_id} ({item.status})")

    missing = [item.analyst_wording for item in package.missing_evidence[:3]]
    aggregate_note = "Global distinct account count is not available from approved aggregates."
    for aggregate in package.precomputed_aggregates:
        if aggregate.safe_for_model_use and aggregate.value is not None:
            aggregate_note = f"Approved aggregate {aggregate.aggregate_key}={aggregate.value} (source={aggregate.source})."
            break

    summary_parts = []
    if lead:
        summary_parts.append(lead)
    if mitre_lines:
        summary_parts.append("MITRE (permitted set): " + ", ".join(mitre_lines) + ".")
    summary_parts.append(aggregate_note)
    if severity_label:
        summary_parts.append(f"Severity matrix: {severity_label}.")
    if missing:
        summary_parts.append("Missing evidence: " + " ".join(missing))

    preview_rows = _preview_rows_from_evidence(source_evidence)
    normalized_spl = None
    if spl_validation and spl_validation.get("approved"):
        normalized_spl = spl_validation.get("normalized_spl")

    mitre_payload = []
    for mapping in mitre_mappings:
        item = mapping.model_dump() if hasattr(mapping, "model_dump") else dict(mapping)
        technique_id = str(item.get("technique_id") or "")
        permitted = next((row for row in package.permitted_mitre_techniques if row.technique_id == technique_id), None)
        status = permitted.status if permitted else str(item.get("status") or "requires_validation")
        mitre_payload.append({"technique_id": technique_id, "status": status, "name": item.get("name")})

    priority = _priority_from_severity(severity_label)
    allowed_actions = [row.action_id for row in package.permitted_actions if row.allowed][:4]

    return {
        "analyst_summary": " ".join(part for part in summary_parts if part)[:1200],
        "severity_label": severity_label,
        "priority": priority,
        "mitre_mappings": mitre_payload,
        "splunk_results_table": preview_rows,
        "recommended_actions": allowed_actions,
        "missing_evidence": [item.evidence_key for item in package.missing_evidence],
        "candidate_spl": normalized_spl,
        "execution_eligible": False,
        "sent_to_mcp": False,
        "draft_source": "deterministic_lab",
    }


def _narrate_with_progress_and_timeout(
    *,
    package: GovernedSynthesisPackage,
    deterministic_draft: dict[str, Any],
    severity_label: str | None,
    client: LocalChatClient,
    structured_context: dict[str, Any],
) -> tuple[NarrationResult | NarrationFailure | None, bool]:
    """Run live narration with heartbeats; return (result, timed_out)."""
    import time

    timeout_s = live_synthesis_timeout_seconds()
    heartbeat_label = "Still generating the final governed answer..."
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            narrate_analyst_summary,
            package=package,
            deterministic_draft=deterministic_draft,
            severity_label=severity_label,
            client=client,
            structured_context=structured_context,
        )
        started = time.monotonic()
        poll_s = 4.0
        while True:
            remaining = timeout_s - (time.monotonic() - started)
            if remaining <= 0:
                return None, True
            try:
                result = future.result(timeout=min(poll_s, remaining))
                return result, False
            except concurrent.futures.TimeoutError:
                emit_heartbeat("generating_answer", heartbeat_label)
            except LocalChatError as exc:
                return (
                    NarrationFailure(code=exc.code, user_message=exc.user_message),
                    False,
                )
            except Exception as exc:  # noqa: BLE001
                code = local_chat_error_code(exc)
                return (
                    NarrationFailure(
                        code=code,
                        user_message=user_message_for_local_chat_error(code),
                    ),
                    False,
                )


def _preview_rows_from_evidence(source_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for envelope in source_evidence:
        if envelope.get("source_type") != "splunk_mcp":
            continue
        rows = envelope.get("preview_rows") or []
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)][:5]
    return []


def _priority_from_severity(severity_label: str | None) -> str | None:
    if not severity_label:
        return None
    for token in ("P1", "P2", "P3", "P4"):
        if token in severity_label:
            return token
    return None
