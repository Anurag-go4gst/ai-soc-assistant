"""Tier-D deterministic answer-quality checks (T5.1, plan 2026-06-10_0356 rev 3).

Judges the final chat payload — the answer an analyst actually receives —
on five binary dimensions. Forbidden-claim patterns are imported from the
governed answer composer so quality checks and composition share one source
of truth and cannot drift apart.

Every check returns a definitive pass/fail with a reason; no scores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.synthesis import claim_patterns

_SEVERITY_CLAIM = re.compile(r"\bP([1-4])\b")
_MITRE_ID = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")

# Analyst-card fields whose text reaches the analyst as prose.
_PROSE_FIELDS = (
    "finding_title",
    "one_sentence_finding",
    "direct_answer_summary",
    "evidence_summary",
    "severity_rationale",
    "severity_safety_note",
    "mitre_status_summary",
    "sop_guidance",
    "review_notice",
    "investigation_steps",
    "recommended_actions",
    "limitations",
    "analyst_checklist",
    "closure_conditions",
    "escalation_criteria",
)

# Fields where a bare P1–P4 token is a severity assertion. Action/step lists
# are excluded: their entries carry calibrated "P2 — do X" priority prefixes,
# which are work-ordering labels, not severity claims.
_SEVERITY_PROSE_FIELDS = (
    "finding_title",
    "one_sentence_finding",
    "direct_answer_summary",
    "evidence_summary",
    "severity_rationale",
    "mitre_status_summary",
)

# Enabled render section -> analyst_response fields that must back it.
# A section listed here with none of its backing fields populated is an
# empty promise to the analyst. Unmapped sections are skipped, not failed.
_SECTION_BACKING: dict[str, tuple[str, ...]] = {
    "draft_spl_preview": ("spl_draft_preview", "draft_spl_code"),
    "spl_artifact": ("spl_code",),
    "limitations": ("limitations",),
    # review_notice backs guidance on refusal/HIL answers ("no containment
    # action was performed; change approval required").
    "analyst_action_guidance": (
        "recommended_actions",
        "analyst_checklist",
        "investigation_steps",
        "review_notice",
    ),
    "procedural_steps": ("investigation_steps", "sop_guidance"),
    "investigation_guidance": ("investigation_steps", "closure_conditions", "sop_guidance"),
    "severity_assessment": ("severity_label",),
    "mitre_mapping": ("mitre_mappings",),
    "not_claimed": ("not_claimed",),
    "policy_citation": ("retrieved_playbook", "sop_guidance"),
    "live_results": ("splunk_results_table",),
    "triage_checklist": ("analyst_checklist",),
    "evidence_checklist": ("required_evidence",),
}


@dataclass
class CheckResult:
    check_id: str
    passed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "reason": self.reason}


def run_answer_quality_checks(payload: dict[str, Any]) -> list[CheckResult]:
    """Run all Tier-D checks against one chat response payload."""
    analyst = payload.get("analyst_response") or {}
    prose_parts = _collect_prose_parts(payload, analyst)
    prose = "\n".join(prose_parts)
    return [
        _grounding_no_orphan_claims(payload, analyst, prose),
        _completeness_sections(analyst),
        _actionability_priorities(payload, analyst),
        _honesty_limitations(payload, analyst, prose),
        _no_forbidden_claims(prose, prose_parts, payload),
    ]


def _collect_prose_parts(payload: dict[str, Any], analyst: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    message = payload.get("message")
    if isinstance(message, str):
        parts.append(message)
    for field in _PROSE_FIELDS:
        value = analyst.get(field)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value if isinstance(item, (str, int, float)))
    return parts


def _grounding_no_orphan_claims(
    payload: dict[str, Any], analyst: dict[str, Any], prose: str
) -> CheckResult:
    check_id = "grounding_no_orphan_claims"

    severity_decision = payload.get("severity_decision") or {}
    decided = str(
        (severity_decision.get("severity_label") if isinstance(severity_decision, dict) else None)
        or analyst.get("severity_label")
        or ""
    )
    decided_p = _SEVERITY_CLAIM.search(decided)
    severity_prose = "\n".join(
        str(analyst.get(field))
        for field in _SEVERITY_PROSE_FIELDS
        if isinstance(analyst.get(field), str)
    )
    if isinstance(payload.get("message"), str):
        severity_prose = f"{payload['message']}\n{severity_prose}"
    for claim in _SEVERITY_CLAIM.finditer(severity_prose):
        if not decided_p or claim.group(1) != decided_p.group(1):
            return CheckResult(
                check_id,
                False,
                f"prose claims severity P{claim.group(1)} but decided severity is {decided or 'unset'}",
            )

    allowed = _allowed_mitre_ids(payload, analyst)
    for match in _MITRE_ID.finditer(prose):
        technique_id = match.group(0).upper()
        if technique_id not in allowed:
            return CheckResult(
                check_id, False, f"prose cites {technique_id} absent from every contract MITRE list"
            )
    return CheckResult(check_id, True, "all severity and MITRE claims trace to contract fields")


def _allowed_mitre_ids(payload: dict[str, Any], analyst: dict[str, Any]) -> set[str]:
    contract = payload.get("answer_contract") or {}
    allowed: set[str] = set()
    for key in (
        "mitre_technique_ids",
        "evidence_supported_mitre",
        "candidate_mitre",
        "requires_validation_mitre",
        "not_claimed_mitre",
        "ruled_out_mitre",
    ):
        allowed |= {str(item).upper() for item in contract.get(key) or []}
    for item in payload.get("mitre_mappings") or []:
        if isinstance(item, dict) and item.get("technique_id"):
            allowed.add(str(item["technique_id"]).upper())
    for source_key in ("mitre_mappings", "not_claimed"):
        for item in analyst.get(source_key) or []:
            if isinstance(item, dict):
                technique = item.get("Technique") or item.get("technique_id")
                if technique:
                    allowed.add(str(technique).upper())
    return allowed


def _completeness_sections(analyst: dict[str, Any]) -> CheckResult:
    check_id = "completeness_sections"
    render_sections = analyst.get("render_sections") or {}
    for section, enabled in render_sections.items():
        if not enabled:
            continue
        backing = _SECTION_BACKING.get(str(section))
        if backing is None:
            continue
        if not any(_present(analyst.get(field)) for field in backing):
            return CheckResult(
                check_id, False, f"section {section} enabled but no backing content in {backing}"
            )
    return CheckResult(check_id, True, "every enabled section has backing content")


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return True


def _actionability_priorities(payload: dict[str, Any], analyst: dict[str, Any]) -> CheckResult:
    check_id = "actionability_priorities"
    actions = analyst.get("recommended_actions") or []
    if any(not str(item).strip() for item in actions):
        return CheckResult(check_id, False, "recommended_actions contains an empty entry")

    severity_decision = payload.get("severity_decision") or {}
    label = str(
        severity_decision.get("severity_label") if isinstance(severity_decision, dict) else ""
    )
    if label.startswith(("P1", "P2")) and not actions:
        return CheckResult(
            check_id, False, f"severity {label} requires recommended actions but none present"
        )
    return CheckResult(check_id, True, "actions present where severity demands and never empty")


def _honesty_limitations(
    payload: dict[str, Any], analyst: dict[str, Any], prose: str
) -> CheckResult:
    check_id = "honesty_limitations"

    candidate_spl = payload.get("candidate_spl") or {}
    if candidate_spl.get("execution_eligible") is True:
        return CheckResult(check_id, False, "candidate SPL marked execution_eligible=true")

    execution = payload.get("execution") or {}
    executed = str(execution.get("status") or "") == "executed"
    if not executed and claim_patterns.EXECUTED_SPL.search(prose):
        return CheckResult(check_id, False, "prose claims SPL execution but nothing was executed")

    # The non-execution disclosure is owed only when the answer carries an SPL
    # artifact or an execution was attempted/blocked — a pure knowledge or
    # judgment answer implies no execution to disclose.
    draft_preview = analyst.get("spl_draft_preview") or {}
    has_spl_artifact = bool(
        candidate_spl.get("candidate_spl")
        or analyst.get("spl_code")
        or analyst.get("draft_spl_code")
        or draft_preview.get("draft_spl")
    )
    execution_attempted = str(execution.get("status") or "") not in {"", "skipped"}
    if not executed and (has_spl_artifact or execution_attempted):
        disclosed = any(
            _present(value)
            for value in (
                analyst.get("limitations"),
                analyst.get("execution_status_label"),
                analyst.get("review_notice"),
                draft_preview.get("draft_status"),
            )
        )
        if not disclosed:
            return CheckResult(
                check_id,
                False,
                "SPL artifact present but answer discloses no execution status or limitations",
            )
    return CheckResult(check_id, True, "execution claims honest; limitations stated where due")


def _no_forbidden_claims(prose: str, prose_parts: list[str], payload: dict[str, Any]) -> CheckResult:
    check_id = "no_forbidden_claims"
    lowered = prose.lower()

    for marker in claim_patterns.GITHUB_MARKERS:
        if marker in lowered:
            return CheckResult(check_id, False, f"prose contains provenance marker {marker!r}")
    if claim_patterns.APPROVED_EXEC.search(prose):
        return CheckResult(check_id, False, "prose claims SPL is approved for execution")
    # Negation must sit in the same field as the compromise wording — a
    # "candidate only" elsewhere in the answer cannot license the claim.
    for part in prose_parts:
        if claim_patterns.COMPROMISE.search(part) and not claim_patterns.NEGATION.search(part):
            return CheckResult(check_id, False, "prose asserts compromise without negation framing")

    contract = payload.get("answer_contract") or {}
    if not contract.get("evidence_supported_mitre") and re.search(
        r"\bevidence[- ]supported\b", lowered
    ):
        statuses = str(payload.get("mitre_evidence_status") or "")
        if "evidence_supported" not in statuses:
            return CheckResult(
                check_id, False, "prose claims evidence-supported MITRE but contract has none"
            )
    return CheckResult(check_id, True, "no forbidden claims detected")
