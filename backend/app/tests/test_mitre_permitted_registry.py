from __future__ import annotations

from app.coverage.question_runtime_map import question_runtime_entry
from app.threat.mitre_permitted import (
    mitre_permitted_for_question_ref,
    resolve_mitre_mappings_for_chat,
)


def test_q004_has_taxonomy_mitre_permitted_on_runtime_map() -> None:
    entry = question_runtime_entry("q0.q004")
    assert entry is not None
    permitted = entry.get("mitre_permitted")
    assert isinstance(permitted, list)
    assert "T1071" in permitted or "T1041" in permitted
    assert "taxonomy_suggested_MITRE_candidates" in (entry.get("mitre_permitted_sources") or [])


def test_mitre_permitted_for_question_ref_helper() -> None:
    ids = mitre_permitted_for_question_ref("q0.q004")
    assert ids


def test_resolve_mitre_mappings_merges_use_case_and_registry() -> None:
    mappings = resolve_mitre_mappings_for_chat(
        question_ref="q0.q062",
        use_case_id="auth_failed_login_spike",
        source_refs=["ev-1"],
    )
    technique_ids = {m.technique_id for m in mappings}
    assert technique_ids
