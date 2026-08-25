"""Cross-stream FinalEvidenceGate — single classifier for raw stream outputs.

This module is the canonical home for evidence classification and
evidence-derived permissions. It takes RAW stream inputs (execution, RAG
retrieval, MCP evidence, SPL drafts/validations, CVE snapshots, source
references) and produces a normalized :class:`GatedEvidenceState` that
downstream consumers (context sufficiency, MITRE, severity, RunContract,
AnswerContract, lineage, governance trace, renderer) project from.

Phase 1 scope: pure classification + permission logic only. The module does
NOT import the pipeline and has no side effects. The counting semantics here
intentionally mirror ``run_contract_builder._count_collected_evidence`` so a
later phase can delegate to this gate without changing the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# Execution statuses that authorize live-result language / results tables.
# Mirrors run_contract_builder._EXECUTION_AUTHORIZED_STATUSES.
_EXECUTION_AUTHORIZED_STATUSES = frozenset(
    {
        "executed",
        "executed_mock_evidence",
        "executed_live_evidence",
        "success",
    }
)

# source_type values treated as fetched/vendored reference context (not local
# environment confirmation): RAG excerpts, CVE advisory snapshots, vendor
# bulletins, MITRE descriptions, GitHub/source references. These support
# "according to this source" guidance but never local-environment confirmation.
_REFERENCE_SOURCE_TYPES = frozenset(
    {
        "rag",
        "cve_snapshot",
        "github",
        "github_reference",
        "source_reference",
        "vendor_bulletin",
        "mitre_reference",
    }
)

# collection_status values that mean a record was actually collected this turn.
_COLLECTED_STATUSES = frozenset({"collected"})

# collection_status values that mean a record is review-only / not evidence.
_REVIEW_STATUSES = frozenset({"skipped", "blocked", "failed", "ambiguous", "planned"})


class EvidenceClass(str, Enum):
    """Exactly one class is assigned to every stream output."""

    COLLECTED_EVIDENCE = "collected_evidence"
    SOURCE_BACKED_REFERENCE = "source_backed_reference"
    REVIEW_ARTIFACT = "review_artifact"
    CANDIDATE_CLAIM = "candidate_claim"
    SUPPRESSED_CONFIRMED_CLAIM = "suppressed_confirmed_claim"


@dataclass(frozen=True)
class GatedEvidenceState:
    """Normalized output of :func:`apply_final_evidence_gate`.

    ``gated_source_evidence`` is a CLASSIFIED VIEW (collected + source-backed
    reference records), not a replacement list. It is never fed into context
    sufficiency — sufficiency still inspects the full ``source_evidence`` and
    self-filters by ``collection_status`` (no list surgery, per the locked
    plan). ``to_dict()`` serializes refs only, never full filtered records.

    The permission booleans are the single authority for what the final answer
    may claim. They are faithful supersets of the run_contract logic they
    formalize.
    """

    gated_source_evidence: list[dict[str, Any]]
    collected_evidence_refs: list[str]
    source_backed_reference_refs: list[str]
    review_artifact_refs: list[str]
    candidate_claim_refs: list[str]
    suppressed_claims: list[str]
    collected_evidence_count: int
    environment_evidence_count: int
    source_backed_reference_count: int
    review_artifact_count: int
    candidate_claim_count: int
    allow_live_result_language: bool
    allow_results_table: bool
    allow_environment_fact_claims: bool
    allow_vulnerability_confirmed: bool
    allow_mitre_mapping: bool
    allow_severity_assessment: bool
    source_evidence_status: str
    mitre_visibility: str
    severity_label: str | None
    effective_hil_required: bool
    debug_raw_record_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return a plain JSON-safe mapping for structured_context / trace.

        Every value is a list / int / bool / str / None so the result can be
        stashed in ``structured_context["final_evidence_gate"]`` and dumped to
        debug or trace sinks without further serialization.
        """
        return {
            # Refs only — never serialize full filtered records into the debug
            # payload. The full in-memory view lives on ``gated_source_evidence``;
            # the gate does not feed it into sufficiency (no list surgery).
            "gated_source_evidence_refs": [
                _record_ref(record) for record in self.gated_source_evidence
            ],
            "collected_evidence_refs": list(self.collected_evidence_refs),
            "source_backed_reference_refs": list(self.source_backed_reference_refs),
            "review_artifact_refs": list(self.review_artifact_refs),
            "candidate_claim_refs": list(self.candidate_claim_refs),
            "suppressed_claims": list(self.suppressed_claims),
            "collected_evidence_count": int(self.collected_evidence_count),
            "environment_evidence_count": int(self.environment_evidence_count),
            "source_backed_reference_count": int(self.source_backed_reference_count),
            "review_artifact_count": int(self.review_artifact_count),
            "candidate_claim_count": int(self.candidate_claim_count),
            "allow_live_result_language": bool(self.allow_live_result_language),
            "allow_results_table": bool(self.allow_results_table),
            "allow_environment_fact_claims": bool(self.allow_environment_fact_claims),
            "allow_vulnerability_confirmed": bool(self.allow_vulnerability_confirmed),
            "allow_mitre_mapping": bool(self.allow_mitre_mapping),
            "allow_severity_assessment": bool(self.allow_severity_assessment),
            "source_evidence_status": str(self.source_evidence_status),
            "mitre_visibility": str(self.mitre_visibility),
            "severity_label": self.severity_label,
            "effective_hil_required": bool(self.effective_hil_required),
            "debug_raw_record_count": int(self.debug_raw_record_count),
        }


