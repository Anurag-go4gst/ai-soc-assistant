from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.actions.capability_policy import ActionCapability, BLOCKED_EXECUTION_ACTIONS
from app.threat.mitre_kb import MitreMappingDecision


class SynthesisStatus(BaseModel):
    enabled: bool = False
    status: str = "disabled"
    provider: str | None = None
    model: str | None = None
    reason: str = "Stage 3K evidence-based synthesis is not enabled."
    allowed_inputs: list[str] = Field(default_factory=lambda: ["StructuredContext", "SourceEvidence summaries", "approved RAG excerpts"])


AggregateSource = Literal["splunk", "deterministic_policy", "not_available"]
AggregateComputedBy = Literal["splunk_global_query", "deterministic_precompute", "not_available"]
MissingEvidenceStatus = Literal["not_available", "not_collected", "insufficient", "unavailable"]


class PrecomputedAggregate(BaseModel):
    aggregate_key: str
    value: int | float | str | None = None
    status: str | None = None
    source: AggregateSource
    computed_by: AggregateComputedBy
    evidence_refs: list[str] = Field(default_factory=list)
    safe_for_model_use: bool


class MissingEvidenceItem(BaseModel):
    evidence_key: str
    status: MissingEvidenceStatus
    analyst_wording: str


class PermittedMitreTechnique(BaseModel):
    technique_id: str
    name: str
    status: str
    confidence: float
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)


class PermittedAction(BaseModel):
    action_id: str
    label: str
    tier: int
    allowed: bool
    blocked_reason: str | None = None
    requires_hil: bool
    execution_path: str


class SynthesisGuardConstraints(BaseModel):
    do_not_compute_global_aggregates: bool = True
    do_not_infer_absence_from_missing_evidence: bool = True
    mitre_must_be_from_permitted_set: bool = True
    model_may_introduce_new_mitre: bool = False
    max_action_tier: int = 1
    no_raw_spl_execution: bool = True
    no_remediation_actions: bool = True


class GovernedSynthesisPackage(BaseModel):
    package_version: str = "stage3k1a"
    trace_id: str
    selected_skill: str | None = None
    synthesis_allowed: bool = False
    precomputed_aggregates: list[PrecomputedAggregate]
    missing_evidence: list[MissingEvidenceItem]
    permitted_mitre_techniques: list[PermittedMitreTechnique]
    permitted_actions: list[PermittedAction]
    guard_constraints: SynthesisGuardConstraints = Field(default_factory=SynthesisGuardConstraints)
    source_evidence_refs: list[str] = Field(default_factory=list)


DEFAULT_MISSING_EVIDENCE: dict[str, str] = {
    "privileged_account_status": "privileged-account status is not yet available",
    "source_ip_ownership": "source IP ownership is not yet available",
    "cmdb_asset_criticality": "CMDB asset criticality is not yet available",
    "success_after_failure": "success-after-failure evidence is not yet available",
    "post_login_activity": "post-login activity evidence is not yet available",
}

SAFE_GLOBAL_DISTINCT_KEYS = ("global_distinct_users", "global_distinct_user_count")


def build_governed_synthesis_package(
    *,
    structured_context: dict[str, Any],
    source_evidence: list[dict[str, Any]],
    mitre_mappings: list[MitreMappingDecision] | list[dict[str, Any]] | None,
    action_capability: ActionCapability,
) -> GovernedSynthesisPackage:
    source_refs = [str(item.get("evidence_id")) for item in source_evidence if item.get("evidence_id")]
    return GovernedSynthesisPackage(
        trace_id=str(structured_context.get("trace_id") or ""),
        selected_skill=structured_context.get("selected_skill"),
        synthesis_allowed=False,
        precomputed_aggregates=_precomputed_aggregates(structured_context, source_refs),
        missing_evidence=_missing_evidence(structured_context),
        permitted_mitre_techniques=_permitted_mitre_techniques(mitre_mappings or [], structured_context),
        permitted_actions=_permitted_actions(action_capability),
        source_evidence_refs=source_refs,
    )


