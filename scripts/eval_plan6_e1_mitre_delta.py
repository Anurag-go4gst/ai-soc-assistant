#!/usr/bin/env python3
"""Offline Plan 6 E1 measurement. Mutates in-memory copies only; never writes artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch as mock_patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tools/coverage_authoring"))

from app.threat.mitre_decision import resolve_mitre_decision  # noqa: E402
import app.threat.mitre_registry_enrichment as mre  # noqa: E402
from app.threat.mitre_registry_enrichment import (  # noqa: E402
    load_mitre_enrichment_drafts,
    registry_mitre_metadata_for_runtime,
)
from app.threat.mitre_runtime_promotion import runtime_patch_for_draft_item  # noqa: E402

ELEVEN = [
    "q0.q021",
    "q0.q028",
    "q0.q040",
    "q0.q046",
    "q0.q047",
    "q0.q050",
    "q0.q060",
    "q0.q062",
    "q0.q063",
    "q0.q083",
    "q0.q089",
]
RUNTIME = REPO / "backend/app/coverage/question_runtime_map_v1.json"
CATALOG = REPO / "backend/app/use_cases/catalog.json"
LEDGER = REPO / "docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json"
OUT_JSON = REPO / "docs/evals/plan6/mitre_11row_promotion_delta.json"

META_FIELDS = (
    "mitre_candidate",
    "mitre_permitted",
    "mitre_blocked",
    "mitre_visibility_policy",
    "mitre_requires_evidence",
    "mitre_requires_alert_context",
    "mapping_rationale",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump_meta(meta) -> dict:
    if meta is None:
        return {"_missing": True}
    return {
        field: getattr(meta, field).value if field == "mitre_visibility_policy" else getattr(meta, field)
        for field in META_FIELDS
    }


def decision_snapshot(meta, **kwargs) -> dict:
    decision = resolve_mitre_decision(
        question_ref=kwargs.get("question_ref"),
        use_case_id=None,
        source_refs=[],
        intent_classification=kwargs.get("intent_classification") or {},
        evidence_plan=kwargs.get("evidence_plan") or {},
        registry_metadata=meta,
        alert_context_present=bool(kwargs.get("alert_context_present")),
        negative_evidence=None,
        source_evidence=kwargs.get("source_evidence"),
        explicit_mitre_request=bool(kwargs.get("explicit_mitre_request")),
    )
    technique_ids = [
        str(item.get("technique_id") or item.get("id") or "")
        for item in decision.techniques
        if isinstance(item, dict)
    ]
    return {
        "mitre_status": decision.mitre_status,
        "technique_ids": [tid for tid in technique_ids if tid],
        "registry_candidates": list(decision.registry_candidates),
        "not_claimed": list(decision.not_claimed),
        "answer_visible": decision.answer_visible,
        "reason": decision.reason,
    }


def main() -> None:
    before_runtime = sha256(RUNTIME)
    before_catalog = sha256(CATALOG)
    before_ledger = sha256(LEDGER)

    payload = json.loads(RUNTIME.read_text(encoding="utf-8"))
    rows = {str(e["question_ref"]): e for e in payload["entries"]}
    drafts = load_mitre_enrichment_drafts()
    q_drafts = drafts["questions_by_id"]
    u_drafts = drafts["use_cases_by_id"]

    promoted_rows = {ref: copy.deepcopy(row) for ref, row in rows.items()}
    patch_changed: list[str] = []
    for ref, draft_item in q_drafts.items():
        if ref not in promoted_rows:
            continue
        patch = runtime_patch_for_draft_item(draft_item, question_ref=ref, use_case_id=None)
        before = {k: promoted_rows[ref].get(k) for k in patch}
        promoted_rows[ref].update(patch)
        after = {k: promoted_rows[ref].get(k) for k in patch}
        if before != after:
            patch_changed.append(ref)

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    use_cases = {
        str(row["use_case_id"]): row
        for row in catalog.get("use_cases", [])
        if isinstance(row, dict) and row.get("use_case_id")
    }
    catalog_changed: list[str] = []
    for uid, draft_item in u_drafts.items():
        row = use_cases.get(uid)
        if row is None:
            continue
        patch = runtime_patch_for_draft_item(draft_item, question_ref=None, use_case_id=uid)
        before = {k: row.get(k) for k in patch}
        trial = copy.deepcopy(row)
        trial.update(patch)
        after = {k: trial.get(k) for k in patch}
        if before != after:
            catalog_changed.append(uid)

    with mock_patch.object(mre, "_load_runtime_question_entries_by_ref", lambda: rows):
        committed_meta = {ref: registry_mitre_metadata_for_runtime(question_ref=ref) for ref in ELEVEN}
    with mock_patch.object(mre, "_load_runtime_question_entries_by_ref", lambda: promoted_rows):
        promoted_meta = {ref: registry_mitre_metadata_for_runtime(question_ref=ref) for ref in ELEVEN}

    postures = {
        "no_intent": {
            "intent_classification": {},
            "evidence_plan": {},
            "explicit_mitre_request": False,
            "alert_context_present": False,
        },
        "explicit_mitre_no_alert": {
            "intent_classification": {
                "intent_family": "attack_discovery",
                "answer_goal": ["mitre_mapping"],
            },
            "evidence_plan": {"answer_mode": "hybrid"},
            "explicit_mitre_request": True,
            "alert_context_present": False,
        },
        "explicit_mitre_with_alert": {
            "intent_classification": {
                "intent_family": "attack_discovery",
                "answer_goal": ["mitre_mapping"],
            },
            "evidence_plan": {"answer_mode": "hybrid"},
            "explicit_mitre_request": True,
            "alert_context_present": True,
        },
        "knowledge_rag_only": {
            "intent_classification": {"intent_family": "knowledge_recall"},
            "evidence_plan": {"answer_mode": "rag_only"},
            "explicit_mitre_request": False,
            "alert_context_present": False,
        },
        "live_investigation_no_explicit": {
            "intent_classification": {"intent_family": "live_investigation"},
            "evidence_plan": {"answer_mode": "live_investigation"},
            "explicit_mitre_request": False,
            "alert_context_present": True,
        },
    }

    eleven_out = []
    for ref in ELEVEN:
        row = rows[ref]
        before = dump_meta(committed_meta[ref])
        after = dump_meta(promoted_meta[ref])
        field_delta = {
            field: {"before": before.get(field), "after": after.get(field)}
            for field in META_FIELDS
            if before.get(field) != after.get(field)
        }
        decisions = {}
        for name, kwargs in postures.items():
            kwargs = dict(kwargs)
            kwargs["question_ref"] = ref
            decisions[name] = {
                "before": decision_snapshot(committed_meta[ref], **kwargs),
                "after": decision_snapshot(promoted_meta[ref], **kwargs),
            }
        eleven_out.append(
            {
                "question_ref": ref,
                "question": row.get("question"),
                "pattern_type": row.get("pattern_type"),
                "legacy_router_intent_hint": row.get("legacy_router_intent_hint"),
                "field_delta": field_delta,
                "committed_meta": before,
                "promoted_meta": after,
                "decisions": decisions,
            }
        )

    after_runtime = sha256(RUNTIME)
    after_catalog = sha256(CATALOG)
    after_ledger = sha256(LEDGER)

    result = {
        "eleven_count": len(ELEVEN),
        "runtime_patch_changed_question_refs": sorted(patch_changed),
        "runtime_patch_changed_count": len(patch_changed),
        "catalog_patch_changed_use_case_ids": sorted(catalog_changed),
        "catalog_patch_changed_count": len(catalog_changed),
        "hashes_unchanged": {
            "runtime_map": before_runtime == after_runtime,
            "catalog": before_catalog == after_catalog,
            "drift_ledger": before_ledger == after_ledger,
            "runtime_sha256": before_runtime,
            "catalog_sha256": before_catalog,
            "ledger_sha256": before_ledger,
        },
        "eleven": eleven_out,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in result if k != "eleven"}, indent=2))
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