def classify_source_record(record: dict[str, Any]) -> EvidenceClass:
    """Classify a single ``source_evidence`` record into an :class:`EvidenceClass`.

    Rules (conservative, deterministic):

    - Reference source types (RAG, CVE snapshot) are
      ``source_backed_reference`` whenever they were retrieved/collected.
    - Splunk/MCP records with ``collection_status == "collected"`` and execution
      provenance are ``collected_evidence``.
    - Records with a review/skip/block/fail status, plus SAIA candidate-SPL
      outputs, are ``review_artifact``.
    - Anything unrecognized is treated as a ``review_artifact`` (fail safe: it
      will not be counted as collected evidence nor permit live claims).
    """
    if not isinstance(record, dict):
        return EvidenceClass.REVIEW_ARTIFACT

    source_type = str(record.get("source_type") or "").strip()
    collection_status = str(record.get("collection_status") or "").strip()
    output_type = str(record.get("output_type") or "").strip()

    # SAIA candidate SPL is a generated artifact for analyst review, never
    # collected environment evidence, even though it is marked "collected".
    if source_type == "splunk_mcp_saia" or output_type == "candidate_spl":
        return EvidenceClass.REVIEW_ARTIFACT

    if source_type in _REFERENCE_SOURCE_TYPES:
        if collection_status in _COLLECTED_STATUSES or _reference_retrieved(record):
            return EvidenceClass.SOURCE_BACKED_REFERENCE
        return EvidenceClass.REVIEW_ARTIFACT

    if collection_status in _COLLECTED_STATUSES:
        # Collected splunk/mcp/discovery rows with execution provenance.
        return EvidenceClass.COLLECTED_EVIDENCE

    if collection_status in _REVIEW_STATUSES:
        return EvidenceClass.REVIEW_ARTIFACT

    # Unknown / placeholder records fail safe to review_artifact.
    return EvidenceClass.REVIEW_ARTIFACT


def _reference_retrieved(record: dict[str, Any]) -> bool:
    """True when a reference record actually returned source content."""
    try:
        result_count = int(record.get("result_count") or 0)
    except (TypeError, ValueError):
        result_count = 0
    return result_count > 0


def _record_ref(record: dict[str, Any]) -> str:
    """Stable reference id for a source_evidence record."""
    evidence_id = record.get("evidence_id")
    if isinstance(evidence_id, str) and evidence_id.strip():
        return evidence_id.strip()
    source_type = str(record.get("source_type") or "unknown")
    source_name = str(record.get("source_name") or "unknown")
    return f"{source_type}:{source_name}"


