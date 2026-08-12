"""Routing truth-set schema and its capability-consistency invariant (Plan 4 R1.1).

The 105-question golden set cannot tell a correct route from an incorrect one:
every row matches `exact_105_*` and routes by registry table lookup, its labels
are circular with the understanding table that consumes them, and `spl_status` is
`none` on 113 of 120 frozen answer rows — so a regression that suppressed SPL
across the whole set would still report `120 exact`.

This module defines the schema for an independent, **labels-only** routing
benchmark. It holds no answers and never compares answer text; it is a separate
artifact from the answer goldens and must not be conflated with them.

Two properties make it non-tautological:

1. `acceptable_skills` is a **set**. Many SOC questions have more than one
   legitimate route; requiring a single exact skill would manufacture failures
   and pressure the labeller toward whatever the router already does.
2. Route correctness and capability consistency are **independent verdicts**. A
   row can be `route_ok` and still be `capability_inconsistent` — that is exactly
   the D1 defect class, where the selected skill's contract denies SPL that the
   labelled intent requires.

Capability authority is **not** reimplemented here. The invariant delegates to
`skill_intent_compatibility._contract_grants`, which delegates to
`composer._skill_permits` — one implementation, as Plan 3 B2 established. A second
capability table would be a second authority by another name.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from contracts.skill_enum import SKILL_ENUM

SCHEMA_VERSION = "2026-08-12-routing-truth-set-v1"

#: Row completeness stages. `corpus` rows carry identity only (R1.2 assembles
#: them before any label exists); `labeled` rows carry the full adjudication
#: (R1.3). Validating a corpus file against `labeled` is the check that proves
#: R1.3 actually happened.
STAGE_CORPUS = "corpus"
STAGE_LABELED = "labeled"
STAGES = frozenset({STAGE_CORPUS, STAGE_LABELED})

#: Capabilities a label may reference.
CAPABILITY_RAG = "rag"
CAPABILITY_SPL = "spl"
CAPABILITY_MCP = "mcp"
CAPABILITIES = frozenset({CAPABILITY_RAG, CAPABILITY_SPL, CAPABILITY_MCP})

#: Capabilities the skill capability contract actually reasons about, and
#: therefore the only ones the consistency verdict can gate on. `composer.
#: _PURPOSE_TOOL_HINTS` has keys for `spl` and `mcp` only; there is no RAG permit
#: key. `rag` is still labelled — E0 reports it — but gating on it would require
#: inventing a RAG permit table, i.e. the second capability authority this module
#: exists to avoid. The limit is stated in the contract doc, not worked around.
CONTRACT_GATED_CAPABILITIES = frozenset({CAPABILITY_SPL, CAPABILITY_MCP})

LABEL_CONFIDENCES = frozenset({"high", "med", "low"})

#: Intent families a label may use. Closed set, harvested from the live
#: classifier; `test_routing_truth_set_schema.py` pins every member against
#: `intent_classifier.py` so a label can never name a family the runtime cannot
#: produce, and so a family renamed in the classifier breaks this list loudly.
INTENT_FAMILIES = frozenset(
    {
        "alert_summary",
        "clarification_required",
        "cve_investigation",
        "github_investigation",
        "guided_investigation",
        "hybrid_alert_review",
        "hybrid_investigation_plus_policy",
        "knowledge_only",
        "live_investigation",
        "mitre_explanation",
        "mitre_mapping",
        "policy_knowledge",
        "reference_knowledge",
        "sop_or_playbook",
        "spl_generation_and_run",
        "spl_generation_only",
    }
)

#: Answer shapes a label may use: the router's own `AnswerShape` vocabulary plus
#: `clarification`, which is a legitimate expected outcome (an under-specified
#: ask should be clarified) but is not one of the router's shape literals.
EXTRA_ANSWER_SHAPES = frozenset({"clarification"})

#: Per-row verdicts. Route correctness and capability consistency are orthogonal:
#: a row carries one route verdict and, independently, may be flagged
#: `capability_inconsistent`.
VERDICT_ROUTE_OK = "route_ok"
VERDICT_ROUTE_WRONG = "route_wrong"
VERDICT_CAPABILITY_INCONSISTENT = "capability_inconsistent"

_REQUIRED_CORPUS_FIELDS = ("row_id", "query", "source")
_REQUIRED_LABEL_FIELDS = (
    "expected_intent_family",
    "expected_answer_shape",
    "acceptable_skills",
    "required_capabilities",
    "forbidden_capabilities",
    "ambiguous",
    "label_confidence",
    "rationale",
    "labeled_without_registry_hint",
)


def answer_shapes() -> frozenset[str]:
    """Allowed `expected_answer_shape` values.

    Imported from the router at call time so a change to `AnswerShape` surfaces
    here rather than drifting into a stale copy.
    """
    from typing import get_args

    from app.chat.answer_shape_router import AnswerShape

    return frozenset(get_args(AnswerShape)) | EXTRA_ANSWER_SHAPES


@dataclass(frozen=True)
class RowValidation:
    row_id: str
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _as_str_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if any(not isinstance(item, str) for item in value):
        return None
    return [str(item) for item in value]


def validate_row(row: Mapping[str, Any], *, stage: str = STAGE_LABELED) -> RowValidation:
    """Validate one row. Returns collected errors rather than raising.

    Collecting is deliberate: a malformed corpus should report every problem in
    one pass, so fixing rows is not a game of whack-a-mole against the first
    assertion that happens to fire.
    """
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage!r}")

    row_id = str(row.get("row_id") or "<missing row_id>")
    errors: list[str] = []

    for key in _REQUIRED_CORPUS_FIELDS:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key}: missing or not a non-empty string")

    if stage == STAGE_CORPUS:
        # Corpus rows must not be pre-labelled — a label present before R1.3 is
        # exactly the contamination the staged schema exists to prevent.
        for key in _REQUIRED_LABEL_FIELDS:
            if key in row:
                errors.append(f"{key}: label present at corpus stage (labels belong to R1.3)")
        return RowValidation(row_id=row_id, errors=errors)

    for key in _REQUIRED_LABEL_FIELDS:
        if key not in row:
            errors.append(f"{key}: missing")

    family = row.get("expected_intent_family")
    if family is not None and family not in INTENT_FAMILIES:
        errors.append(f"expected_intent_family: {family!r} not in the closed family set")

    shape = row.get("expected_answer_shape")
    if shape is not None and shape not in answer_shapes():
        errors.append(f"expected_answer_shape: {shape!r} not an allowed answer shape")

    skills = _as_str_list(row.get("acceptable_skills"))
    if skills is None:
        errors.append("acceptable_skills: must be a list of strings")
    else:
        if not skills:
            errors.append("acceptable_skills: must contain at least one skill")
        if len(set(skills)) != len(skills):
            errors.append("acceptable_skills: duplicate entries (it is a set, not a ranking)")
        for skill in skills:
            if skill not in SKILL_ENUM:
                errors.append(f"acceptable_skills: {skill!r} is not a routable skill")

    for key in ("required_capabilities", "forbidden_capabilities"):
        caps = _as_str_list(row.get(key))
        if caps is None:
            errors.append(f"{key}: must be a list of strings")
            continue
        if len(set(caps)) != len(caps):
            errors.append(f"{key}: duplicate entries")
        for cap in caps:
            if cap not in CAPABILITIES:
                errors.append(f"{key}: {cap!r} not in {sorted(CAPABILITIES)}")

    required = set(_as_str_list(row.get("required_capabilities")) or [])
    forbidden = set(_as_str_list(row.get("forbidden_capabilities")) or [])
    overlap = required & forbidden
    if overlap:
        errors.append(f"capability sets contradict each other on {sorted(overlap)}")

    if not isinstance(row.get("ambiguous"), bool):
        errors.append("ambiguous: must be a bool")

    confidence = row.get("label_confidence")
    if confidence not in LABEL_CONFIDENCES:
        errors.append(f"label_confidence: {confidence!r} not in {sorted(LABEL_CONFIDENCES)}")

    rationale = row.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        errors.append("rationale: missing or empty (every label must say why)")

    if row.get("labeled_without_registry_hint") is not True:
        errors.append(
            "labeled_without_registry_hint: must be true — a label derived from "
            "legacy_router_intent_hint or an observed route is not independent evidence"
        )

    if row.get("ambiguous") is True:
        readings = row.get("candidate_readings")
        parsed = _as_str_list(readings)
        if parsed is None or len(parsed) < 2:
            errors.append(
                "candidate_readings: an ambiguous row must record at least two competing readings"
            )

    return RowValidation(row_id=row_id, errors=errors)


def validate_rows(rows: Iterable[Mapping[str, Any]], *, stage: str = STAGE_LABELED) -> list[RowValidation]:
    results = [validate_row(row, stage=stage) for row in rows]
    seen: dict[str, int] = {}
    for result in results:
        seen[result.row_id] = seen.get(result.row_id, 0) + 1
    duplicates = sorted(row_id for row_id, count in seen.items() if count > 1)
    if duplicates:
        results.append(RowValidation(row_id="<corpus>", errors=[f"duplicate row_id: {duplicates}"]))
    return results


def load_truth_set(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise ValueError(f"{path}: expected an object with a 'rows' list")
    return payload


def file_sha256(path: str | Path) -> str:
    """SHA256 of the label file, for R1.3's order commitment.

    The labels are committed and hashed *before* the evaluator runs, so a later
    silent edit that makes the numbers look better is detectable.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capability_consistency(
    *,
    selected_skill: str | None,
    required_capabilities: Iterable[str],
) -> tuple[bool, frozenset[str]]:
    """Evaluate the capability-consistency invariant for one row.

    Returns `(consistent, denied)`. A row is inconsistent when the selected
    skill's capability contract denies a capability the row's **label** marks
    required — independent of whether the route itself is acceptable, and
    independent of whether the final answer would still match an answer golden.

    Only `CONTRACT_GATED_CAPABILITIES` participate; see that constant for why RAG
    does not. Capability lookup delegates to the composer's permit logic through
    `skill_intent_compatibility._contract_grants` — this function owns the
    invariant, not the capability table.
    """
    from app.chat.skill_intent_compatibility import _contract_grants, skill_contract_for

    required = {str(item) for item in required_capabilities} & CONTRACT_GATED_CAPABILITIES
    if not required:
        return True, frozenset()

    contract = skill_contract_for(selected_skill)
    denied = frozenset(cap for cap in required if not _contract_grants(contract, cap))
    return (not denied), denied
