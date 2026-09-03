"""Minimal canonical EvidenceState — derived view over existing governed runtime state.

Plan 8 E0A. This is not a database, persistence layer, or duplicate raw-evidence store.
Authority remains on SourceEvidence, StructuredContext, CanonicalFacts, and FinalEvidenceGate.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "minimal_evidence_state_v2"

TrustClass = Literal[
    "trusted_control_authority",
    "untrusted_input",
    "untrusted_evidence",
    "non_authoritative_generated",
]

EvidenceLifecycle = Literal[
    "required",
    "obtained",
    "missing",
    "stale",
    "invalidated",
    "blocked",
    "empty",
    "diagnostic",
]

_REFERENCE_SOURCE_TYPES = frozenset(
    {"rag", "cve_snapshot", "github", "github_reference", "source_reference", "vendor_bulletin", "mitre_reference"}
)
_GENERATED_SOURCE_TYPES = frozenset({"splunk_mcp_saia"})
_BLOCKED_STATUSES = frozenset({"blocked", "requires_human_review"})
_INVALIDATED_STATUSES = frozenset({"failed", "ambiguous"})
_STALE_MARKERS = ("stale", "expired", "freshness_exceeded")


class EvidenceStateItem(BaseModel):
    """Metadata for one required/obtained/missing/stale/invalidated/blocked key."""

    key: str
    status: EvidenceLifecycle
    provenance: str | None = None
    trust_class: TrustClass = "untrusted_evidence"
    scope: dict[str, Any] = Field(default_factory=dict)
    observed_at: str | None = None
    freshness: str | None = None
    applicability: str | None = None


class MinimalEvidenceState(BaseModel):
    """Deterministic derived EvidenceState. Contains keys and metadata, never raw rows."""

    schema_version: str = SCHEMA_VERSION
    required: list[str] = Field(default_factory=list)
    obtained: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    stale: list[str] = Field(default_factory=list)
    invalidated: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)
    empty: list[str] = Field(default_factory=list)
    diagnostic: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    trust_class: TrustClass = "untrusted_evidence"
    scope: dict[str, Any] = Field(default_factory=dict)
    items: list[EvidenceStateItem] = Field(default_factory=list)

    def model_dump_view(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload.pop("preview_rows", None)
        return payload


def derive_minimal_evidence_state(
    *,
    source_evidence: list[dict[str, Any]] | None = None,
    structured_context: dict[str, Any] | None = None,
    evidence_plan: dict[str, Any] | None = None,
    resolved_query_contract: dict[str, Any] | None = None,
    canonical_facts: dict[str, Any] | None = None,
    final_evidence_gate: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
) -> MinimalEvidenceState:
    """Project existing governed fields into the architecture EvidenceState vocabulary."""
    records = [item for item in (source_evidence or []) if isinstance(item, dict)]
    context = structured_context if isinstance(structured_context, dict) else {}
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    rqc = resolved_query_contract if isinstance(resolved_query_contract, dict) else {}
    facts = canonical_facts if isinstance(canonical_facts, dict) else {}
    gate = final_evidence_gate if isinstance(final_evidence_gate, dict) else {}
    exec_payload = execution if isinstance(execution, dict) else {}

    required = _unique(
        [
            *list(rqc.get("evidence_requirements") or []),
            *list(plan.get("required_evidence_keys") or []),
            *list(plan.get("missing_required_evidence") or []),
            *list(context.get("missing_evidence") or []),
        ]
    )
    if plan.get("needs_rag"):
        required = _unique([*required, "rag"])
    if plan.get("needs_spl"):
        required = _unique([*required, "spl"])
    if plan.get("needs_mcp"):
        required = _unique([*required, "mcp"])
    for cap in rqc.get("required_capabilities") or []:
        required = _unique([*required, str(cap)])

    obtained: list[str] = []
    stale: list[str] = []
    invalidated: list[str] = []
    blocked: list[str] = []
    empty: list[str] = []
    diagnostic: list[str] = []
    items: list[EvidenceStateItem] = []
    item_by_key: dict[str, EvidenceStateItem] = {}

    for record in records:
        key = _record_key(record)
        status = str(record.get("collection_status") or "")
        lifecycle = _lifecycle_for_record(record, rqc=rqc)
        item = EvidenceStateItem(
            key=key,
            status=lifecycle,
            provenance=str(record.get("provenance") or record.get("source_name") or "") or None,
            trust_class=_trust_class_for_record(record),
            scope=_scope_for_record(record, rqc=rqc),
            observed_at=str(record.get("created_at") or "") or None,
            freshness=_freshness_for_record(record),
        )
        item_by_key[key] = item
        if lifecycle == "obtained":
            obtained.append(key)
            for field_name in record.get("fields_returned") or []:
                field_key = str(field_name)
                obtained.append(field_key)
                item_by_key.setdefault(
                    field_key,
                    EvidenceStateItem(
                        key=field_key,
                        status="obtained",
                        provenance=item.provenance,
                        trust_class=item.trust_class,
                        scope=item.scope,
                        observed_at=item.observed_at,
                        freshness=item.freshness,
                    ),
                )
        elif lifecycle == "stale":
            stale.append(key)
        elif lifecycle == "invalidated":
            invalidated.append(key)
        elif lifecycle == "blocked":
            blocked.append(key)
        elif lifecycle == "empty":
            empty.append(key)
        elif lifecycle == "diagnostic":
            diagnostic.append(key)
        elif status not in {"collected", "skipped", "planned"}:
            invalidated.append(key)

    for fact in facts.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        kind = str(fact.get("kind") or "")
        if not kind:
            continue
        provenance = fact.get("provenance") if isinstance(fact.get("provenance"), dict) else {}
        evidence_class = str(provenance.get("evidence_class") or "")
        is_obtained_evidence = bool(
            kind not in {"entity", "timeframe", "plan_step_outcome"}
            and evidence_class not in {"plan", "session"}
            and _fact_has_accepted_evidence(fact)
        )
        # CanonicalFacts uses one `executed_evidence` kind for every SourceEvidence
        # record, including governed SOC-KB retrieval. The EvidenceState key
        # `executed_evidence` is read as "evidence produced by an actual execution",
        # so only a fact whose provenance is an execution class may claim it; a
        # knowledge/reference record is projected under its own key instead. The
        # fact stream itself is untouched -- this is the derived view only.
        kind = _evidence_state_key_for_fact_kind(kind, evidence_class=evidence_class)
        lifecycle: EvidenceLifecycle = "obtained" if is_obtained_evidence else "diagnostic"
        if is_obtained_evidence:
            obtained.append(kind)
        else:
            diagnostic.append(kind)
        item_by_key.setdefault(
            kind,
            EvidenceStateItem(
                key=kind,
                status=lifecycle,
                provenance=str(provenance.get("node") or "canonical_facts") or None,
                trust_class=(
                    "untrusted_evidence"
                    if is_obtained_evidence
                    else "trusted_control_authority"
                    if evidence_class == "plan"
                    else "untrusted_input"
                ),
                scope={"evidence_class": provenance.get("evidence_class")},
            ),
        )

    execution_status = str(exec_payload.get("status") or "").strip()
    if execution_status:
        diagnostic.append("execution_status")
        item_by_key.setdefault(
            "execution_status",
            EvidenceStateItem(
                key="execution_status",
                status="diagnostic",
                provenance="execution",
                trust_class="trusted_control_authority",
                scope={"status": execution_status},
            ),
        )

    if plan.get("needs_mcp") and plan.get("mcp_allowed") is not True:
        blocked.append("mcp")
        item_by_key["mcp"] = EvidenceStateItem(
            key="mcp",
            status="blocked",
            provenance="evidence_plan",
            trust_class="trusted_control_authority",
            scope={"reason": "mcp_not_allowed_by_evidence_plan"},
        )

    for claim in gate.get("suppressed_claims") or []:
        key = str(claim)
        invalidated.append(key)
        item_by_key.setdefault(
            key,
            EvidenceStateItem(
                key=key,
                status="invalidated",
                provenance="final_evidence_gate",
                trust_class="untrusted_evidence",
            ),
        )

    obtained = _unique(obtained)
    stale = _unique(stale)
    invalidated = _unique(invalidated)
    blocked = _unique(blocked)
    empty = _unique(empty)
    diagnostic = _unique(diagnostic)
    accepted = set(obtained)
    stale = [key for key in stale if key not in accepted]
    invalidated = [key for key in invalidated if key not in accepted]
    blocked = [key for key in blocked if key not in accepted]
    empty = [key for key in empty if key not in accepted]
    usable = set(obtained) - set(stale) - set(invalidated) - set(blocked)
    missing = [key for key in required if key not in usable]
    for key in missing:
        item_by_key.setdefault(
            key,
            EvidenceStateItem(
                key=key,
                status="missing",
                provenance="derived_minimal_evidence_state",
                trust_class="untrusted_evidence",
                applicability=_required_key_semantics(key),
            ),
        )
    items = []
    for key in _unique(
        [*required, *obtained, *stale, *invalidated, *blocked, *empty, *diagnostic, *missing]
    ):
        item = item_by_key.get(key)
        if item is None:
            item = EvidenceStateItem(
                key=key,
                status="obtained" if key in obtained else "missing",
                provenance="derived_minimal_evidence_state",
                trust_class="untrusted_evidence",
            )
            item_by_key[key] = item
        items.append(item)

    derived_from = [
        name
        for name, present in (
            ("source_evidence", bool(records)),
            ("structured_context", bool(context)),
            ("evidence_plan", bool(plan)),
            ("resolved_query_contract", bool(rqc)),
            ("canonical_facts", bool(facts)),
            ("final_evidence_gate", bool(gate)),
            ("execution", bool(exec_payload)),
        )
        if present
    ]
    return MinimalEvidenceState(
        required=required,
        obtained=obtained,
        missing=missing,
        stale=stale,
        invalidated=invalidated,
        blocked=blocked,
        empty=empty,
        diagnostic=diagnostic,
        provenance={"derived_from": derived_from, "raw_evidence_duplicated": False},
        trust_class="untrusted_evidence",
        scope={
            "time_scope": rqc.get("time_scope"),
            "entities": rqc.get("entities") if isinstance(rqc.get("entities"), dict) else {},
        },
        items=items,
    )


def _unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = str(value).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


_EXECUTION_EVIDENCE_CLASSES = frozenset({"mcp_search", "mcp", "execution", "splunk_mcp"})


def _required_key_semantics(key: str) -> str | None:
    """Name what a required key actually demands, so a gap is not misread.

    `spl` enters `required` from `evidence_plan.needs_spl` and means *executed SPL
    result*, not "an SPL artifact exists" -- a review-only draft leaves it missing by
    design. Spelling that out on the item keeps the list honest without rewriting
    `required`/`missing`, which feed evidence sufficiency.
    """
    if key == "spl":
        return "executed_spl_result"
    if key == "mcp" or key.startswith("mcp:"):
        return "executed_mcp_result"
    return None


def _evidence_state_key_for_fact_kind(kind: str, *, evidence_class: str) -> str:
    """Map a CanonicalFact kind onto its EvidenceState key.

    Identity for every kind except `executed_evidence`, which is only allowed to
    keep that key when the fact carries execution provenance. Anything else
    (governed RAG/knowledge records harvested from SourceEvidence) becomes
    `source_evidence`, so `executed_evidence == obtained` can never be satisfied
    by a run in which nothing executed.
    """
    if kind != "executed_evidence":
        return kind
    if evidence_class in _EXECUTION_EVIDENCE_CLASSES:
        return kind
    return "source_evidence"


def _record_key(record: dict[str, Any]) -> str:
    source_type = str(record.get("source_type") or "")
    if source_type in _REFERENCE_SOURCE_TYPES:
        return "rag" if source_type == "rag" else source_type
    if source_type in {"splunk_mcp", "splunk"}:
        return "mcp"
    if source_type in _GENERATED_SOURCE_TYPES:
        return "candidate_spl"
    evidence_id = str(record.get("evidence_id") or "").strip()
    return evidence_id or source_type or "unknown"


def _trust_class_for_record(record: dict[str, Any]) -> TrustClass:
    source_type = str(record.get("source_type") or "")
    if source_type in _GENERATED_SOURCE_TYPES or record.get("output_type") == "candidate_spl":
        return "non_authoritative_generated"
    if source_type == "manual":
        return "untrusted_input"
    return "untrusted_evidence"


def _scope_for_record(record: dict[str, Any], *, rqc: dict[str, Any]) -> dict[str, Any]:
    entities = record.get("entities") if isinstance(record.get("entities"), dict) else {}
    return {
        "source_name": record.get("source_name"),
        "source_type": record.get("source_type"),
        "time_range": record.get("time_range"),
        "time_scope": rqc.get("time_scope"),
        "tool_name": record.get("tool_name"),
        "entities": entities,
    }


def _freshness_for_record(record: dict[str, Any]) -> str | None:
    warnings = [str(item).lower() for item in (record.get("warnings") or [])]
    if any(marker in warning for warning in warnings for marker in _STALE_MARKERS):
        return "stale"
    created = str(record.get("created_at") or "").strip()
    return created or None


def _lifecycle_for_record(record: dict[str, Any], *, rqc: dict[str, Any]) -> EvidenceLifecycle:
    status = str(record.get("collection_status") or "")
    if status in _BLOCKED_STATUSES:
        return "blocked"
    if status in _INVALIDATED_STATUSES:
        return "invalidated"
    if _freshness_for_record(record) == "stale":
        return "stale"
    time_range = str(record.get("time_range") or "")
    time_scope = str(rqc.get("time_scope") or "")
    if time_range and time_scope and time_range != time_scope and "stale" in time_range.lower():
        return "stale"
    if status == "collected":
        if _trust_class_for_record(record) == "non_authoritative_generated":
            return "diagnostic"
        if _record_has_accepted_evidence(record):
            return "obtained"
        return "empty"
    if status in {"planned", "requested", "attempted", "skipped", "unavailable", "not_available"}:
        return "diagnostic"
    return "missing"


def _record_has_accepted_evidence(record: dict[str, Any]) -> bool:
    if "result_count" in record:
        return _positive_count(record.get("result_count"))
    for key in ("preview_rows", "rows", "citations", "chunks"):
        value = record.get(key)
        if isinstance(value, (list, tuple)) and value:
            return True
    return bool(record.get("raw_result_hash"))


def _fact_has_accepted_evidence(fact: dict[str, Any]) -> bool:
    payload = fact.get("payload") if isinstance(fact.get("payload"), dict) else {}
    if fact.get("kind") == "rag_citation":
        return bool(payload.get("citation"))
    if fact.get("kind") == "executed_evidence":
        return _positive_count(payload.get("row_count")) or bool(payload.get("row_summary"))
    return bool(payload)


def _positive_count(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False