def count_collected_evidence(
    *,
    execution: dict[str, Any] | None,
    soc_kb_retrieval: dict[str, Any] | None,
    mcp_evidence: list[dict[str, Any]] | None,
) -> int:
    """Count collected rows from RAW inputs — mirrors run_contract_builder.

    Reproduces ``run_contract_builder._count_collected_evidence`` exactly so a
    later phase can delegate to this gate without changing the numbers:

    - A retrieved SOC-KB (RAG) retrieval counts as +1 collected (reference type,
      but historically counted toward sufficiency).
    - An ``executed`` execution counts +1, plus +1 more when the
      ``broaden_scope_on_empty`` recipe's first call was empty across >=2 calls.
    - Each ``collected`` MCP evidence item counts +1.
    """
    count = 0

    if isinstance(soc_kb_retrieval, dict) and str(soc_kb_retrieval.get("retrieval_status") or "") == "retrieved":
        count += 1

    exec_dict = execution if isinstance(execution, dict) else {}
    exec_status = str(exec_dict.get("status") or "")
    if exec_status == "executed":
        count += 1
        orchestration = exec_dict.get("mcp_orchestration")
        if isinstance(orchestration, dict) and orchestration.get("recipe_id") == "broaden_scope_on_empty":
            calls = orchestration.get("calls")
            if isinstance(calls, list) and len(calls) >= 2:
                primary = calls[0]
                if isinstance(primary, dict) and primary.get("outcome") == "empty":
                    count += 1

    if isinstance(mcp_evidence, list):
        count += sum(
            1
            for item in mcp_evidence
            if isinstance(item, dict) and str(item.get("collection_status") or "") == "collected"
        )

    return count