def _precomputed_aggregates(structured_context: dict[str, Any], source_refs: list[str]) -> list[PrecomputedAggregate]:
    metrics = structured_context.get("metrics") if isinstance(structured_context.get("metrics"), dict) else {}
    provenance = structured_context.get("aggregate_provenance") if isinstance(structured_context.get("aggregate_provenance"), dict) else {}
    for key in SAFE_GLOBAL_DISTINCT_KEYS:
        value = metrics.get(key)
        source = provenance.get(f"{key}.source")
        computed_by = provenance.get(f"{key}.computed_by")
        if isinstance(value, (int, float)) and source in {"splunk", "deterministic_policy"} and computed_by in {"splunk_global_query", "deterministic_precompute"}:
            return [
                PrecomputedAggregate(
                    aggregate_key="global_distinct_users",
                    value=value,
                    source=source,
                    computed_by=computed_by,
                    evidence_refs=source_refs,
                    safe_for_model_use=True,
                )
            ]
    return [
        PrecomputedAggregate(
            aggregate_key="global_distinct_users",
            status="not_available",
            source="not_available",
            computed_by="not_available",
            evidence_refs=[],
            safe_for_model_use=False,
        )
    ]


def _missing_evidence(structured_context: dict[str, Any]) -> list[MissingEvidenceItem]:
    missing = set(DEFAULT_MISSING_EVIDENCE)
    for item in structured_context.get("missing_evidence") or []:
        if str(item) in DEFAULT_MISSING_EVIDENCE:
            missing.add(str(item))
    return [
        MissingEvidenceItem(
            evidence_key=key,
            status="not_available",
            analyst_wording=DEFAULT_MISSING_EVIDENCE[key],
        )
        for key in sorted(missing)
    ]


def _permitted_mitre_techniques(
    mitre_mappings: list[MitreMappingDecision] | list[dict[str, Any]],
    structured_context: dict[str, Any],
) -> list[PermittedMitreTechnique]:
    has_success_or_session_evidence = _has_success_or_session_evidence(structured_context)
    techniques: list[PermittedMitreTechnique] = []
    seen: set[str] = set()
    for mapping in mitre_mappings:
        item = mapping.model_dump() if isinstance(mapping, BaseModel) else dict(mapping)
        technique_id = str(item.get("technique_id") or "")
        if not technique_id or technique_id in seen:
            continue
        status = str(item.get("status") or item.get("support") or "requires_validation")
        if technique_id == "T1078" and not has_success_or_session_evidence:
            status = "requires_validation"
        techniques.append(
            PermittedMitreTechnique(
                technique_id=technique_id,
                name=str(item.get("name") or technique_id),
                status=status,
                confidence=_confidence_for_status(status),
                rationale=str(item.get("why") or item.get("rationale") or "Deterministic MITRE registry permitted this technique."),
                evidence_refs=[str(ref) for ref in item.get("source_refs") or item.get("evidence_refs") or []],
            )
        )
        seen.add(technique_id)
    if "T1110.001" in seen and "T1078" not in seen:
        techniques.append(
            PermittedMitreTechnique(
                technique_id="T1078",
                name="Valid Accounts",
                status="requires_validation" if not has_success_or_session_evidence else "analyst_review",
                confidence=0.5,
                rationale="Valid Accounts remains a validation-only pivot until successful-login, session, or post-login evidence is present.",
                evidence_refs=[],
            )
        )
    return techniques


def _has_success_or_session_evidence(structured_context: dict[str, Any]) -> bool:
    text = str(structured_context.get("structured_facts") or "").lower()
    text += " " + str(structured_context.get("entity_summary") or "").lower()
    text += " " + str(structured_context.get("metrics") or "").lower()
    return any(marker in text for marker in ("success_after_failure", "successful login", "session", "post_login", "post-login"))


def _confidence_for_status(status: str) -> float:
    if status == "supported":
        return 0.8
    if status in {"candidate", "analyst_review", "requires_validation"}:
        return 0.5
    if status == "confirmed":
        return 0.95
    return 0.4


def _permitted_actions(action_capability: ActionCapability) -> list[PermittedAction]:
    allowed = set(action_capability.allowed_actions)
    blocked = set(action_capability.unavailable_actions) | set(BLOCKED_EXECUTION_ACTIONS) | {"remediation", "write_action"}
    actions: list[PermittedAction] = []
    for action_id in sorted(allowed):
        actions.append(
            PermittedAction(
                action_id=action_id,
                label=action_id.replace("_", " ").title(),
                tier=1,
                allowed=True,
                requires_hil=action_capability.hil_required,
                execution_path="renderer_only",
            )
        )
    for action_id in sorted(blocked - allowed):
        actions.append(
            PermittedAction(
                action_id=action_id,
                label=action_id.replace("_", " ").title(),
                tier=2,
                allowed=False,
                blocked_reason="blocked_by_stage3k1a_tier1_prepare_policy",
                requires_hil=True,
                execution_path="none",
            )
        )
    return actions
