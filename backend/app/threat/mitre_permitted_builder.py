"""P5-6/P5-8: Deterministic per-row mitre_permitted builder.

Report-only. Never writes to mitre_permitted[] as 'supported' without SOC approval.
Joins: (1) use-case catalog mitre_candidates, (2) local ATT&CK bundle validation.
Status bridge maps target vocab to existing mitre_kb codes at the boundary.

Target vocab: supported | candidate | needs_review | not_mapped | not_applicable
Existing MITRE_MAPPING_STATUSES bridge (C.1 table):
  supported    <- supported, confirmed
  candidate    <- candidate
  needs_review <- requires_validation, analyst_review
  not_mapped   <- no deterministic mapping
  not_applicable <- knowledge-only / no ATT&CK need
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.threat.mitre_kb import load_mitre_techniques
from app.use_cases.registry import get_use_case, match_use_cases


# Target status vocabulary (P5-8 canonical).
STATUS_SUPPORTED = "supported"
STATUS_CANDIDATE = "candidate"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_NOT_MAPPED = "not_mapped"
STATUS_NOT_APPLICABLE = "not_applicable"

TARGET_STATUSES = frozenset({
    STATUS_SUPPORTED,
    STATUS_CANDIDATE,
    STATUS_NEEDS_REVIEW,
    STATUS_NOT_MAPPED,
    STATUS_NOT_APPLICABLE,
})

# Bridge: existing mitre_kb status → target vocab.
_STATUS_BRIDGE: dict[str, str] = {
    "supported": STATUS_SUPPORTED,
    "confirmed": STATUS_SUPPORTED,
    "candidate": STATUS_CANDIDATE,
    "requires_validation": STATUS_NEEDS_REVIEW,
    "analyst_review": STATUS_NEEDS_REVIEW,
}


def bridge_mitre_status(existing_status: str) -> str:
    """Map existing MITRE_MAPPING_STATUSES value to target vocab."""
    return _STATUS_BRIDGE.get(existing_status.strip().lower(), STATUS_NEEDS_REVIEW)


@dataclass
class MitrePermittedEntry:
    technique_id: str
    technique_name: str
    tactic: str
    status: str
    source: str
    use_case_ids: list[str] = field(default_factory=list)
    in_local_bundle: bool = True
    soc_approved: bool = False
    requires_soc_review: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique_id": self.technique_id,
            "technique_name": self.technique_name,
            "tactic": self.tactic,
            "status": self.status,
            "source": self.source,
            "use_case_ids": self.use_case_ids,
            "in_local_bundle": self.in_local_bundle,
            "soc_approved": self.soc_approved,
            "requires_soc_review": self.requires_soc_review,
            "notes": self.notes,
        }


@dataclass
class MitrePermittedResult:
    question_ref: str
    use_case_id: str | None
    entries: list[MitrePermittedEntry] = field(default_factory=list)
    mitre_mapping_source: str = "none"
    overall_status: str = STATUS_NOT_MAPPED

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_ref": self.question_ref,
            "use_case_id": self.use_case_id,
            "entries": [e.to_dict() for e in self.entries],
            "mitre_mapping_source": self.mitre_mapping_source,
            "overall_status": self.overall_status,
        }


def _build_bundle_index() -> dict[str, Any]:
    """Build technique_id → technique index from local bundle."""
    return {t.technique_id: t for t in load_mitre_techniques()}


def _deterministic_status(use_case_id: str, technique_id: str) -> str:
    """Mirror existing _status_for logic; return target vocab."""
    if technique_id == "T1110.001" and use_case_id == "auth_failed_login_spike":
        return STATUS_SUPPORTED
    if technique_id == "T1078":
        return STATUS_CANDIDATE
    return STATUS_NEEDS_REVIEW


def build_mitre_permitted_for_question(
    question_ref: str,
    *,
    use_case_id: str | None = None,
    query_text: str | None = None,
) -> MitrePermittedResult:
    """Deterministic mitre_permitted for a registry row.

    Priority order:
    1. Explicit use_case_id → catalog mitre_candidates
    2. query_text → match_use_cases → catalog mitre_candidates
    3. All candidates validated against local bundle
    4. Status assigned deterministically; soc_approved=False always (report-only)
    """
    bundle = _build_bundle_index()

    resolved_use_case_id = use_case_id
    if not resolved_use_case_id and query_text:
        matches = match_use_cases(query_text, limit=1)
        if matches:
            resolved_use_case_id = matches[0].use_case_id

    if not resolved_use_case_id:
        return MitrePermittedResult(
            question_ref=question_ref,
            use_case_id=None,
            mitre_mapping_source="none",
            overall_status=STATUS_NOT_MAPPED,
        )

    use_case = get_use_case(resolved_use_case_id)
    if use_case is None:
        return MitrePermittedResult(
            question_ref=question_ref,
            use_case_id=resolved_use_case_id,
            mitre_mapping_source="none",
            overall_status=STATUS_NOT_MAPPED,
        )

    candidate_ids: list[str] = use_case.mitre_candidates
    if not candidate_ids:
        return MitrePermittedResult(
            question_ref=question_ref,
            use_case_id=resolved_use_case_id,
            mitre_mapping_source="use_case",
            overall_status=STATUS_NOT_MAPPED,
        )

    entries: list[MitrePermittedEntry] = []
    for technique_id in candidate_ids:
        technique = bundle.get(technique_id)
        if technique is None:
            entries.append(
                MitrePermittedEntry(
                    technique_id=technique_id,
                    technique_name="unknown",
                    tactic="unknown",
                    status=STATUS_NEEDS_REVIEW,
                    source="use_case_catalog",
                    use_case_ids=[resolved_use_case_id],
                    in_local_bundle=False,
                    soc_approved=False,
                    requires_soc_review=True,
                    notes=["id_not_in_local_bundle"],
                )
            )
            continue

        status = _deterministic_status(resolved_use_case_id, technique_id)
        entries.append(
            MitrePermittedEntry(
                technique_id=technique_id,
                technique_name=technique.name,
                tactic=technique.tactic,
                status=status,
                source="use_case_catalog",
                use_case_ids=[resolved_use_case_id],
                in_local_bundle=True,
                soc_approved=False,
                requires_soc_review=status != STATUS_SUPPORTED,
                notes=[],
            )
        )

    if not entries:
        overall = STATUS_NOT_MAPPED
    elif any(e.status == STATUS_SUPPORTED for e in entries):
        overall = STATUS_SUPPORTED
    elif any(e.status == STATUS_CANDIDATE for e in entries):
        overall = STATUS_CANDIDATE
    else:
        overall = STATUS_NEEDS_REVIEW

    return MitrePermittedResult(
        question_ref=question_ref,
        use_case_id=resolved_use_case_id,
        entries=entries,
        mitre_mapping_source="use_case_catalog",
        overall_status=overall,
    )


def technique_in_local_bundle(technique_id: str) -> bool:
    """Return True if technique_id exists in the local ATT&CK bundle."""
    bundle = _build_bundle_index()
    return technique_id in bundle


def canonical_technique_name_tactic(technique_id: str) -> tuple[str, str] | None:
    """Return authoritative (name, tactic) from the local bundle, or None if absent.

    Used to override untrusted LLM-supplied technique_name: a model may pair a
    real ID with the wrong name (observed: T1110.002 labelled "Password Guessing"
    instead of "Password Cracking"). The bundle is the single source of truth for
    the name once the ID validates.
    """
    technique = _build_bundle_index().get(technique_id)
    if technique is None:
        return None
    return technique.name, technique.tactic