def apply_final_evidence_gate(
    *,
    source_evidence: list[dict[str, Any]],
    execution: dict[str, Any],
    soc_kb_retrieval: dict[str, Any] | None,
    mcp_evidence: list[dict[str, Any]] | None,
    evidence_plan: dict[str, Any] | None,
    intent: dict[str, Any] | None,
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None = None,
    spl_draft_preview: dict[str, Any] | None = None,
    route_live_data_request: bool = False,
    execution_authorized: bool | None = None,
    effective_hil_required: bool = False,
    mitre_visibility: str = "hidden",
    severity_label: str | None = None,
    policy_backed: bool = False,
) -> GatedEvidenceState:
    """Classify raw stream outputs and derive evidence-backed permissions.

    Pure function — no pipeline imports, no side effects. ``source_evidence`` is
    the packaged record list to classify; the collected-evidence *count* is
    derived from the RAW ``execution``/``soc_kb_retrieval``/``mcp_evidence``
    inputs (NOT by counting packaged records) so it matches the existing
    run_contract authority exactly.

    Args:
        source_evidence: Packaged source_evidence records to classify.
        execution: Raw execution state (status, mcp_orchestration, ...).
        soc_kb_retrieval: Raw SOC-KB/RAG retrieval state.
        mcp_evidence: Raw MCP loop evidence hops.
        evidence_plan: Evidence plan (needs_mitre, spl_allowed, ...).
        intent: Intent classification.
        spl_validation: SPL validation record (review artifact).
        candidate_spl: Candidate SPL record (review artifact).
        spl_draft_preview: SPL draft preview (review artifact).
        route_live_data_request: Whether the route is a live-data request.
        execution_authorized: Precomputed authorization; recomputed from
            ``execution.status`` when None.
        effective_hil_required: Caller-resolved HIL flag (passed through and
            OR-ed with the live-without-execution rule).
        mitre_visibility: Incoming MITRE posture
            (``hidden`` / ``candidate`` / ``evidence_supported``).
        severity_label: Incoming severity label, if any.
        policy_backed: Whether the intent is policy-backed in catalog (enables
            MITRE/severity without collected evidence).

    Returns:
        A frozen :class:`GatedEvidenceState`.
    """
    records = source_evidence if isinstance(source_evidence, list) else []
    intent_dict = intent if isinstance(intent, dict) else {}
    plan_dict = evidence_plan if isinstance(evidence_plan, dict) else {}

    # --- collected count from RAW inputs (authority parity) -----------------
    collected_evidence_count = count_collected_evidence(
        execution=execution,
        soc_kb_retrieval=soc_kb_retrieval,
        mcp_evidence=mcp_evidence,
    )

    # --- execution authorization -------------------------------------------
    exec_dict = execution if isinstance(execution, dict) else {}
    exec_status = str(exec_dict.get("status") or "skipped")
    if execution_authorized is None:
        execution_authorized = exec_status.lower() in _EXECUTION_AUTHORIZED_STATUSES
    else:
        execution_authorized = bool(execution_authorized)

    # --- classify each packaged record -------------------------------------
    collected_refs: list[str] = []
    reference_refs: list[str] = []
    review_refs: list[str] = []
    candidate_refs: list[str] = []
    gated_source_evidence: list[dict[str, Any]] = []

    for record in records:
        evidence_class = classify_source_record(record)
        ref = _record_ref(record) if isinstance(record, dict) else "unknown"
        if evidence_class is EvidenceClass.COLLECTED_EVIDENCE:
            collected_refs.append(ref)
            gated_source_evidence.append(record)
        elif evidence_class is EvidenceClass.SOURCE_BACKED_REFERENCE:
            reference_refs.append(ref)
            gated_source_evidence.append(record)
        elif evidence_class is EvidenceClass.CANDIDATE_CLAIM:
            candidate_refs.append(ref)
            # candidate claims are not canonical evidence; excluded.
        else:  # REVIEW_ARTIFACT / SUPPRESSED_CONFIRMED_CLAIM
            review_refs.append(ref)
            # review artifacts are not canonical evidence; excluded.

    # --- permissions --------------------------------------------------------
    # allow_live mirrors run_contract: authorized execution AND collected rows.
    allow_live = execution_authorized and collected_evidence_count > 0
    allow_live_result_language = allow_live
    allow_results_table = allow_live
    allow_environment_fact_claims = allow_live

    # Vulnerability confirmation needs collected environment evidence with
    # asset identity + installed product/version. No current path supplies that,
    # so this stays False; CVE snapshots are reference-only.
    allow_vulnerability_confirmed = False

    environment_evidence_count = len(collected_refs)

    allow_mitre_mapping = _allow_mitre_mapping(
        evidence_plan=plan_dict,
        environment_evidence_count=environment_evidence_count,
        policy_backed=policy_backed,
    )

    allow_severity_assessment = _allow_severity_assessment(
        intent=intent_dict,
        evidence_plan=plan_dict,
        route_live_data_request=route_live_data_request,
        execution_authorized=execution_authorized,
        collected_evidence_count=collected_evidence_count,
        environment_evidence_count=environment_evidence_count,
        policy_backed=policy_backed,
    )

    # --- HIL: pass-through OR live-without-execution ------------------------
    # SPL-authoring products are review-only artifacts; live-data *interest*
    # must not invent an investigation-style HIL gate when execution is off.
    if str(plan_dict.get("answer_mode") or "") == "spl_utility_authoring":
        resolved_hil = bool(effective_hil_required)
    else:
        resolved_hil = bool(effective_hil_required) or (
            bool(route_live_data_request) and not execution_authorized
        )

    # --- normalized postures ------------------------------------------------
    normalized_mitre_visibility = _normalize_mitre_visibility(
        mitre_visibility=mitre_visibility,
        allow_mitre_mapping=allow_mitre_mapping,
    )
    resolved_severity = severity_label if allow_severity_assessment else None

    packaged_count = len(records)
    if collected_evidence_count > 0:
        source_evidence_status = "collected"
    elif packaged_count > 0:
        source_evidence_status = "metadata_only"
    else:
        source_evidence_status = "none"

    return GatedEvidenceState(
        gated_source_evidence=gated_source_evidence,
        collected_evidence_refs=collected_refs,
        source_backed_reference_refs=reference_refs,
        review_artifact_refs=review_refs,
        candidate_claim_refs=candidate_refs,
        suppressed_claims=[],
        collected_evidence_count=collected_evidence_count,
        environment_evidence_count=environment_evidence_count,
        source_backed_reference_count=len(reference_refs),
        review_artifact_count=len(review_refs),
        candidate_claim_count=len(candidate_refs),
        allow_live_result_language=allow_live_result_language,
        allow_results_table=allow_results_table,
        allow_environment_fact_claims=allow_environment_fact_claims,
        allow_vulnerability_confirmed=allow_vulnerability_confirmed,
        allow_mitre_mapping=allow_mitre_mapping,
        allow_severity_assessment=allow_severity_assessment,
        source_evidence_status=source_evidence_status,
        mitre_visibility=normalized_mitre_visibility,
        severity_label=resolved_severity,
        effective_hil_required=resolved_hil,
        debug_raw_record_count=packaged_count,
    )


