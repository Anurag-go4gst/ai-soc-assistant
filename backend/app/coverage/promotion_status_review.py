"""Operator-reviewed promotion_status writes for the catalogue runtime map.

Runtime classifiers read ``promotion_status`` only. Persistent updates happen
exclusively through this reviewed path — never from /chat, LLM output, or
automatic runtime demotion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.coverage.promotion_lifecycle import promotion_gate_decision
from app.coverage.row_authority import UNSUPPORTED, classify_runtime_row_authority, project_s3_authority_ready
from app.use_cases.answer_packs import reviewed_answer_pack

DEFAULT_RUNTIME_MAP_PATH = (
    Path(__file__).resolve().parent / "question_runtime_map_v1.json"
)
DEFAULT_AUDIT_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "evals" / "out" / "promotion_status_audit.jsonl"
)

PromotionAction = Literal["promote", "demote"]
VALID_STORED_STATUSES = frozenset({"in_manifest", "not_in_manifest"})


@dataclass
class ReviewedPromotionEvidence:
    operator_id: str
    review_ticket: str
    pack_id: str | None = None
    golden_passed: bool = False
    golden_run_ref: str | None = None
    reviewed_reason: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromotionStatusWriteRequest:
    action: PromotionAction
    question_ref: str
    row_revision: str
    reviewed_evidence: ReviewedPromotionEvidence
    dry_run: bool = True
    runtime_map_path: Path | None = None
    audit_path: Path | None = None

    def model_dump(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reviewed_evidence"] = self.reviewed_evidence.model_dump()
        if self.runtime_map_path is not None:
            payload["runtime_map_path"] = str(self.runtime_map_path)
        if self.audit_path is not None:
            payload["audit_path"] = str(self.audit_path)
        return payload


@dataclass
class PromotionStatusWriteResult:
    allowed: bool
    applied: bool
    dry_run: bool
    action: PromotionAction
    question_ref: str
    before_status: str | None = None
    after_status: str | None = None
    row_revision_expected: str | None = None
    row_revision_actual: str | None = None
    blockers: list[str] = field(default_factory=list)
    gate_summary: dict[str, Any] = field(default_factory=dict)
    audit_record_id: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def compute_row_revision(entry: dict[str, Any]) -> str:
    """Stable fingerprint for stale-row rejection."""
    payload = {
        "question_ref": entry.get("question_ref"),
        "promotion_status": entry.get("promotion_status"),
        "manifest_coverage_id": entry.get("manifest_coverage_id"),
        "s3_authority_ready": entry.get("s3_authority_ready"),
        "proposed_primary_skill": entry.get("proposed_primary_skill"),
        "route_blocked": entry.get("route_blocked"),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def evaluate_promotion_status_write(request: PromotionStatusWriteRequest) -> PromotionStatusWriteResult:
    """Evaluate a promotion/demotion write without mutating the runtime map."""
    map_path = request.runtime_map_path or DEFAULT_RUNTIME_MAP_PATH
    runtime_map = _load_runtime_map(map_path)
    entry, index = _find_entry(runtime_map, request.question_ref)
    if entry is None or index is None:
        return PromotionStatusWriteResult(
            allowed=False,
            applied=False,
            dry_run=request.dry_run,
            action=request.action,
            question_ref=request.question_ref,
            blockers=["stale_or_missing_row_id"],
        )

    before_status = str(entry.get("promotion_status") or "")
    actual_revision = compute_row_revision(entry)
    blockers: list[str] = []
    if request.row_revision != actual_revision:
        blockers.append("stale_row_revision")

    evidence = request.reviewed_evidence
    if not str(evidence.operator_id or "").strip():
        blockers.append("operator_id_required")
    if not str(evidence.review_ticket or "").strip():
        blockers.append("review_ticket_required")

    manifest_index = _manifest_index()
    manifest_entry = manifest_index.get(str(entry.get("manifest_coverage_id") or ""))
    row_status, row_blockers = classify_runtime_row_authority(entry, manifest_entry)
    s3_ready = project_s3_authority_ready(row_status)

    if request.action == "promote":
        target_status = "in_manifest"
        pack = reviewed_answer_pack(case_id=request.question_ref, use_case_id=evidence.pack_id)
        if pack is None:
            blockers.append("reviewed_answer_pack_required")
        if not evidence.golden_passed:
            blockers.append("golden_test_required")
        if not str(evidence.golden_run_ref or "").strip():
            blockers.append("golden_run_ref_required")
        if entry.get("route_blocked") is True:
            blockers.append("route_blocked")
        if row_status == UNSUPPORTED:
            blockers.append("unsafe_row_authority_unsupported")
        if before_status == target_status:
            blockers.append("already_in_target_status")
        gate = promotion_gate_decision(
            stored_promotion_status=before_status,
            reviewed_pack_loaded=pack is not None,
            golden_passed=evidence.golden_passed,
            s3_authority_ready=s3_ready,
        )
        blockers.extend(item for item in gate["blockers"] if item not in blockers)
        gate_summary = gate
    else:
        target_status = "not_in_manifest"
        gate_summary = {}
        reason = str(evidence.reviewed_reason or "").strip()
        if not reason:
            blockers.append("reviewed_demotion_reason_required")
        if before_status == target_status:
            blockers.append("already_in_target_status")
        if entry.get("authority_pilot_candidate") is True and before_status == "in_manifest":
            blockers.append("authority_pilot_demotion_requires_coe_signoff")
        if row_blockers and entry.get("route_blocked") is not True:
            unsafe = [item for item in row_blockers if item.startswith("manifest_readiness:")]
            if unsafe and before_status == "in_manifest":
                blockers.append("unsafe_dependency_state")

    allowed = not blockers
    return PromotionStatusWriteResult(
        allowed=allowed,
        applied=False,
        dry_run=request.dry_run,
        action=request.action,
        question_ref=request.question_ref,
        before_status=before_status,
        after_status=target_status if allowed else before_status,
        row_revision_expected=request.row_revision,
        row_revision_actual=actual_revision,
        blockers=blockers,
        gate_summary=gate_summary,
    )


def apply_promotion_status_write(request: PromotionStatusWriteRequest) -> PromotionStatusWriteResult:
    """Apply a reviewed promotion_status write when all gates pass."""
    evaluation = evaluate_promotion_status_write(request)
    if not evaluation.allowed:
        return evaluation

    if request.dry_run:
        evaluation.applied = False
        return evaluation

    map_path = request.runtime_map_path or DEFAULT_RUNTIME_MAP_PATH
    runtime_map = _load_runtime_map(map_path)
    entry, index = _find_entry(runtime_map, request.question_ref)
    if entry is None or index is None:
        evaluation.allowed = False
        evaluation.blockers = ["stale_or_missing_row_id"]
        return evaluation

    if compute_row_revision(entry) != request.row_revision:
        evaluation.allowed = False
        evaluation.blockers = ["stale_row_revision"]
        return evaluation

    target_status = "in_manifest" if request.action == "promote" else "not_in_manifest"
    before_status = str(entry.get("promotion_status") or "")
    updated_entry = dict(entry)
    updated_entry["promotion_status"] = target_status
    runtime_map["entries"][index] = updated_entry
    _write_runtime_map(map_path, runtime_map)

    audit_record = _build_audit_record(request, before_status=before_status, after_status=target_status)
    audit_path = request.audit_path or DEFAULT_AUDIT_PATH
    _append_audit_record(audit_path, audit_record)

    evaluation.applied = True
    evaluation.before_status = before_status
    evaluation.after_status = target_status
    evaluation.audit_record_id = audit_record["audit_id"]
    return evaluation


def _build_audit_record(
    request: PromotionStatusWriteRequest,
    *,
    before_status: str,
    after_status: str,
) -> dict[str, Any]:
    evidence = request.reviewed_evidence
    audit_id = hashlib.sha256(
        json.dumps(
            {
                "question_ref": request.question_ref,
                "action": request.action,
                "before": before_status,
                "after": after_status,
                "operator_id": evidence.operator_id,
                "review_ticket": evidence.review_ticket,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:20]
    return {
        "audit_id": audit_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": request.action,
        "question_ref": request.question_ref,
        "before_promotion_status": before_status,
        "after_promotion_status": after_status,
        "operator_id": evidence.operator_id,
        "review_ticket": evidence.review_ticket,
        "pack_id": evidence.pack_id,
        "golden_passed": evidence.golden_passed,
        "golden_run_ref": evidence.golden_run_ref,
        "reviewed_reason": evidence.reviewed_reason,
        "authority_of_record": "catalogue_runtime_map",
        "runtime_classifier_mutated": False,
        "llm_authority": False,
    }


def _load_runtime_map(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_runtime_map(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _find_entry(runtime_map: dict[str, Any], question_ref: str) -> tuple[dict[str, Any] | None, int | None]:
    ref = question_ref.strip().lower()
    entries = runtime_map.get("entries")
    if not isinstance(entries, list):
        return None, None
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("question_ref") or "").lower() == ref:
            return entry, index
    return None, None


def _manifest_index() -> dict[str, dict[str, Any]]:
    manifest_path = Path(__file__).resolve().parent / "pattern_coverage_v1.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        coverage_id = entry.get("coverage_id")
        if isinstance(coverage_id, str) and coverage_id:
            index[coverage_id] = entry
    return index


def _append_audit_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
