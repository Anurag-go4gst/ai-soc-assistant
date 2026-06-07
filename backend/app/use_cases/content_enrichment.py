from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTENT_ENRICHMENT_PATH = Path(__file__).with_name("content_enrichment.json")


@lru_cache(maxsize=1)
def load_content_enrichment() -> dict[str, Any]:
    """Load curated enrichment metadata from the local app bundle only."""
    if not CONTENT_ENRICHMENT_PATH.exists():
        return {"records": {}}
    payload = json.loads(CONTENT_ENRICHMENT_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"records": {}}


def content_enrichment_records() -> dict[str, dict[str, Any]]:
    records = load_content_enrichment().get("records")
    if not isinstance(records, dict):
        return {}
    return {str(key): value for key, value in records.items() if isinstance(value, dict)}


def get_content_enrichment(use_case_id: str | None) -> dict[str, Any] | None:
    if not use_case_id:
        return None
    records = content_enrichment_records()
    if use_case_id in records:
        return dict(records[use_case_id])
    for record in records.values():
        if record.get("use_case_id") == use_case_id or record.get("proposed_use_case_id") == use_case_id:
            return dict(record)
    return None


def enrichment_spl_governance(use_case_id: str | None) -> dict[str, Any] | None:
    record = get_content_enrichment(use_case_id)
    if record is None:
        return None
    status = str(record.get("spl_template_status") or "unavailable")
    allowed_templates = [str(item) for item in record.get("allowed_spl_templates") or []]
    evidence_requirements = [str(item) for item in record.get("evidence_requirements") or []]
    limitations = [str(item) for item in record.get("limitations") or []]
    return {
        "use_case_id": record.get("use_case_id") or record.get("proposed_use_case_id"),
        "use_case_status": record.get("use_case_status"),
        "spl_template_status": status,
        "allowed_spl_templates": allowed_templates,
        "evidence_requirements": evidence_requirements,
        "limitations": limitations,
        "governed_limitation": _spl_limitation(status, allowed_templates),
        "llm_fallback_allowed": False,
    }


def _spl_limitation(status: str, allowed_templates: list[str]) -> str | None:
    if status == "active":
        if allowed_templates:
            return None
        return "active_enrichment_without_allowed_template"
    if status == "planned":
        return "spl_template_planned_no_free_spl_fallback"
    return "spl_template_unavailable_no_free_spl_fallback"