def _allow_mitre_mapping(
    *,
    evidence_plan: dict[str, Any],
    environment_evidence_count: int,
    policy_backed: bool,
) -> bool:
    """MITRE mapping needs ``needs_mitre`` AND environment evidence or policy."""
    if not bool(evidence_plan.get("needs_mitre")):
        return False
    if environment_evidence_count > 0:
        return True
    return bool(policy_backed)


# Intent families that never assess severity without explicit evidence/policy.
# Mirrors run_contract_builder._NON_SEVERITY_INTENT_FAMILIES.
_NON_SEVERITY_INTENT_FAMILIES = frozenset(
    {
        "spl_generation_only",
        "guided_investigation",
        "knowledge_only",
        "policy_knowledge",
        "sop_or_playbook",
        "mitre_explanation",
        "clarification_required",
    }
)
# Mirrors run_contract_builder._POLICY_SEVERITY_FAMILIES.
_POLICY_SEVERITY_FAMILIES = frozenset(
    {
        "hybrid_alert_review",
        "alert_summary",
        "live_investigation",
        "mitre_mapping",
        "spl_generation_only",
    }
)


def _allow_severity_assessment(
    *,
    intent: dict[str, Any],
    evidence_plan: dict[str, Any],
    route_live_data_request: bool,
    execution_authorized: bool,
    collected_evidence_count: int,
    environment_evidence_count: int,
    policy_backed: bool,
) -> bool:
    """Severity rules — faithful to run_contract_builder._allow_severity_assessment.

    ``collected_evidence_count`` is retained for legacy RunContract parity and
    may include source-backed references such as retrieved RAG. Severity must
    not use that broad count as incident evidence. It requires policy backing,
    explicit execution authorization, or collected environment evidence.
    """
    # SPL-authoring product mode (review-only artifact) never assesses severity
    # from live-data interest, zero evidence, or policy co-match alone.
    if str(evidence_plan.get("answer_mode") or "") == "spl_utility_authoring":
        return False
    intent_family = str(intent.get("intent_family") or "")
    if policy_backed and intent_family in _POLICY_SEVERITY_FAMILIES:
        return True
    if route_live_data_request and not execution_authorized and collected_evidence_count == 0:
        return False
    if intent_family == "spl_generation_only" and route_live_data_request and collected_evidence_count == 0:
        return False
    if environment_evidence_count > 0 or execution_authorized:
        return True
    return intent_family not in _NON_SEVERITY_INTENT_FAMILIES


def _normalize_mitre_visibility(*, mitre_visibility: str, allow_mitre_mapping: bool) -> str:
    """Cap MITRE posture to allowed states.

    Three allowed postures: ``hidden``, ``candidate``, ``evidence_supported``.
    Only ``evidence_supported`` may render as mapped/confirmed, and it requires
    ``allow_mitre_mapping``. When mapping is disallowed, an incoming
    ``evidence_supported`` is downgraded to ``candidate``.
    """
    posture = str(mitre_visibility or "hidden").strip() or "hidden"
    if posture not in {"hidden", "candidate", "evidence_supported"}:
        # Unknown posture fails safe to candidate (never confirmed).
        posture = "candidate"
    if posture == "evidence_supported" and not allow_mitre_mapping:
        return "candidate"
    return posture
