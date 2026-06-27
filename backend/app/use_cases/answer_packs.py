from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ANSWER_PACKS_PATH = Path(__file__).with_name("answer_packs.json")
REVIEWED_STATUSES = frozenset({"reviewed", "approved", "runtime_reviewed"})


@lru_cache(maxsize=1)
def load_answer_packs() -> dict[str, dict[str, Any]]:
    """Load derived answer-pack projections.

    Answer packs are read-only runtime projections. They may enrich EvidencePlan
    only after review; raw LLM prose and draft packs are ignored by callers.
    """
    if not ANSWER_PACKS_PATH.exists():
        return {}
    try:
        payload = json.loads(ANSWER_PACKS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    rows = payload.get("packs") if isinstance(payload, dict) else None
    if isinstance(rows, dict):
        return {str(key): value for key, value in rows.items() if isinstance(value, dict)}
    if isinstance(rows, list):
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            pack_id = str(row.get("case_id") or row.get("use_case_id") or "").strip()
            if pack_id:
                result[pack_id] = row
        return result
    return {}


def reviewed_answer_pack(*, case_id: str | None = None, use_case_id: str | None = None) -> dict[str, Any] | None:
    packs = load_answer_packs()
    for key in (case_id, use_case_id):
        if not key:
            continue
        pack = packs.get(str(key))
        if pack and _reviewed(pack):
            return _runtime_projection(pack)
    return None


def answer_pack_summary(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": str(pack.get("case_id") or pack.get("use_case_id") or ""),
        "review_status": str(pack.get("review_status") or ""),
        "provenance": str(pack.get("provenance") or ""),
        "raw_llm_prose_loaded": False,
        "runtime_authority": "evidence_plan_enrichment_only",
        "mitre_candidate_status": "candidate_only" if pack.get("mitre_candidates") else None,
        "spl_family_suggestion_loaded": bool(pack.get("spl_family_suggestion")),
    }


def _reviewed(pack: dict[str, Any]) -> bool:
    return str(pack.get("review_status") or "").strip().lower() in REVIEWED_STATUSES


def _runtime_projection(pack: dict[str, Any]) -> dict[str, Any]:
    """Return reviewed EvidencePlan-only fields; never raw prose or authority."""
    allowed_keys = {
        "case_id",
        "use_case_id",
        "review_status",
        "provenance",
        "required_evidence",
        "optional_evidence",
        "source_needs",
        "caveats",
        "must_not_claim",
        "mitre_candidates",
        "dependency_gaps",
        "spl_family_suggestion",
        "spl_template_id",
        "spl_validator_id",
    }
    projected = {key: value for key, value in pack.items() if key in allowed_keys}
    if projected.get("spl_family_suggestion") and not _spl_family_suggestion_allowed(projected):
        projected.pop("spl_family_suggestion", None)
    return projected


def _spl_family_suggestion_allowed(pack: dict[str, Any]) -> bool:
    return bool(str(pack.get("spl_template_id") or "").strip()) or bool(
        str(pack.get("spl_validator_id") or "").strip()
    )
