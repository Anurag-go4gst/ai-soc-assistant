"""Load and normalize MITRE registry metadata from enrichment drafts (metadata only)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.threat.mitre_registry_schema import (
    MITRE_REGISTRY_SCHEMA_VERSION,
    MitreRegistryMetadata,
    MitreVisibilityPolicy,
)
from app.use_cases.content_enrichment import (
    get_content_enrichment,
    runtime_enrichment_activation_allowed,
)

def _find_repo_root() -> Path:
    """Resolve the repo root in both the host checkout and the container.

    `parents[3]` is correct on the host (.../backend/app/threat/file -> repo) but
    resolves to "/" inside the container, where the backend is mounted at /app
    and the full repo is mounted read-only at /workspace. Search upward for the
    enrichment data dir, then fall back to /workspace, then to parents[3].
    """
    here = Path(__file__).resolve()
    for base in (*here.parents, Path("/workspace")):
        if (base / "docs/input/mitre_enrichment").is_dir():
            return base
    return here.parents[3]


_REPO_ROOT = _find_repo_root()
_QUESTION_DRAFT_PATH = (
    _REPO_ROOT / "docs/input/mitre_enrichment/question_105_for_mitre_enrichment.DRAFT.json"
)
_USE_CASE_DRAFT_PATH = (
    _REPO_ROOT / "docs/input/mitre_enrichment/use_case_42_for_mitre_enrichment.DRAFT.json"
)
_ATTACK_SUBSET_PATH = Path(__file__).resolve().parent / "mitre_attack_subset.json"
_RUNTIME_QUESTION_MAP_PATH = _REPO_ROOT / "backend/app/coverage/question_runtime_map_v1.json"
_RUNTIME_CATALOG_PATH = _REPO_ROOT / "backend/app/use_cases/catalog.json"


def _upper_id_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not item:
            continue
        upper = str(item).strip().upper()
        if upper and upper not in seen:
            seen.add(upper)
            out.append(upper)
    return out


@lru_cache(maxsize=1)
def load_mitre_attack_subset_technique_ids() -> frozenset[str]:
    payload = json.loads(_ATTACK_SUBSET_PATH.read_text(encoding="utf-8"))
    techniques = payload.get("techniques") if isinstance(payload, dict) else []
    ids: set[str] = set()
    if isinstance(techniques, list):
        for row in techniques:
            if isinstance(row, dict) and row.get("technique_id"):
                ids.add(str(row["technique_id"]).upper())
    return frozenset(ids)


def map_draft_visibility_to_policy(registry_block: dict[str, Any]) -> MitreVisibilityPolicy:
    """Map draft visibility fields to normalized MitreVisibilityPolicy."""
    raw_policy = str(
        registry_block.get("answer_visibility_policy")
        or registry_block.get("default_visibility")
        or ""
    ).lower()
    if "do_not_show_unless_user_asks" in raw_policy or raw_policy == "answer_if_requested":
        return MitreVisibilityPolicy.answer_if_requested
    if "answer_if_requested_or_supported" in raw_policy or raw_policy == "answer_if_supported":
        return MitreVisibilityPolicy.answer_if_supported
    if raw_policy == "trace_only":
        return MitreVisibilityPolicy.trace_only
    return MitreVisibilityPolicy.trace_only


def normalize_legacy_mitre_fields(
    item: dict[str, Any],
    *,
    question_ref: str | None = None,
    use_case_id: str | None = None,
) -> MitreRegistryMetadata:
    """Build MitreRegistryMetadata from a draft item (merge: registry block, legacy, KB overlap)."""
    registry_block = item.get("mitre_registry")
    registry_block = dict(registry_block) if isinstance(registry_block, dict) else {}

    permitted: list[str] = []
    candidate: list[str] = []
    blocked: list[str] = []

    permitted.extend(_upper_id_list(registry_block.get("permitted") or registry_block.get("mitre_permitted")))
    candidate.extend(_upper_id_list(registry_block.get("candidate") or registry_block.get("mitre_candidate")))
    blocked.extend(_upper_id_list(registry_block.get("blocked") or registry_block.get("mitre_blocked")))

    permitted.extend(_upper_id_list(item.get("mitre_permitted")))
    candidate.extend(_upper_id_list(item.get("mitre_candidates")))

    kb_refs = item.get("kb_references")
    if isinstance(kb_refs, dict):
        candidate.extend(_upper_id_list(kb_refs.get("mitre_runtime_kb_overlap")))

    requires_evidence = registry_block.get("requires_evidence")
    if requires_evidence is None:
        requires_evidence = True
    else:
        requires_evidence = bool(requires_evidence)

    requires_alert_context = bool(registry_block.get("requires_alert_context", False))
    visibility = map_draft_visibility_to_policy(registry_block)
    rationale = registry_block.get("mapping_rationale")
    rationale = rationale.strip() if isinstance(rationale, str) and rationale.strip() else None

    def _dedupe(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for tid in seq:
            if tid not in seen:
                seen.add(tid)
                out.append(tid)
        return out

    permitted = _dedupe(permitted)
    candidate = _dedupe([t for t in candidate if t not in set(permitted)])
    blocked = _dedupe(blocked)

    return MitreRegistryMetadata(
        schema_version=MITRE_REGISTRY_SCHEMA_VERSION,
        registry_role="metadata_not_evidence",
        mitre_permitted=permitted,
        mitre_candidate=candidate,
        mitre_blocked=blocked,
        mitre_requires_evidence=requires_evidence,
        mitre_requires_alert_context=requires_alert_context,
        mitre_visibility_policy=visibility,
        source_question_ref=question_ref,
        source_use_case_id=use_case_id,
        mapping_rationale=rationale,
    )


@lru_cache(maxsize=1)
def load_mitre_enrichment_drafts() -> dict[str, Any]:
    """Load 105-question and 42-use-case MITRE enrichment draft exports."""
    questions = json.loads(_QUESTION_DRAFT_PATH.read_text(encoding="utf-8"))
    use_cases = json.loads(_USE_CASE_DRAFT_PATH.read_text(encoding="utf-8"))
    q_items = questions.get("items") if isinstance(questions, dict) else []
    u_items = use_cases.get("items") if isinstance(use_cases, dict) else []
    if not isinstance(q_items, list) or not isinstance(u_items, list):
        raise ValueError("MITRE enrichment drafts must contain items[] arrays")
    q_by_id = {str(row["id"]): row for row in q_items if isinstance(row, dict) and row.get("id")}
    u_by_id = {str(row["id"]): row for row in u_items if isinstance(row, dict) and row.get("id")}
    return {
        "questions": questions,
        "use_cases": use_cases,
        "questions_by_id": q_by_id,
        "use_cases_by_id": u_by_id,
        "question_count": len(q_by_id),
        "use_case_count": len(u_by_id),
    }


def clear_mitre_enrichment_cache() -> None:
    load_mitre_enrichment_drafts.cache_clear()
    load_mitre_attack_subset_technique_ids.cache_clear()
    _load_runtime_question_entries_by_ref.cache_clear()
    _load_runtime_use_case_entries_by_id.cache_clear()


@lru_cache(maxsize=1)
def _load_runtime_question_entries_by_ref() -> dict[str, dict[str, Any]]:
    if not _RUNTIME_QUESTION_MAP_PATH.is_file():
        return {}
    payload = json.loads(_RUNTIME_QUESTION_MAP_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return {}
    return {
        str(row["question_ref"]): row
        for row in entries
        if isinstance(row, dict) and row.get("question_ref")
    }


@lru_cache(maxsize=1)
def _load_runtime_use_case_entries_by_id() -> dict[str, dict[str, Any]]:
    if not _RUNTIME_CATALOG_PATH.is_file():
        return {}
    payload = json.loads(_RUNTIME_CATALOG_PATH.read_text(encoding="utf-8"))
    use_cases = payload.get("use_cases") if isinstance(payload, dict) else []
    if not isinstance(use_cases, list):
        return {}
    return {
        str(row["use_case_id"]): row
        for row in use_cases
        if isinstance(row, dict) and row.get("use_case_id")
    }


def _synthetic_draft_item_from_runtime_row(row: dict[str, Any]) -> dict[str, Any]:
    """Build a draft-shaped dict so normalize_legacy_mitre_fields can read runtime JSON."""
    kb_overlap = row.get("mitre_runtime_kb_overlap")
    kb_refs: dict[str, Any] | None = None
    if isinstance(kb_overlap, list) and kb_overlap:
        kb_refs = {"mitre_runtime_kb_overlap": kb_overlap}
    candidates = row.get("mitre_candidates")
    if candidates is None:
        candidates = row.get("mitre_candidate")
    return {
        "mitre_registry": row.get("mitre_registry"),
        "mitre_permitted": row.get("mitre_permitted"),
        "mitre_candidates": candidates,
        "kb_references": kb_refs,
    }


def registry_mitre_metadata(
    *,
    question_ref: str | None = None,
    use_case_id: str | None = None,
) -> MitreRegistryMetadata | None:
    """Resolve normalized MITRE registry metadata for a 105 question_ref or 42 use_case_id."""
    if not question_ref and not use_case_id:
        return None
    if question_ref:
        runtime_row = _load_runtime_question_entries_by_ref().get(question_ref)
        if isinstance(runtime_row, dict) and isinstance(runtime_row.get("mitre_registry"), dict):
            item = _synthetic_draft_item_from_runtime_row(runtime_row)
            return normalize_legacy_mitre_fields(item, question_ref=question_ref, use_case_id=None)
    if use_case_id:
        runtime_row = _load_runtime_use_case_entries_by_id().get(use_case_id)
        if isinstance(runtime_row, dict) and isinstance(runtime_row.get("mitre_registry"), dict):
            item = _synthetic_draft_item_from_runtime_row(runtime_row)
            meta = normalize_legacy_mitre_fields(item, question_ref=None, use_case_id=use_case_id)
            return _merge_enrichment_mitre_candidates(meta, use_case_id)
        enrichment = get_content_enrichment(use_case_id)
        if isinstance(enrichment, dict):
            item = {
                "mitre_registry": {
                    "candidate": enrichment.get("mitre_candidates") or [],
                    "requires_evidence": True,
                    "requires_alert_context": False,
                    "answer_visibility_policy": "answer_if_requested",
                    "mapping_rationale": "Batch 3 pilot enrichment metadata; not observed evidence.",
                },
                "mitre_candidates": enrichment.get("mitre_candidates") or [],
            }
            return normalize_legacy_mitre_fields(item, question_ref=None, use_case_id=use_case_id)
    drafts = load_mitre_enrichment_drafts()
    if question_ref:
        item = drafts["questions_by_id"].get(question_ref)
        if isinstance(item, dict):
            return normalize_legacy_mitre_fields(item, question_ref=question_ref, use_case_id=None)
    if use_case_id:
        item = drafts["use_cases_by_id"].get(use_case_id)
        if isinstance(item, dict):
            return normalize_legacy_mitre_fields(item, question_ref=None, use_case_id=use_case_id)
    return None


def registry_mitre_metadata_for_runtime(
    *,
    question_ref: str | None = None,
    use_case_id: str | None = None,
) -> MitreRegistryMetadata | None:
    """Runtime-safe MITRE registry lookup.

    Authoritative runtime knowledge rows and drafts remain available. Enrichment-json
    fallback and enrichment merges require governed runtime activation.
    """
    if question_ref:
        runtime_row = _load_runtime_question_entries_by_ref().get(question_ref)
        if isinstance(runtime_row, dict) and isinstance(runtime_row.get("mitre_registry"), dict):
            item = _synthetic_draft_item_from_runtime_row(runtime_row)
            return normalize_legacy_mitre_fields(item, question_ref=question_ref, use_case_id=None)

    if use_case_id:
        runtime_row = _load_runtime_use_case_entries_by_id().get(use_case_id)
        if isinstance(runtime_row, dict) and isinstance(runtime_row.get("mitre_registry"), dict):
            item = _synthetic_draft_item_from_runtime_row(runtime_row)
            meta = normalize_legacy_mitre_fields(item, question_ref=None, use_case_id=use_case_id)
            if runtime_enrichment_activation_allowed(use_case_id):
                return _merge_enrichment_mitre_candidates(meta, use_case_id)
            return meta

        if runtime_enrichment_activation_allowed(use_case_id):
            return registry_mitre_metadata(question_ref=question_ref, use_case_id=use_case_id)

        drafts = load_mitre_enrichment_drafts()
        item = drafts["use_cases_by_id"].get(use_case_id)
        if isinstance(item, dict):
            return normalize_legacy_mitre_fields(item, question_ref=None, use_case_id=use_case_id)
        return None

    if question_ref:
        drafts = load_mitre_enrichment_drafts()
        item = drafts["questions_by_id"].get(question_ref)
        if isinstance(item, dict):
            return normalize_legacy_mitre_fields(item, question_ref=question_ref, use_case_id=None)
    return None


def _merge_enrichment_mitre_candidates(
    meta: MitreRegistryMetadata,
    use_case_id: str,
) -> MitreRegistryMetadata:
    enrichment = get_content_enrichment(use_case_id)
    if not isinstance(enrichment, dict):
        return meta
    blocked = set(meta.mitre_blocked)
    existing = set(meta.mitre_permitted) | set(meta.mitre_candidate) | blocked
    additions = [
        tid
        for tid in _upper_id_list(enrichment.get("mitre_candidates"))
        if tid not in existing and tid not in blocked
    ]
    if not additions:
        return meta
    return meta.model_copy(update={"mitre_candidate": [*meta.mitre_candidate, *additions]})


def iter_all_question_mitre_metadata() -> list[MitreRegistryMetadata]:
    drafts = load_mitre_enrichment_drafts()
    return [
        normalize_legacy_mitre_fields(item, question_ref=question_ref, use_case_id=None)
        for question_ref, item in sorted(drafts["questions_by_id"].items())
        if isinstance(item, dict)
    ]


def iter_all_use_case_mitre_metadata() -> list[MitreRegistryMetadata]:
    drafts = load_mitre_enrichment_drafts()
    return [
        normalize_legacy_mitre_fields(item, question_ref=None, use_case_id=use_case_id)
        for use_case_id, item in sorted(drafts["use_cases_by_id"].items())
        if isinstance(item, dict)
    ]


def is_policy_or_sop_row(item: dict[str, Any]) -> bool:
    """Heuristic: knowledge/SOP/playbook/policy rows (for audit visibility checks)."""
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    tag_text = " ".join(str(t) for t in tags).lower()
    text = " ".join(
        [
            str(item.get("question_text") or ""),
            str(item.get("use_case_name") or ""),
            str(item.get("description") or ""),
            tag_text,
        ]
    ).lower()
    patterns = item.get("patterns_keywords")
    if isinstance(patterns, dict):
        intent_patterns = patterns.get("intent_patterns")
        if isinstance(intent_patterns, list):
            text += " " + " ".join(str(p) for p in intent_patterns).lower()
    markers = ("sop", "playbook", "runbook", "policy", "escalation", "sop_response")
    return any(marker in text for marker in markers)


def is_failed_login_only_row(item: dict[str, Any]) -> bool:
    """Failed-login investigation without success-after-failure context."""
    row_id = str(item.get("id") or "").lower()
    if row_id == "auth_success_after_failure":
        return False
    text = " ".join(
        [
            str(item.get("question_text") or ""),
            str(item.get("use_case_name") or ""),
            str(item.get("description") or ""),
        ]
    ).lower()
    if "successful login" in text and ("after" in text or "following" in text):
        return False
    if "success after" in text:
        return False
    failed_markers = (
        "failed login",
        "failed logins",
        "failed-login",
        "brute force",
        "password guessing",
        "excessive failed",
    )
    return any(marker in text for marker in failed_markers)


def allows_success_identity_evidence_context(item: dict[str, Any]) -> bool:
    """Row covers success-after-failure or valid-account abuse with evidence context."""
    row_id = str(item.get("id") or "").lower()
    if row_id == "auth_success_after_failure":
        return True
    text = " ".join(
        [
            str(item.get("question_text") or ""),
            str(item.get("use_case_name") or ""),
            str(item.get("description") or ""),
        ]
    ).lower()
    return ("successful login" in text and "after" in text) or "valid account" in text
